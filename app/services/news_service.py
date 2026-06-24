"""实时资讯服务 — 三源轮询入库 + 关键词打分 + 查询。

由 :mod:`app.main` 的 APScheduler 每 5 分钟调用 :py:meth:`NewsService.fetch_and_persist`
拉取最新资讯落库；前端通过 ``GET /api/news/realtime`` 调
:py:meth:`NewsService.list_recent_news` 查询。

单源失败由本层 try/except 隔离，连续 3 次失败的源跳过 5 分钟再试，
不引入「健康表」（看 uvicorn.log 即可定位）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import news_client
from app.models import NewsItem
from app.news_keywords import match_keywords


logger = logging.getLogger(__name__)


# 跨源去重的相似窗：30 分钟内同 title_hash 视为重复
_CROSS_SOURCE_DEDUP_WINDOW = timedelta(minutes=30)

# 连续失败 N 次的源跳过 M 秒；不引入「健康表」，进程内记账即可
_FAILURE_THRESHOLD = 3
_FAILURE_SKIP_SECONDS = 300
_consecutive_failures: dict[str, int] = {}
_skip_until: dict[str, float] = {}


# 三个 fetcher 的注册表，方便测试 monkeypatch
Fetcher = Callable[[], list[news_client.NormalizedNewsItem]]
_FETCHERS: list[tuple[str, Fetcher]] = [
    ("eastmoney_724", lambda: news_client.fetch_eastmoney_724(200)),
    ("ths_live", lambda: news_client.fetch_ths_live(1, 50)),
    ("sina_roll", lambda: news_client.fetch_sina_roll(100)),
]


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    """去空白 / 截前 50 字符，给跨源去重算 sha1 用。"""

    return _WHITESPACE_RE.sub("", title)[:50]


def _title_hash(title: str) -> str:
    return hashlib.sha1(_normalize_title(title).encode("utf-8")).hexdigest()[:40]


class NewsService:
    """服务层 — 无副作用，显式传入 session（与 :mod:`app.services.ai_center` 一致）。"""

    def fetch_and_persist(self, session: Session) -> dict:
        """三源串行抓取 → 去重 → 计算 importance → bulk insert。

        返回 ``{"fetched": int, "inserted": int, "pinned": int, "errors": [...]}``。
        单源失败不影响其他源；失败次数累积到阈值后自动跳过 5 分钟。
        """

        all_items: list[news_client.NormalizedNewsItem] = []
        errors: list[dict] = []
        now_mono = time.monotonic()

        for source, fetcher in _FETCHERS:
            skip_until = _skip_until.get(source, 0.0)
            if skip_until > now_mono:
                logger.info("news fetch skipped (cooling) source=%s remain=%.0fs",
                            source, skip_until - now_mono)
                continue
            try:
                items = fetcher()
                all_items.extend(items)
                _consecutive_failures[source] = 0
            except Exception as exc:  # noqa: BLE001 — 单源失败必须隔离
                logger.exception("news fetch failed source=%s", source)
                errors.append({"source": source, "msg": str(exc)})
                _consecutive_failures[source] = _consecutive_failures.get(source, 0) + 1
                if _consecutive_failures[source] >= _FAILURE_THRESHOLD:
                    _skip_until[source] = now_mono + _FAILURE_SKIP_SECONDS
                    logger.warning(
                        "news source=%s reached failure threshold %d, skipping for %ds",
                        source, _FAILURE_THRESHOLD, _FAILURE_SKIP_SECONDS,
                    )
                    _consecutive_failures[source] = 0

        result = {"fetched": len(all_items), "inserted": 0, "pinned": 0, "errors": errors}
        if not all_items:
            return result

        # 同源已存在的 (source, source_id) 一次性查出来，做差集
        existing_keys: set[tuple[str, str]] = set()
        by_source: dict[str, list[str]] = {}
        for item in all_items:
            by_source.setdefault(item["source"], []).append(item["source_id"])
        for source, source_ids in by_source.items():
            # SQLite IN 列表理论上限大，但分批保险
            for i in range(0, len(source_ids), 500):
                chunk = source_ids[i : i + 500]
                rows = session.execute(
                    select(NewsItem.source, NewsItem.source_id)
                    .where(NewsItem.source == source)
                    .where(NewsItem.source_id.in_(chunk))
                ).all()
                existing_keys.update((r.source, r.source_id) for r in rows)

        # 跨源去重窗：30 分钟内已见过的 title_hash 也跳过
        recent_cutoff = datetime.now() - _CROSS_SOURCE_DEDUP_WINDOW
        recent_hashes: set[str] = set(
            session.execute(
                select(NewsItem.title_hash).where(NewsItem.published_at >= recent_cutoff)
            ).scalars()
        )

        rows: list[dict] = []
        pinned_count = 0
        seen_hashes_this_batch: set[str] = set()
        for item in all_items:
            key = (item["source"], item["source_id"])
            if key in existing_keys:
                continue
            th = _title_hash(item["title"])
            if th in recent_hashes or th in seen_hashes_this_batch:
                continue
            seen_hashes_this_batch.add(th)

            level, action_hits, industry_hits, is_pinned = self._compute_importance(
                item["title"], item.get("summary", "")
            )
            if is_pinned:
                pinned_count += 1

            rows.append(
                {
                    "source": item["source"],
                    "source_id": item["source_id"],
                    "title_hash": th,
                    "title": item["title"][:300],
                    "summary": (item.get("summary") or "")[:800] or None,
                    "url": item.get("url") or None,
                    "published_at": item["published_at"],
                    "fetched_at": datetime.now(),
                    "importance_level": level,
                    "matched_action": json.dumps(action_hits, ensure_ascii=False) if action_hits else None,
                    "matched_industry": json.dumps(industry_hits, ensure_ascii=False) if industry_hits else None,
                    "affected_stocks": None,  # v1 留口
                    "is_pinned": is_pinned,
                    "raw_json": None,  # v1 不存原始，节省 DB 体积；需要时再开
                }
            )

        if rows:
            session.bulk_insert_mappings(NewsItem, rows)
            session.commit()

        result["inserted"] = len(rows)
        result["pinned"] = pinned_count
        return result

    def list_recent_news(
        self,
        session: Session,
        *,
        limit: int = 50,
        hours: int | None = 24,
        importance_min: int = 0,
        sources: list[str] | None = None,
        industries: list[str] | None = None,
        actions: list[str] | None = None,
        since_id: int | None = None,
    ) -> dict:
        """查询最近资讯。

        排序：``is_pinned DESC, published_at DESC``，置顶条目在前。
        游标：``since_id`` 用于「加载更多」，给出当前展示列表中最小 id，下一页返回
        ``id < since_id`` 的条目。
        """

        stmt = select(NewsItem)
        if hours is not None:
            stmt = stmt.where(NewsItem.published_at >= datetime.now() - timedelta(hours=hours))
        if importance_min > 0:
            stmt = stmt.where(NewsItem.importance_level >= importance_min)
        if sources:
            stmt = stmt.where(NewsItem.source.in_(sources))
        if since_id is not None:
            stmt = stmt.where(NewsItem.id < since_id)

        # industries / actions 用 LIKE 命中 JSON 字符串（SQLite 上 JSON1 函数不普及，
        # 用粗暴的子串 LIKE 即可 — JSON 字符串里出现 "化工" 就算命中）
        if industries:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(*[NewsItem.matched_industry.like(f'%"{ind}"%') for ind in industries])
            )
        if actions:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(*[NewsItem.matched_action.like(f'%"{act}"%') for act in actions])
            )

        stmt = stmt.order_by(NewsItem.is_pinned.desc(), NewsItem.published_at.desc()).limit(limit)

        items = session.execute(stmt).scalars().all()

        out_items = [self._serialize(item) for item in items]
        counts = {
            "total": len(out_items),
            "pinned": sum(1 for x in out_items if x["is_pinned"]),
            "high": sum(1 for x in out_items if x["importance_level"] == 2),
            "medium": sum(1 for x in out_items if x["importance_level"] == 1),
        }
        return {
            "items": out_items,
            "next_cursor": out_items[-1]["id"] if out_items else None,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "counts": counts,
        }

    @staticmethod
    def _compute_importance(title: str, summary: str) -> tuple[int, list[str], list[str], bool]:
        """关键词命中评分。

        ``(level, action_hits, industry_hits, is_pinned)``
        - 双命中 → ``(2, [...], [...], True)``：置顶
        - 单命中 → ``(1, [...], [], False)`` 或 ``(1, [], [...], False)``
        - 都没命中 → ``(0, [], [], False)``
        """

        text = f"{title} {summary or ''}"
        action_hits, industry_hits = match_keywords(text)
        if action_hits and industry_hits:
            return 2, action_hits, industry_hits, True
        if action_hits or industry_hits:
            return 1, action_hits, industry_hits, False
        return 0, [], [], False

    @staticmethod
    def _serialize(item: NewsItem) -> dict:
        def _decode(text: str | None) -> list[str]:
            if not text:
                return []
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return []

        return {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "summary": item.summary,
            "url": item.url,
            "published_at": item.published_at.isoformat(timespec="seconds"),
            "importance_level": item.importance_level,
            "matched_action": _decode(item.matched_action),
            "matched_industry": _decode(item.matched_industry),
            "is_pinned": bool(item.is_pinned),
        }
