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
import math
import re
import time
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
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
_SIMILARITY_PUNCT_RE = re.compile(r"[，。！？、：；,.!?;:()（）【】\[\]《》“”\"'`·|｜/\\-]")
_NOISE_PREFIX_RE = re.compile(r"^(?:快讯|异动快报|公告精选|盘中快讯|午评|早评|财经早参|财联社|同花顺财经讯)[:：\s]*")
_NOISE_WORDS = ("消息称", "据悉", "财经讯", "表示", "称", "相关", "方面")
_EVENT_WORDS = (
    "回购", "并购", "收购", "中标", "签约", "涨价", "提价", "调价", "停牌", "复牌",
    "业绩", "预增", "减持", "增持", "重组", "涨停", "跌停", "减产", "限产", "订单",
    "合同", "合作", "投资", "涨幅", "跌幅", "上市", "获批", "调研",
)
_CONFLICT_EVENT_PAIRS = (("增持", "减持"), ("涨停", "跌停"), ("涨幅", "跌幅"), ("涨价", "降价"))
_CODE_RE = re.compile(r"(?<!\d)(?:[036]\d{5}|[68]\d{5})(?!\d)")
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_AMOUNT_RE = re.compile(r"\d+(?:\.\d+)?(?:亿元|万元|亿|万)")
_SOURCE_WEIGHT = {"ths_live": 90, "eastmoney_724": 85, "sina_roll": 75}
_SIMILARITY_WINDOW = timedelta(minutes=60)
_SIMILARITY_STRICT_WINDOW = timedelta(hours=2)


def _to_half_width(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _normalize_title_for_similarity(title: str) -> str:
    """更激进的相似度比较用标题归一化。

    保留数字/百分比/股票代码/金额，去掉来源前缀、标点、弱噪声词。
    """

    text = _to_half_width(title).lower().strip()
    text = _NOISE_PREFIX_RE.sub("", text)
    for word in _NOISE_WORDS:
        text = text.replace(word, "")
    text = _SIMILARITY_PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub("", text)
    return text


def _similarity_threshold(length: int) -> float | None:
    if length < 10:
        return None
    if length < 18:
        return 0.93
    if length <= 35:
        return 0.88
    return 0.84


def _extract_title_entities(title: str) -> dict[str, set[str]]:
    text = _to_half_width(title)
    return {
        "codes": set(_CODE_RE.findall(text)),
        "percents": set(_PERCENT_RE.findall(text)),
        "amounts": set(_AMOUNT_RE.findall(text)),
        "events": {word for word in _EVENT_WORDS if word in text},
    }


def _has_entity_conflict(a: dict[str, set[str]], b: dict[str, set[str]]) -> bool:
    if a["codes"] and b["codes"] and a["codes"].isdisjoint(b["codes"]):
        return True
    if a["amounts"] and b["amounts"] and a["amounts"].isdisjoint(b["amounts"]):
        return True
    for left, right in _CONFLICT_EVENT_PAIRS:
        if (left in a["events"] and right in b["events"]) or (right in a["events"] and left in b["events"]):
            return True
    return False


def _news_similarity(a: NewsItem, b: NewsItem) -> float:
    norm_a = _normalize_title_for_similarity(a.title)
    norm_b = _normalize_title_for_similarity(b.title)
    if norm_a == norm_b and norm_a:
        return 1.0
    threshold = _similarity_threshold(min(len(norm_a), len(norm_b)))
    if threshold is None:
        return 0.0
    if _has_entity_conflict(_extract_title_entities(a.title), _extract_title_entities(b.title)):
        return 0.0
    # 常见跨源改写：一个来源是短标题，另一个来源在后面追加背景信息。
    # 例如「美光科技涨幅收窄至10%」 vs 「美光科技涨幅收窄至10%，此前一度上涨20%」。
    # 只要较短标题已经达到动态阈值长度，就视为强相似。
    shorter, longer = sorted((norm_a, norm_b), key=len)
    if shorter and shorter in longer:
        return 0.98
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def _is_duplicate_candidate(a: NewsItem, b: NewsItem) -> tuple[bool, float]:
    # 同源连续快讯不做模糊聚合，只允许精确标题 hash 聚合。
    if a.source == b.source and a.title_hash != b.title_hash:
        return False, 0.0
    delta = abs(a.published_at - b.published_at)
    similarity = _news_similarity(a, b)
    if similarity >= 1.0 and delta <= _SIMILARITY_STRICT_WINDOW:
        return True, similarity
    norm_len = min(
        len(_normalize_title_for_similarity(a.title)),
        len(_normalize_title_for_similarity(b.title)),
    )
    threshold = _similarity_threshold(norm_len)
    if threshold is None:
        return False, similarity
    if delta <= _SIMILARITY_WINDOW and similarity >= threshold:
        return True, similarity
    if delta <= _SIMILARITY_STRICT_WINDOW and similarity >= 0.96:
        return True, similarity
    return False, similarity


def _decode_json_list(text: str | None) -> list[str]:
    if not text:
        return []
    try:
        value = json.loads(text)
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _source_weight(source: str) -> int:
    return _SOURCE_WEIGHT.get(source, 70)


def _choose_representative(items: list[NewsItem]) -> NewsItem:
    return sorted(
        items,
        key=lambda item: (
            bool(item.is_pinned),
            item.importance_level,
            _source_weight(item.source),
            bool(item.summary),
            bool(item.url),
            item.published_at,
            item.id,
        ),
        reverse=True,
    )[0]


def _rank_score(item: NewsItem, cluster_size: int = 1) -> float:
    now = datetime.now()
    age_minutes = max(0.0, (now - (item.published_at or item.fetched_at)).total_seconds() / 60)
    freshness_score = 100 * math.exp(-age_minutes / 180)
    importance_score = {0: 20, 1: 65, 2: 100}.get(item.importance_level or 0, 20)
    duplicate_score = min(100, 45 + 25 * math.log2(max(cluster_size, 1)))
    source_score = _source_weight(item.source)
    matched_action = _decode_json_list(item.matched_action)
    matched_industry = _decode_json_list(item.matched_industry)
    affected_stocks = _decode_json_list(item.affected_stocks)
    relevance_score = min(
        100,
        (35 if matched_action else 0)
        + (25 if matched_industry else 0)
        + (30 if affected_stocks else 0),
    )
    quality_score = min(
        100,
        (30 if item.summary else 0)
        + (20 if item.url else 0)
        + (20 if 8 <= len(item.title or "") <= 80 else 0)
        + (10 if item.published_at else 0)
        + (20 if cluster_size > 1 else 0),
    )
    pinned_boost = 15 if item.is_pinned else 0
    return round(
        freshness_score * 0.35
        + importance_score * 0.25
        + duplicate_score * 0.15
        + source_score * 0.10
        + relevance_score * 0.10
        + quality_score * 0.05
        + pinned_boost,
        2,
    )


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
        hours: int | None = 48,
        importance_min: int = 0,
        sources: list[str] | None = None,
        industries: list[str] | None = None,
        actions: list[str] | None = None,
        since_id: int | None = None,
        sort: str = "mixed",
    ) -> dict:
        """查询最近资讯。

        排序模式 ``sort``：
          - ``mixed``（默认）：``is_pinned DESC, published_at DESC`` — 重要置顶 + 时间倒序
          - ``latest``：``published_at DESC`` — 纯按时间，最新最上
          - ``important``：``importance_level DESC, published_at DESC`` — 红框 > 黄框 > 普通

        游标：``since_id`` 用于「加载更多」，下一页返回 ``id < since_id`` 的条目。

        返回 ``counts`` 是过滤窗口内**全量统计**（不是 limit 截断后的本页计数），
        ``window_total`` 给出窗口内符合 source/industry/action 筛选的总条数。

        返回 ``last_fetched_at`` 是 DB 里最新一条的 ``fetched_at`` —— 用户在 UI 上
        可看到「最近一次拉取数据 X 分钟前」，知道系统在动。
        """

        from sqlalchemy import case, func, or_

        # ── 1. 构建公共 WHERE（counts / items 共用）──
        cutoff = datetime.now() - timedelta(hours=hours) if hours is not None else None

        def _apply_window_filters(s):
            """窗口 + source/industry/action 过滤；不应用 importance_min 和 since_id。"""

            if cutoff is not None:
                s = s.where(NewsItem.published_at >= cutoff)
            if sources:
                s = s.where(NewsItem.source.in_(sources))
            if industries:
                s = s.where(or_(*[NewsItem.matched_industry.like(f'%"{ind}"%') for ind in industries]))
            if actions:
                s = s.where(or_(*[NewsItem.matched_action.like(f'%"{act}"%') for act in actions]))
            return s

        # ── 2. 窗口内的真实计数（无 LIMIT）──
        count_stmt = _apply_window_filters(
            select(
                func.count(NewsItem.id),
                func.sum(case((NewsItem.is_pinned == True, 1), else_=0)),  # noqa: E712
                func.sum(case((NewsItem.importance_level == 2, 1), else_=0)),
                func.sum(case((NewsItem.importance_level == 1, 1), else_=0)),
            )
        )
        row = session.execute(count_stmt).one()
        window_total = int(row[0] or 0)
        counts = {
            "total": window_total,
            "pinned": int(row[1] or 0),
            "high": int(row[2] or 0),
            "medium": int(row[3] or 0),
        }

        # ── 3. items 查询 — 多取候选后在查询层做 cluster 聚合去重 ──
        candidate_limit = min(max(limit * 8, 300), 1000)
        stmt = _apply_window_filters(select(NewsItem))
        if importance_min > 0:
            stmt = stmt.where(NewsItem.importance_level >= importance_min)
        if since_id is not None:
            stmt = stmt.where(NewsItem.id < since_id)
        stmt = stmt.order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(candidate_limit)

        candidates = session.execute(stmt).scalars().all()
        clusters = self._cluster_news_items(candidates)
        cluster_payloads = [self._serialize_cluster(cluster) for cluster in clusters]

        if sort == "latest":
            cluster_payloads.sort(key=lambda x: (x["published_at"], x["id"]), reverse=True)
        elif sort == "important":
            cluster_payloads.sort(
                key=lambda x: (
                    x["importance_level"],
                    x["published_at"],
                    x["duplicate_count"],
                    x["id"],
                ),
                reverse=True,
            )
        elif sort == "hot":
            cluster_payloads.sort(
                key=lambda x: (
                    x["rank_score"],
                    x["is_pinned"],
                    x["importance_level"],
                    x["duplicate_count"],
                    x["published_at"],
                    x["id"],
                ),
                reverse=True,
            )
        else:  # mixed（默认）
            cluster_payloads.sort(
                key=lambda x: (x["is_pinned"], x["published_at"], x["id"]),
                reverse=True,
            )
        out_items = cluster_payloads[:limit]

        # ── 4. 最近一次拉取时间 — DB 里 max(fetched_at) ──
        last_fetched = session.execute(select(func.max(NewsItem.fetched_at))).scalar()
        last_fetched_iso = (
            last_fetched.isoformat(timespec="seconds") if last_fetched else None
        )

        return {
            "items": out_items,
            "next_cursor": out_items[-1]["id"] if out_items else None,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "last_fetched_at": last_fetched_iso,
            "counts": counts,
            "display_counts": {"raw_total": window_total, "deduped_total": len(cluster_payloads)},
            "window_hours": hours,
            "sort": sort,
        }

    @staticmethod
    def _cluster_news_items(items: list[NewsItem]) -> list[list[NewsItem]]:
        """查询层聚合去重：保留原始新闻，只把展示结果合并为 cluster。"""

        clusters: list[list[NewsItem]] = []
        representatives: list[NewsItem] = []
        for item in items:
            matched_idx: int | None = None
            matched_similarity = 0.0
            for idx, rep in enumerate(representatives):
                ok, similarity = _is_duplicate_candidate(rep, item)
                if ok and similarity > matched_similarity:
                    matched_idx = idx
                    matched_similarity = similarity
            if matched_idx is None:
                clusters.append([item])
                representatives.append(item)
            else:
                clusters[matched_idx].append(item)
                representatives[matched_idx] = _choose_representative(clusters[matched_idx])
        return clusters

    @staticmethod
    def _serialize_cluster(cluster: list[NewsItem]) -> dict:
        representative = _choose_representative(cluster)
        payload = NewsService._serialize(representative)
        duplicates = [item for item in cluster if item.id != representative.id]
        serialized_duplicates = []
        for item in sorted(duplicates, key=lambda x: x.published_at, reverse=True):
            data = NewsService._serialize(item)
            data["similarity"] = round(_news_similarity(representative, item), 4)
            serialized_duplicates.append(data)
        sources = sorted({item.source for item in cluster}, key=_source_weight, reverse=True)
        rank_score = _rank_score(representative, len(cluster))
        payload.update(
            {
                "duplicate_count": len(cluster),
                "duplicate_sources": sources,
                "duplicates": serialized_duplicates,
                "rank_score": rank_score,
            }
        )
        return payload

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
            "fetched_at": item.fetched_at.isoformat(timespec="seconds") if item.fetched_at else None,
            "importance_level": item.importance_level,
            "matched_action": _decode(item.matched_action),
            "matched_industry": _decode(item.matched_industry),
            "is_pinned": bool(item.is_pinned),
        }
