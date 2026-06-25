"""tests for app.services.news_service — 去重 / importance / 单源容错。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import news_client
from app.models import NewsItem
from app.services import news_service as ns


@pytest.fixture(autouse=True)
def _reset_failure_state(monkeypatch):
    """每个测试前重置模块级失败计数，避免相互污染。"""

    ns._consecutive_failures.clear()
    ns._skip_until.clear()
    yield


def _make_item(source: str, source_id: str, title: str, *, summary: str = "",
               minutes_ago: int = 1) -> news_client.NormalizedNewsItem:
    return news_client.NormalizedNewsItem(
        source=source,
        source_id=source_id,
        title=title,
        summary=summary,
        url=f"https://example.com/{source_id}",
        published_at=datetime.now() - timedelta(minutes=minutes_ago),
        raw={},
    )


def test_dedup_same_source(db_session, monkeypatch):
    """同 (source, source_id) 跑两次 fetch_and_persist 只入库 1 行。"""

    item = _make_item("eastmoney_724", "abc123", "测试标题 1")
    monkeypatch.setattr(
        ns,
        "_FETCHERS",
        [("eastmoney_724", lambda: [item])],
    )

    svc = ns.NewsService()
    first = svc.fetch_and_persist(db_session)
    second = svc.fetch_and_persist(db_session)

    assert first["fetched"] == 1
    assert first["inserted"] == 1
    assert first["errors"] == []
    # 第二次跑：源仍返回同一条 → existing_keys 命中 → inserted=0
    assert second["fetched"] == 1
    assert second["inserted"] == 0

    listing = svc.list_recent_news(db_session, limit=10)
    assert listing["counts"]["total"] == 1


def test_importance_double_match_pinned():
    """命中行为 + 行业 → level=2、is_pinned=True。"""

    level, action_hits, industry_hits, pinned = ns.NewsService._compute_importance(
        "华鲁恒升宣布纯碱涨价 10%", "化工龙头集体跟涨"
    )
    assert level == 2
    assert "涨价" in action_hits
    assert "化工" in industry_hits
    assert pinned is True

    # 单命中（仅行为）→ level=1、不置顶
    level1, action1, industry1, pinned1 = ns.NewsService._compute_importance(
        "某公司业绩预增 80%", ""
    )
    assert level1 == 1
    assert action1 == ["业绩"]
    assert industry1 == []
    assert pinned1 is False

    # 都没命中
    level0, *_ = ns.NewsService._compute_importance("赛事结果公布", "围棋甲级联赛对决")
    assert level0 == 0


def test_single_source_failure_isolated(db_session, monkeypatch):
    """同花顺源 fetcher 抛错 → 不 raise；东财 + 新浪照常入库；errors 列出失败源。"""

    em_item = _make_item("eastmoney_724", "em1", "东财快讯")
    sina_item = _make_item("sina_roll", "sina1", "新浪头条")

    def _failing_ths() -> list[news_client.NormalizedNewsItem]:
        raise RuntimeError("simulated ths outage")

    monkeypatch.setattr(
        ns,
        "_FETCHERS",
        [
            ("eastmoney_724", lambda: [em_item]),
            ("ths_live", _failing_ths),
            ("sina_roll", lambda: [sina_item]),
        ],
    )

    svc = ns.NewsService()
    result = svc.fetch_and_persist(db_session)

    assert result["fetched"] == 2  # 只有 em + sina 成功
    assert result["inserted"] == 2
    assert len(result["errors"]) == 1
    assert result["errors"][0]["source"] == "ths_live"
    assert "simulated ths outage" in result["errors"][0]["msg"]

def test_list_recent_news_counts_sort_and_last_fetched(db_session):
    """counts 是窗口内全量统计；sort 可切换；返回 last_fetched_at 和每条 fetched_at。"""

    now = datetime.now()
    rows = [
        NewsItem(
            source="eastmoney_724",
            source_id="old-high",
            title_hash="h1",
            title="旧的重要新闻",
            published_at=now - timedelta(minutes=20),
            fetched_at=now - timedelta(minutes=19),
            importance_level=2,
            is_pinned=True,
        ),
        NewsItem(
            source="sina_roll",
            source_id="new-normal",
            title_hash="h2",
            title="最新普通新闻",
            published_at=now - timedelta(minutes=1),
            fetched_at=now,
            importance_level=0,
            is_pinned=False,
        ),
        NewsItem(
            source="ths_live",
            source_id="mid-medium",
            title_hash="h3",
            title="中等关注新闻",
            published_at=now - timedelta(minutes=5),
            fetched_at=now - timedelta(minutes=4),
            importance_level=1,
            is_pinned=False,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()

    svc = ns.NewsService()
    limited = svc.list_recent_news(db_session, limit=1, hours=48, sort="mixed")
    assert limited["counts"] == {"total": 3, "pinned": 1, "high": 1, "medium": 1}
    assert limited["last_fetched_at"] is not None
    assert limited["items"][0]["fetched_at"] is not None

    latest = svc.list_recent_news(db_session, limit=3, hours=48, sort="latest")
    assert [item["title"] for item in latest["items"]] == [
        "最新普通新闻",
        "中等关注新闻",
        "旧的重要新闻",
    ]

    important = svc.list_recent_news(db_session, limit=3, hours=48, sort="important")
    assert [item["importance_level"] for item in important["items"]] == [2, 1, 0]


def test_cross_source_similarity_dedup_cluster(db_session):
    """东财/同花顺轻微改写的同一条新闻，查询层聚合为一条展示。"""

    now = datetime.now()
    db_session.add_all(
        [
            NewsItem(
                source="eastmoney_724",
                source_id="em-mu",
                title_hash="h-em-mu",
                title="美光科技涨幅收窄至10%",
                summary="此前一度上涨20%",
                url="https://example.com/em",
                published_at=now - timedelta(minutes=2),
                fetched_at=now - timedelta(minutes=1),
                importance_level=0,
                is_pinned=False,
            ),
            NewsItem(
                source="ths_live",
                source_id="ths-mu",
                title_hash="h-ths-mu",
                title="美光科技涨幅收窄至10%，此前一度上涨20%",
                summary="美光科技盘中涨幅回落",
                url="https://example.com/ths",
                published_at=now - timedelta(minutes=3),
                fetched_at=now - timedelta(minutes=1),
                importance_level=0,
                is_pinned=False,
            ),
        ]
    )
    db_session.commit()

    svc = ns.NewsService()
    result = svc.list_recent_news(db_session, limit=10, hours=48, sort="latest")

    assert result["counts"]["total"] == 2  # 原始条数仍保留
    assert result["display_counts"]["deduped_total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["duplicate_count"] == 2
    assert set(item["duplicate_sources"]) == {"eastmoney_724", "ths_live"}
    assert len(item["duplicates"]) == 1
    assert item["duplicates"][0]["similarity"] >= 0.84


def test_similarity_does_not_merge_conflicting_stock_codes(db_session):
    """标题结构相似但股票代码不同，不能错误聚合。"""

    now = datetime.now()
    db_session.add_all(
        [
            NewsItem(
                source="eastmoney_724",
                source_id="em-a",
                title_hash="h-a",
                title="600519 贵州茅台拟回购股份",
                published_at=now - timedelta(minutes=2),
                fetched_at=now,
                importance_level=1,
                is_pinned=False,
            ),
            NewsItem(
                source="ths_live",
                source_id="ths-b",
                title_hash="h-b",
                title="000858 五粮液拟回购股份",
                published_at=now - timedelta(minutes=3),
                fetched_at=now,
                importance_level=1,
                is_pinned=False,
            ),
        ]
    )
    db_session.commit()

    result = ns.NewsService().list_recent_news(db_session, limit=10, hours=48)
    assert result["display_counts"]["deduped_total"] == 2
    assert all(item["duplicate_count"] == 1 for item in result["items"])


def test_hot_sort_uses_duplicate_boost(db_session):
    """综合热度排序中，多源重复新闻应排在同级别单源新闻前。"""

    now = datetime.now()
    db_session.add_all(
        [
            NewsItem(
                source="eastmoney_724",
                source_id="em-ai",
                title_hash="h-ai-1",
                title="AI算力芯片需求持续增长",
                summary="多家机构关注",
                published_at=now - timedelta(minutes=5),
                fetched_at=now,
                importance_level=1,
                matched_industry='["AI", "半导体"]',
                is_pinned=False,
            ),
            NewsItem(
                source="ths_live",
                source_id="ths-ai",
                title_hash="h-ai-2",
                title="AI算力芯片需求持续增长 多家机构关注",
                summary="同花顺跟进报道",
                published_at=now - timedelta(minutes=6),
                fetched_at=now,
                importance_level=1,
                matched_industry='["AI", "半导体"]',
                is_pinned=False,
            ),
            NewsItem(
                source="sina_roll",
                source_id="sina-single",
                title_hash="h-single",
                title="普通单源关注新闻",
                summary="单源消息",
                published_at=now - timedelta(minutes=4),
                fetched_at=now,
                importance_level=1,
                is_pinned=False,
            ),
        ]
    )
    db_session.commit()

    result = ns.NewsService().list_recent_news(db_session, limit=10, hours=48, sort="hot")
    assert result["items"][0]["duplicate_count"] == 2
    assert result["items"][0]["rank_score"] > result["items"][1]["rank_score"]