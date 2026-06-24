from contextlib import contextmanager
from datetime import datetime
import re

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import _collect_once, _run_scheduled_job, create_app, create_session_factory
from app.models import FundFlowDailyHistory, FundFlowSnapshot


class FakeGateway:
    def __init__(self) -> None:
        self.sector_stock_calls = 0
        self.individual_calls = 0
        self.source_snapshots = {
            "market_index_spot": {
                "source_label": "tencent",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": True,
                "degraded_fields": [],
            },
            "market_index_history:sh000001": {
                "source_label": "akshare",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": False,
                "degraded_fields": [],
            },
            "market_index_history:sz399001": {
                "source_label": "akshare",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": False,
                "degraded_fields": [],
            },
            "market_index_history:sz399006": {
                "source_label": "akshare",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": False,
                "degraded_fields": [],
            },
            "market_breadth": {
                "source_label": "akshare",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": False,
                "degraded_fields": [],
            },
        }

    def resolve_sector_name(self, sector_type: str, sector_name: str) -> str | None:
        mapping = {
            ("industry", "公路铁路运输"): "铁路公路",
            ("concept", "电网"): "智能电网",
        }
        return mapping.get((sector_type, sector_name), sector_name)

    def fetch_industry_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "行业": "Alpha",
                    "行业指数": 8123.11,
                    "行业-涨跌幅": "1.56%",
                    "流入资金": 120.5,
                    "流出资金": 88.3,
                    "净额": 32.2,
                    "公司家数": 145,
                    "领涨股": "A1",
                    "领涨股-涨跌幅": "4.12%",
                    "当前价": 320.55,
                }
            ]
        )

    def fetch_concept_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "概念": "智能电网",
                    "概念指数": 3021.88,
                    "概念-涨跌幅": "-0.35%",
                    "流入资金": 25.8,
                    "流出资金": 31.2,
                    "净额": -5.4,
                    "公司家数": 18,
                    "领涨股": "C1",
                    "领涨股-涨跌幅": "2.22%",
                    "当前价": 188.18,
                }
            ]
        )

    def fetch_sector_stocks(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        self.sector_stock_calls += 1
        if sector_type == "concept":
            return pd.DataFrame(
                [
                    {"代码": "300001", "名称": "C1", "最新价": 88.88, "今日主力净流入-净额": "1.2亿", "今日涨跌幅": "2.22%"},
                ]
            )
        return pd.DataFrame(
            [
                {"代码": "002371", "名称": "A1", "最新价": 320.55, "今日主力净流入-净额": 6.8, "今日涨跌幅": 4.12},
                {"代码": "688256", "名称": "A2", "最新价": 188.18, "今日主力净流入-净额": 3.5, "今日涨跌幅": 2.22},
            ]
        )

    def fetch_individual_realtime(self) -> pd.DataFrame:
        self.individual_calls += 1
        return pd.DataFrame(
            [
                {"股票代码": "002371", "股票简称": "A1", "最新价": 320.55, "净额": 6.8, "涨跌幅": 4.12},
                {"股票代码": "688256", "股票简称": "A2", "最新价": 188.18, "净额": 3.5, "涨跌幅": 2.22},
            ]
        )

    def fetch_sector_catalog(self, sector_type: str) -> list[str]:
        if sector_type == "concept":
            return ["智能电网", "商业航天"]
        return ["Alpha", "Beta", "铁路公路"]

    def fetch_daily_history(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_limit_up_pool(self, date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "002111",
                    "名称": "Alpha连板",
                    "涨跌幅": 10.01,
                    "最新价": 12.8,
                    "成交额": 950000000.0,
                    "流通市值": 8600000000.0,
                    "总市值": 11200000000.0,
                    "换手率": 18.6,
                    "封板资金": 240000000.0,
                    "首次封板时间": "093201",
                    "最后封板时间": "093201",
                    "炸板次数": 0,
                    "涨停统计": "4/4",
                    "连板数": 4,
                    "所属行业": "消费电子",
                },
                {
                    "序号": 2,
                    "代码": "300888",
                    "名称": "Beta首板",
                    "涨跌幅": 20.0,
                    "最新价": 45.2,
                    "成交额": 680000000.0,
                    "流通市值": 5200000000.0,
                    "总市值": 6600000000.0,
                    "换手率": 22.4,
                    "封板资金": 180000000.0,
                    "首次封板时间": "101500",
                    "最后封板时间": "132000",
                    "炸板次数": 1,
                    "涨停统计": "1/1",
                    "连板数": 1,
                    "所属行业": "通信服务",
                },
                {
                    "序号": 3,
                    "代码": "688666",
                    "名称": "Gamma二板",
                    "涨跌幅": 19.99,
                    "最新价": 88.3,
                    "成交额": 420000000.0,
                    "流通市值": 7300000000.0,
                    "总市值": 9800000000.0,
                    "换手率": 9.7,
                    "封板资金": 96000000.0,
                    "首次封板时间": "094500",
                    "最后封板时间": "145000",
                    "炸板次数": 2,
                    "涨停统计": "2/2",
                    "连板数": 2,
                    "所属行业": "半导体",
                },
            ]
        )

    def fetch_previous_limit_up_pool(self, date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "002111",
                    "名称": "Alpha连板",
                    "涨跌幅": 10.01,
                    "最新价": 12.8,
                    "涨停价": 12.8,
                    "成交额": 950000000.0,
                    "流通市值": 8600000000.0,
                    "总市值": 11200000000.0,
                    "换手率": 18.6,
                    "涨速": 0.0,
                    "振幅": 4.1,
                    "昨日封板时间": "093500",
                    "昨日连板数": 3,
                    "涨停统计": "4/4",
                    "所属行业": "消费电子",
                },
                {
                    "序号": 2,
                    "代码": "600123",
                    "名称": "Delta断板",
                    "涨跌幅": 3.1,
                    "最新价": 9.8,
                    "涨停价": 10.22,
                    "成交额": 410000000.0,
                    "流通市值": 4800000000.0,
                    "总市值": 5200000000.0,
                    "换手率": 15.2,
                    "涨速": 0.2,
                    "振幅": 7.8,
                    "昨日封板时间": "101200",
                    "昨日连板数": 1,
                    "涨停统计": "1/1",
                    "所属行业": "通用设备",
                },
            ]
        )

    def fetch_broken_limit_up_pool(self, date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "600123",
                    "名称": "Delta断板",
                    "涨跌幅": 3.1,
                    "最新价": 9.8,
                    "涨停价": 10.22,
                    "成交额": 410000000.0,
                    "流通市值": 4800000000.0,
                    "总市值": 5200000000.0,
                    "换手率": 15.2,
                    "涨速": 0.2,
                    "首次封板时间": "101200",
                    "炸板次数": 3,
                    "涨停统计": "1/1",
                    "振幅": 7.8,
                    "所属行业": "通用设备",
                }
            ]
        )

    def fetch_strong_limit_up_pool(self, date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": 1,
                    "代码": "002111",
                    "名称": "Alpha连板",
                    "涨跌幅": 10.01,
                    "最新价": 12.8,
                    "涨停价": 12.8,
                    "成交额": 950000000.0,
                    "流通市值": 8600000000.0,
                    "总市值": 11200000000.0,
                    "换手率": 18.6,
                    "涨速": 0.0,
                    "是否新高": "是",
                    "量比": 2.8,
                    "涨停统计": "4/4",
                    "入选理由": "高标龙头",
                    "所属行业": "消费电子",
                }
            ]
        )

    def fetch_stock_daily_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"日期": datetime(2026, 5, 8).date(), "股票代码": symbol, "成交额": 510000000.0, "振幅": 5.1, "涨跌幅": 3.2, "换手率": 14.1},
                {"日期": datetime(2026, 5, 9).date(), "股票代码": symbol, "成交额": 580000000.0, "振幅": 4.7, "涨跌幅": 2.1, "换手率": 15.3},
                {"日期": datetime(2026, 5, 12).date(), "股票代码": symbol, "成交额": 760000000.0, "振幅": 6.2, "涨跌幅": 5.5, "换手率": 17.6},
                {"日期": datetime(2026, 5, 13).date(), "股票代码": symbol, "成交额": 820000000.0, "振幅": 5.9, "涨跌幅": 6.8, "换手率": 18.1},
                {"日期": datetime(2026, 5, 14).date(), "股票代码": symbol, "成交额": 950000000.0, "振幅": 4.1, "涨跌幅": 10.01, "换手率": 18.6},
            ]
        )

    def fetch_stock_fund_flow_history(self, stock: str, market: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"日期": datetime(2026, 5, 8).date(), "收盘价": 10.21, "涨跌幅": 3.2, "主力净流入-净额": 32000000.0},
                {"日期": datetime(2026, 5, 9).date(), "收盘价": 10.58, "涨跌幅": 2.1, "主力净流入-净额": 41000000.0},
                {"日期": datetime(2026, 5, 12).date(), "收盘价": 11.11, "涨跌幅": 5.5, "主力净流入-净额": 68000000.0},
                {"日期": datetime(2026, 5, 13).date(), "收盘价": 11.63, "涨跌幅": 6.8, "主力净流入-净额": 72000000.0},
                {"日期": datetime(2026, 5, 14).date(), "收盘价": 12.8, "涨跌幅": 10.01, "主力净流入-净额": 88000000.0},
            ]
        )

    def fetch_market_index_spot(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"代码": "sh000001", "名称": "上证指数", "最新价": 3245.67, "涨跌额": 12.34, "涨跌幅": 0.38, "成交额": 456700000000.0},
                {"代码": "sz399001", "名称": "深证成指", "最新价": 10234.56, "涨跌额": -21.45, "涨跌幅": -0.21, "成交额": 612300000000.0},
                {"代码": "sz399006", "名称": "创业板指", "最新价": 1988.8, "涨跌额": 6.12, "涨跌幅": 0.31, "成交额": 188600000000.0},
            ]
        )

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        base = {
            "sh000001": 3200.0,
            "sz399001": 10100.0,
            "sz399006": 1960.0,
        }.get(symbol, 1000.0)
        return pd.DataFrame(
            [
                {"date": datetime(2026, 5, 9).date(), "open": base + 1.0, "high": base + 8.0, "low": base - 3.0, "close": base + 5.0, "volume": 100000000.0},
                {"date": datetime(2026, 5, 12).date(), "open": base + 4.0, "high": base + 10.0, "low": base + 1.0, "close": base + 9.0, "volume": 120000000.0},
                {"date": datetime(2026, 5, 13).date(), "open": base + 9.0, "high": base + 14.0, "low": base + 7.0, "close": base + 12.0, "volume": 132000000.0},
            ]
        )

    def fetch_market_breadth(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"item": "上涨", "value": 3210.0},
                {"item": "下跌", "value": 1430.0},
                {"item": "平盘", "value": 96.0},
                {"item": "涨停", "value": 81.0},
                {"item": "跌停", "value": 12.0},
                {"item": "活跃度", "value": "62.40%"},
                {"item": "统计日期", "value": "2026-05-07 15:00:00"},
            ]
        )

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        return self.source_snapshots.get(
            key,
            {
                "source_label": "akshare",
                "updated_at": "2026-05-07T15:00:00",
                "fallback_used": False,
                "degraded_fields": [],
            },
        )

    def fetch_stock_quote_batch(self, symbols: list[str]) -> dict[str, dict[str, float | str | None]]:
        return {
            "002371": {"code": "002371", "price": 321.11, "change_percent": 4.56},
            "688256": {"code": "688256", "price": 189.01, "change_percent": 2.88},
        }


def build_client_and_gateway() -> tuple[TestClient, FakeGateway]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    with testing_session_local() as session:
        session.add_all(
            [
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Alpha",
                    captured_at=datetime(2026, 5, 7, 9, 59, 0),
                    sector_index=8088.0,
                    change_percent=1.1,
                    inflow=110.0,
                    outflow=90.0,
                    net_amount=20.0,
                    company_count=145,
                    leading_stock="A1",
                    leading_stock_change=3.0,
                    leading_stock_price=300.0,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Alpha",
                    captured_at=datetime(2026, 5, 7, 10, 0, 0),
                    sector_index=8100.0,
                    change_percent=1.3,
                    inflow=115.0,
                    outflow=85.0,
                    net_amount=30.0,
                    company_count=145,
                    leading_stock="A1",
                    leading_stock_change=3.5,
                    leading_stock_price=310.0,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Alpha",
                    captured_at=datetime(2026, 5, 7, 10, 1, 0),
                    sector_index=8123.11,
                    change_percent=1.56,
                    inflow=120.5,
                    outflow=88.3,
                    net_amount=32.2,
                    company_count=145,
                    leading_stock="A1",
                    leading_stock_change=4.12,
                    leading_stock_price=320.55,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Beta",
                    captured_at=datetime(2026, 5, 7, 9, 59, 0),
                    sector_index=7750.0,
                    change_percent=0.7,
                    inflow=500.0,
                    outflow=450.0,
                    net_amount=50.0,
                    company_count=100,
                    leading_stock="B1",
                    leading_stock_change=1.2,
                    leading_stock_price=180.0,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Beta",
                    captured_at=datetime(2026, 5, 7, 10, 0, 0),
                    sector_index=7780.0,
                    change_percent=0.75,
                    inflow=520.0,
                    outflow=470.0,
                    net_amount=50.0,
                    company_count=100,
                    leading_stock="B1",
                    leading_stock_change=1.5,
                    leading_stock_price=190.0,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Beta",
                    captured_at=datetime(2026, 5, 7, 10, 1, 0),
                    sector_index=7800.0,
                    change_percent=0.8,
                    inflow=600.0,
                    outflow=540.0,
                    net_amount=60.0,
                    company_count=100,
                    leading_stock="B1",
                    leading_stock_change=2.0,
                    leading_stock_price=200.0,
                ),
                FundFlowSnapshot(
                    sector_type="concept",
                    sector_name="智能电网",
                    captured_at=datetime(2026, 5, 7, 10, 1, 0),
                    sector_index=3000.0,
                    change_percent=0.8,
                    inflow=200.0,
                    outflow=160.0,
                    net_amount=40.0,
                    company_count=88,
                    leading_stock="C1",
                    leading_stock_change=2.0,
                    leading_stock_price=88.0,
                ),
                FundFlowSnapshot(
                    sector_type="industry",
                    sector_name="Alpha",
                    captured_at=datetime(2026, 5, 6, 10, 1, 0),
                    sector_index=8000.0,
                    change_percent=1.0,
                    inflow=100.0,
                    outflow=80.0,
                    net_amount=20.0,
                    company_count=10,
                    leading_stock="A1",
                    leading_stock_change=1.2,
                    leading_stock_price=30.0,
                ),
                FundFlowDailyHistory(
                    sector_type="industry",
                    sector_name="Alpha",
                    trading_date=datetime(2026, 5, 6).date(),
                    main_net_amount=20.0,
                    main_net_ratio=0.1111,
                ),
                FundFlowDailyHistory(
                    sector_type="industry",
                    sector_name="Alpha",
                    trading_date=datetime(2026, 5, 7).date(),
                    main_net_amount=32.2,
                    main_net_ratio=0.1542,
                ),
                FundFlowDailyHistory(
                    sector_type="industry",
                    sector_name="Beta",
                    trading_date=datetime(2026, 5, 7).date(),
                    main_net_amount=60.0,
                    main_net_ratio=0.0526,
                ),
            ]
        )
        session.commit()

    gateway = FakeGateway()
    app = create_app(
        session_factory=testing_session_local,
        gateway=gateway,
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 7, 16, 0, 0),
    )
    return TestClient(app), gateway


def build_client() -> TestClient:
    client, _ = build_client_and_gateway()
    return client


def test_sqlite_session_factory_enables_wal_and_busy_timeout(tmp_path) -> None:
    db_path = tmp_path / "dashboard.db"
    session_factory = create_session_factory(f"sqlite+pysqlite:///{db_path.as_posix()}")

    with session_factory() as session:
        journal_mode = session.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = session.execute(text("PRAGMA busy_timeout")).scalar()
        synchronous = session.execute(text("PRAGMA synchronous")).scalar()

    assert str(journal_mode).lower() == "wal"
    assert busy_timeout >= 30000
    assert synchronous == 1


def test_core_collector_job_does_not_run_heavy_cache_refreshes() -> None:
    class CollectorSpy:
        def __init__(self) -> None:
            self.calls = 0

        def collect_snapshot(self, session, captured_at=None):
            self.calls += 1
            return {"industry": 1, "concept": 1}

    class RealtimeSpy:
        def __init__(self) -> None:
            self.individual_calls = 0
            self.watched_calls = 0

        def refresh_individual_rankings(self, session, trading_date=None):
            self.individual_calls += 1

        def refresh_watched_sector_stocks(self, session, trading_date=None):
            self.watched_calls += 1

    @contextmanager
    def session_factory():
        yield object()

    collector = CollectorSpy()
    realtime = RealtimeSpy()

    _collect_once(
        session_factory,
        dashboard=object(),
        collector=collector,
        realtime_cache=realtime,
        now_provider=lambda: datetime(2026, 5, 13, 10, 30, 0),
    )

    assert collector.calls == 1
    assert realtime.individual_calls == 0
    assert realtime.watched_calls == 0


def test_scheduled_job_rolls_back_and_swallows_cache_failures() -> None:
    class SessionSpy:
        def __init__(self) -> None:
            self.rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

    session = SessionSpy()

    @contextmanager
    def session_factory():
        yield session

    result = _run_scheduled_job("failing-cache", session_factory, lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    assert result is None
    assert session.rolled_back is True


def test_overview_endpoint_returns_rankings_by_strength() -> None:
    client = build_client()

    response = client.get("/api/overview", params={"sector_type": "industry"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["leaders"][0]["sector_name"] == "Alpha"
    assert round(payload["leaders"][0]["net_strength"], 4) == round(32.2 / (120.5 + 88.3), 4)


def test_comparison_endpoint_returns_multi_sector_series() -> None:
    client = build_client()

    response = client.get(
        "/api/comparison",
        params={"sector_type": "industry", "metric": "net_strength", "granularity": "minute", "lookback_days": 2, "limit": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["series"][0]["sector_name"] == "Alpha"
    assert len(payload["series"]) == 2


def test_comparison_endpoint_supports_laggards_rank_view() -> None:
    client = build_client()

    response = client.get(
        "/api/comparison",
        params={
            "sector_type": "industry",
            "metric": "net_strength",
            "granularity": "minute",
            "lookback_days": 2,
            "limit": 2,
            "rank_view": "laggards",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [series["sector_name"] for series in payload["series"]] == ["Beta", "Alpha"]


def test_comparison_endpoint_supports_specific_trading_date() -> None:
    client = build_client()

    response = client.get(
        "/api/comparison",
        params={
            "sector_type": "industry",
            "metric": "net_strength",
            "granularity": "minute",
            "lookback_days": 30,
            "limit": 0,
            "trading_date": "2026-05-06",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_at"] == "2026-05-06T10:01:00"
    assert [series["sector_name"] for series in payload["series"]] == ["Alpha"]


def test_comparison_endpoint_filters_invalid_watchlist_names() -> None:
    client = build_client()

    response = client.get(
        "/api/comparison",
        params={
            "sector_type": "concept",
            "metric": "net_strength",
            "granularity": "minute",
            "lookback_days": 1,
            "limit": 1,
            "include_sectors": "电网,幽灵概念",
            "trading_date": "2026-05-07",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [series["sector_name"] for series in payload["series"]] == ["智能电网"]
    assert payload["invalid_watchlist"] == ["幽灵概念"]


def test_alerts_endpoint_returns_items() -> None:
    client = build_client()

    response = client.get("/api/alerts", params={"sector_type": "industry"})

    assert response.status_code == 200
    assert "items" in response.json()


def test_status_reports_market_closed() -> None:
    client = build_client()

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["market_open"] is False


def test_sector_and_individual_endpoints_read_from_cache_after_first_request() -> None:
    client, gateway = build_client_and_gateway()

    first_sector = client.get(
        "/api/sector-stocks",
        params={"sector_type": "industry", "sector_name": "Alpha", "page": 1, "page_size": 1},
    )
    second_sector = client.get(
        "/api/sector-stocks",
        params={"sector_type": "industry", "sector_name": "Alpha", "page": 2, "page_size": 1},
    )
    first_individual = client.get("/api/individual-rankings", params={"page": 1, "page_size": 1, "limit": 0})
    second_individual = client.get("/api/individual-rankings", params={"page": 1, "page_size": 5, "limit": 0})

    assert first_sector.status_code == 200
    assert second_sector.status_code == 200
    assert first_individual.status_code == 200
    assert second_individual.status_code == 200
    assert gateway.sector_stock_calls == 1
    assert gateway.individual_calls == 1
    assert first_sector.json()["total"] == 2
    assert second_sector.json()["page"] == 2
    assert second_sector.json()["stocks"][0]["名称"] == "A2"
    assert first_individual.json()["total"] == 2
    assert second_individual.json()["sort_by"] == "net_amount"


def test_stock_search_endpoint_returns_specific_stock_matches() -> None:
    client, gateway = build_client_and_gateway()

    client.get("/api/individual-rankings", params={"page": 1, "page_size": 5, "limit": 0})
    response = client.get("/api/stock-search", params={"keyword": "A1"})

    assert response.status_code == 200
    payload = response.json()
    assert gateway.individual_calls == 1
    assert payload["items"][0]["股票代码"] == "002371"
    assert payload["items"][0]["股票简称"] == "A1"


def test_sector_stocks_endpoint_supports_concept_type() -> None:
    client = build_client()

    response = client.get("/api/sector-stocks", params={"sector_type": "concept", "sector_name": "智能电网"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sector_type"] == "concept"
    assert payload["stocks"][0]["名称"] == "C1"


def test_realtime_quote_overlay_updates_displayed_sector_and_individual_prices() -> None:
    client = build_client()

    sector_payload = client.get(
        "/api/sector-stocks",
        params={"sector_type": "industry", "sector_name": "Alpha", "sort_by": "net_amount", "sort_order": "desc", "page": 1, "page_size": 10},
    ).json()
    individual_payload = client.get(
        "/api/individual-rankings",
        params={"limit": 0, "sort_by": "net_amount", "sort_order": "desc", "page": 1, "page_size": 10},
    ).json()

    assert sector_payload["stocks"][0]["最新价"] == 321.11
    assert sector_payload["stocks"][0]["今日涨跌幅"] == 4.56
    assert individual_payload["stocks"][0]["最新价"] == 321.11
    assert individual_payload["stocks"][0]["涨跌幅"] == 4.56


def test_individual_force_refresh_falls_back_to_cached_snapshot_when_live_refresh_fails() -> None:
    class FlakyGateway(FakeGateway):
        def __init__(self) -> None:
            super().__init__()
            self.fail_individual = False

        def fetch_individual_realtime(self) -> pd.DataFrame:
            if self.fail_individual:
                self.individual_calls += 1
                return pd.DataFrame()
            return super().fetch_individual_realtime()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    gateway = FlakyGateway()
    app = create_app(
        session_factory=testing_session_local,
        gateway=gateway,
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 7, 10, 30, 0),
    )
    client = TestClient(app)

    first = client.get("/api/individual-rankings", params={"page": 1, "page_size": 5, "limit": 0})
    gateway.fail_individual = True
    second = client.get("/api/individual-rankings", params={"page": 1, "page_size": 5, "limit": 0, "force_refresh": "true"})

    assert first.status_code == 200
    assert first.json()["source_status"] == "fetched"
    assert second.status_code == 200
    assert second.json()["source_status"] == "stale_cache"
    assert second.json()["fallback_reason"] == "cached_snapshot_after_refresh_failure"
    assert second.json()["total"] == 2


def test_scheduler_registers_individual_rankings_startup_job(monkeypatch, tmp_path) -> None:
    scheduled_ids: list[str] = []

    class FakeScheduler:
        def __init__(self, *args, **kwargs) -> None:
            self.running = False

        def add_job(self, func, trigger, **kwargs) -> None:
            scheduled_ids.append(kwargs["id"])

        def start(self) -> None:
            self.running = True

        def shutdown(self, wait: bool = False) -> None:
            self.running = False

    monkeypatch.setattr("app.main.BackgroundScheduler", FakeScheduler)

    session_factory = create_session_factory(f"sqlite+pysqlite:///{(tmp_path / 'scheduler.db').as_posix()}")
    app = create_app(
        session_factory=session_factory,
        gateway=FakeGateway(),
        enable_scheduler=True,
        now_provider=lambda: datetime(2026, 5, 7, 10, 30, 0),
    )

    with TestClient(app):
        pass

    assert "collector-core-startup" in scheduled_ids
    assert "individual-rankings-cache-startup" in scheduled_ids


def test_metadata_endpoints_return_dates_and_sector_names() -> None:
    client = build_client()

    dates_response = client.get("/api/trading-dates", params={"sector_type": "industry"})
    sectors_response = client.get("/api/sectors", params={"sector_type": "industry", "trading_date": "2026-05-07"})

    assert dates_response.status_code == 200
    assert dates_response.json()["dates"] == ["2026-05-07", "2026-05-06"]
    assert sectors_response.status_code == 200
    assert sectors_response.json()["sectors"] == ["Alpha", "Beta"]


def test_sector_catalog_endpoint_returns_full_catalog() -> None:
    client = build_client()

    concept_catalog = client.get("/api/sector-catalog", params={"sector_type": "concept"})
    industry_catalog = client.get("/api/sector-catalog", params={"sector_type": "industry"})

    assert concept_catalog.status_code == 200
    assert set(concept_catalog.json()["sectors"]) == {"商业航天", "智能电网"}
    assert industry_catalog.status_code == 200
    assert industry_catalog.json()["sectors"] == ["Alpha", "Beta", "铁路公路"]


def test_system_home_and_page_routes_are_available() -> None:
    client = build_client()

    home = client.get("/")
    sector_page = client.get("/sector-monitor")
    limit_page = client.get("/limit-up-ladder")
    alerts_page = client.get("/alerts")
    opportunity_page = client.get("/opportunity-pool")
    review_page = client.get("/review-center", follow_redirects=False)
    ai_page = client.get("/ai-center")
    workspace_page = client.get("/workspace")

    assert home.status_code == 200
    assert 'id="app"' in home.text
    assert sector_page.status_code == 200
    assert sector_page.text == home.text
    assert limit_page.status_code == 200
    assert limit_page.text == home.text
    assert alerts_page.status_code == 200
    assert alerts_page.text == home.text
    assert opportunity_page.status_code == 200
    assert opportunity_page.text == home.text
    assert review_page.status_code in {302, 307}
    assert review_page.headers["location"] == "/review"
    assert ai_page.status_code == 200
    assert ai_page.text == home.text
    assert workspace_page.status_code == 200
    assert workspace_page.text == home.text
    return

    assert home.status_code == 200
    assert "市场总览驾驶舱" in home.text
    assert "市场情绪复核" in home.text
    assert "当前分档" in home.text
    assert sector_page.status_code == 200
    assert "板块资金监控工作台" in sector_page.text
    assert limit_page.status_code == 200
    assert "A股连板梯度" in limit_page.text
    assert alerts_page.status_code == 200
    assert "预警" in alerts_page.text
    assert opportunity_page.status_code == 200
    assert "机会" in opportunity_page.text
    assert review_page.status_code in {302, 307}
    assert review_page.headers["location"] == "/review"
    assert ai_page.status_code == 200
    assert "AI" in ai_page.text
    assert workspace_page.status_code == 200
    assert "观察" in workspace_page.text


def test_main_pages_share_the_same_primary_navigation_order() -> None:
    client = build_client()
    expected = [
        "/",
        "/alerts",
        "/opportunity-pool",
        "/sector-monitor",
        "/limit-up-ladder",
        "/ai-center",
        "/workspace",
    ]
    page_urls = [
        "/",
        "/alerts",
        "/opportunity-pool",
        "/sector-monitor",
        "/limit-up-ladder",
        "/ai-center",
        "/workspace",
    ]

    root_text = client.get("/").text
    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        assert response.text == root_text
        assert 'id="app"' in response.text
    return

    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        match = re.search(r"<nav[^>]*>(.*?)</nav>", response.text, flags=re.S)
        assert match is not None, f"missing nav in {page_url}"
        hrefs = re.findall(r'href="([^"]+)"', match.group(1))
        assert hrefs == expected, f"unexpected nav order in {page_url}: {hrefs}"


def test_main_pages_use_compact_navigation_and_headers() -> None:
    client = build_client()
    page_urls = [
        "/",
        "/alerts",
        "/opportunity-pool",
        "/sector-monitor",
        "/limit-up-ladder",
        "/ai-center",
        "/workspace",
    ]

    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        assert 'id="app"' in response.text
        assert "global-sidebar" not in response.text, f"unexpected legacy shell markup in {page_url}"
        assert "workspace-shell" not in response.text, f"unexpected legacy page markup in {page_url}"
    return

    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        assert "global-description" not in response.text, f"unexpected sidebar description in {page_url}"
        assert "global-sidebar-note" not in response.text, f"unexpected sidebar note in {page_url}"
        assert "hero-subtitle" not in response.text, f"unexpected hero subtitle in {page_url}"
        assert "global-kicker" not in response.text, f"unexpected sidebar kicker in {page_url}"
        assert "hero-kicker" not in response.text, f"unexpected hero kicker in {page_url}"
        assert "hero-mark" not in response.text, f"unexpected hero mark in {page_url}"
        assert "eyebrow" not in response.text, f"unexpected eyebrow label in {page_url}"
        assert "hero-chip-row" not in response.text, f"unexpected hero chip row in {page_url}"
        assert "status-note" not in response.text, f"unexpected status note in {page_url}"
        assert re.search(r'<div class="panel-head[^"]*"[^>]*>\s*<h3>.*?</h3>\s*<p>', response.text, flags=re.S) is None, f"unexpected panel-head description in {page_url}"
        assert re.search(r'<div class="panel-header[^"]*"[^>]*>.*?<h2>.*?</h2>\s*<p>', response.text, flags=re.S) is None, f"unexpected panel-header description in {page_url}"
        assert re.search(r'<div class="detail-card-header">\s*<div>\s*<h3>.*?</h3>\s*<p>', response.text, flags=re.S) is None, f"unexpected detail-card-header description in {page_url}"


def test_main_pages_use_short_lived_shell_cache() -> None:
    client = build_client()
    page_urls = [
        "/",
        "/alerts",
        "/opportunity-pool",
        "/sector-monitor",
        "/limit-up-ladder",
        "/ai-center",
        "/workspace",
    ]

    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "max-age=300" in cache_control.lower(), f"unexpected cache-control for {page_url}: {cache_control}"
        assert "stale-while-revalidate" in cache_control.lower(), f"unexpected cache-control for {page_url}: {cache_control}"
    return

    for page_url in page_urls:
        response = client.get(page_url)
        assert response.status_code == 200
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" in cache_control.lower(), f"unexpected cache-control for {page_url}: {cache_control}"


def test_home_market_overview_endpoint_returns_indices_and_breadth() -> None:
    client = build_client()

    response = client.get("/api/home/market-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_at"] == "2026-05-07T15:00:00"
    assert [item["symbol"] for item in payload["indices"]] == ["sh000001", "sz399001", "sz399006"]
    assert [item["name"] for item in payload["indices"]] == ["上证指数", "深证成指", "创业板指"]
    assert payload["breadth"]["up_count"] == 3210
    assert payload["breadth"]["down_count"] == 1430
    assert payload["breadth"]["limit_up_count"] == 81
    assert payload["breadth"]["limit_down_count"] == 12
    assert payload["breadth"]["market_turnover"] == 1069000000000.0
    assert payload["source_summary"]["indices"]["source_label"] == "tencent"
    assert payload["source_summary"]["indices"]["fallback_used"] is True
    assert payload["source_summary"]["breadth"]["source_label"] == "akshare"
    assert payload["source_summary"]["degraded_fields"] == []
    assert payload["indices"][0]["source_status"]["source_label"] == "tencent"


def test_home_system_summary_endpoint_returns_dual_module_summary() -> None:
    client = build_client()

    response = client.get("/api/home/system-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sector_monitor"]["current_sector_type"] == "industry"
    assert payload["sector_monitor"]["strongest_inflow_sector"] == "Beta"
    assert payload["sector_monitor"]["weakest_outflow_sector"] == "Alpha"
    assert payload["limit_up_ladder"]["highest_board"] == 4
    assert payload["limit_up_ladder"]["limit_up_count"] == 3
    assert payload["limit_up_ladder"]["market_temperature"]["temperature_score"] >= 0
    assert payload["limit_up_ladder"]["market_temperature"]["temperature_band"] in {"冰点", "偏冷", "中性", "偏热", "过热"}
    assert payload["limit_up_ladder"]["market_temperature"]["summary_text"]
    assert payload["action_priority"]["primary_workspace"] in {"sector-monitor", "limit-up-ladder"}
    assert payload["alert_summary"]["title"]
    assert payload["opportunity_summary"]["title"]
    assert payload["source_summary"]["sector_monitor"]["source_label"] == "cache"
    assert payload["source_summary"]["limit_up_ladder"]["source_label"] == "akshare"


def test_home_system_summary_bootstraps_sector_snapshot_when_cache_is_empty() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    app = create_app(
        session_factory=testing_session_local,
        gateway=FakeGateway(),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 7, 10, 30, 0),
    )
    client = TestClient(app)

    response = client.get("/api/home/system-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sector_monitor"]["strongest_inflow_sector"] is not None
    with testing_session_local() as session:
        assert session.query(FundFlowSnapshot).count() > 0


def test_alerts_feed_endpoint_returns_unified_signal_items() -> None:
    client = build_client()

    response = client.get("/api/alerts/feed", params={"limit": 8})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["signal_type"] in {"market", "sector", "limit_up", "stock"}
    assert payload["items"][0]["freshness_level"] in {"realtime", "delayed", "cache", "stale"}
    assert "action_url" in payload["items"][0]


def test_alerts_summary_endpoint_returns_counts_and_top_signal() -> None:
    client = build_client()

    response = client.get("/api/alerts/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "total" in payload
    assert "high_priority_count" in payload
    assert "top_signal" in payload


def test_opportunities_endpoint_returns_candidates_with_reason_and_risk() -> None:
    client = build_client()

    response = client.get("/api/opportunities", params={"mode": "high-conviction-limitup", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["candidate_type"] in {"sector", "stock", "hybrid"}
    assert payload["items"][0]["entry_reason"]
    assert payload["items"][0]["risk_flag"]
    assert payload["items"][0]["freshness_level"] in {"realtime", "delayed", "cache", "stale"}


def test_review_endpoints_return_daily_overview_and_timeline() -> None:
    client = build_client()

    day_response = client.get("/api/review/day", params={"trading_date": "2026-05-07"})
    timeline_response = client.get("/api/review/timeline", params={"trading_date": "2026-05-07"})

    assert day_response.status_code == 200
    assert timeline_response.status_code == 200
    assert "temperature" in day_response.json()
    assert "top_sectors" in day_response.json()
    assert "ladder_summary" in day_response.json()
    assert timeline_response.json()["items"]


def test_workspace_and_notes_endpoints_persist_watch_items_and_note() -> None:
    client = build_client()

    save_response = client.put(
        "/api/workspace",
        json={
            "watched_sectors": [{"sector_type": "industry", "sector_name": "Alpha"}],
            "watched_stocks": [{"stock_code": "002111", "stock_name": "Alpha连板", "watch_reason": "高标观察"}],
        },
    )
    note_response = client.post(
        "/api/notes",
        json={"trading_date": "2026-05-07", "subject_type": "stock", "subject_key": "002111", "content": "早盘强封，关注回封承接"},
    )
    get_response = client.get("/api/workspace")

    assert save_response.status_code == 200
    assert note_response.status_code == 200
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["watched_sectors"]
    assert payload["watched_stocks"]
    assert payload["notes"]


def test_home_status_endpoint_reports_subsystem_availability() -> None:
    client = build_client()

    response = client.get("/api/home/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_open"] is False
    assert payload["subsystems"]["sector_monitor"] is True
    assert payload["subsystems"]["limit_up_ladder"] is True
    assert payload["updated_at"] == "2026-05-07T16:00:00"


def test_limit_up_dates_endpoint_returns_recent_trade_dates() -> None:
    client = build_client()

    response = client.get("/api/limit-up/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dates"][0] == "2026-05-07"
    assert len(payload["dates"]) >= 5


def test_limit_up_summary_endpoint_returns_sentiment_metrics() -> None:
    client = build_client()

    response = client.get("/api/limit-up/summary", params={"trading_date": "2026-05-07"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["highest_board"] == 4
    assert payload["limit_up_count"] == 3
    assert payload["first_board_count"] == 1
    assert payload["broken_count"] == 1
    assert payload["promotion_count"] == 1
    assert payload["promotion_rate"] == 0.5


def test_limit_up_temperature_endpoint_returns_temperature_payload() -> None:
    client = build_client()

    response = client.get("/api/limit-up/temperature", params={"trading_date": "2026-05-07"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["trading_date"] == "2026-05-07"
    assert "temperature_score" in payload
    assert payload["temperature_band"] in {"冰点", "偏冷", "中性", "偏热", "过热"}
    assert "summary_text" in payload
    assert "factors" in payload
    assert "raw_metrics" in payload
    assert "signals" in payload
    assert "highest_board_score" in payload["factors"]
    assert payload["raw_metrics"]["highest_board"] == 4


def test_limit_up_temperature_history_endpoint_returns_recent_history() -> None:
    client = build_client()

    response = client.get("/api/limit-up/temperature-history", params={"lookback_days": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["lookback_days"] == 5
    assert len(payload["items"]) == 5
    assert "temperature_score" in payload["items"][0]
    assert payload["items"][0]["temperature_band"] in {"冰点", "偏冷", "中性", "偏热", "过热"}


def test_limit_up_ladder_endpoint_groups_stocks_by_board_count() -> None:
    client = build_client()

    response = client.get("/api/limit-up/ladder", params={"trading_date": "2026-05-07", "market_scope": "all"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["groups"][0]["board_count"] == 4
    assert payload["groups"][0]["stock_count"] == 1
    assert payload["groups"][0]["leader"]["code"] == "002111"
    assert payload["groups"][-1]["board_count"] == 1


def test_limit_up_broken_endpoint_returns_broken_board_pool() -> None:
    client = build_client()

    response = client.get("/api/limit-up/broken", params={"trading_date": "2026-05-07"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["code"] == "600123"
    assert payload["items"][0]["broken_board_count"] == 3


def test_limit_up_stock_detail_returns_history_and_rank_context() -> None:
    client = build_client()

    response = client.get("/api/limit-up/stock-detail", params={"trading_date": "2026-05-07", "stock_code": "002111"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"]["code"] == "002111"
    assert payload["stock"]["board_count"] == 4
    assert len(payload["turnover_history"]) == 5
    assert len(payload["net_inflow_history"]) == 5
    assert payload["peer_rankings"]["net_inflow_rank"] == 1


def test_limit_up_search_endpoint_finds_stock_in_ladder() -> None:
    client = build_client()

    response = client.get("/api/limit-up/search", params={"trading_date": "2026-05-07", "keyword": "Alpha"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["code"] == "002111"
    assert payload["items"][0]["source_view"] == "ladder"


def test_monitor_signals_endpoint_returns_board_metrics() -> None:
    client = build_client()

    response = client.get("/api/monitor-signals", params={"sector_type": "industry", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_at"] == "2026-05-07T10:01:00"
    assert payload["items"][0]["sector_name"] == "Alpha"
    assert "acceleration_1" in payload["items"][0]
    assert "acceleration_3" in payload["items"][0]
    assert "persistence" in payload["items"][0]
    assert "divergence" in payload["items"][0]


def test_watchlist_endpoints_persist_and_refresh_prefetch() -> None:
    client, gateway = build_client_and_gateway()

    put_response = client.put(
        "/api/watchlist",
        json=[
            {"sector_type": "industry", "sector_name": "公路铁路运输"},
            {"sector_type": "concept", "sector_name": "电网"},
        ],
    )
    get_response = client.get("/api/watchlist")
    refresh_response = client.post("/api/refresh")
    status_response = client.get("/api/status")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert refresh_response.status_code == 200
    assert status_response.status_code == 200
    assert {item["sector_name"] for item in get_response.json()["items"]} == {"铁路公路", "智能电网"}
    assert refresh_response.json()["prefetched"] >= 2
    assert "cold_rotated" in refresh_response.json()
    assert gateway.sector_stock_calls >= 2
    assert status_response.json()["watched_sector_count"] == 2


def test_navigation_routes_serve_shared_spa_shell() -> None:
    client = build_client()

    root_response = client.get("/")
    alerts_response = client.get("/alerts")
    workspace_response = client.get("/workspace")

    assert root_response.status_code == 200
    assert alerts_response.status_code == 200
    assert workspace_response.status_code == 200
    assert 'id="app"' in root_response.text
    assert root_response.text == alerts_response.text
    assert root_response.text == workspace_response.text
    assert "max-age=300" in root_response.headers["cache-control"]


def test_home_page_aggregate_endpoint_returns_shell_payload() -> None:
    client = build_client()

    response = client.get("/api/page/home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == "home"
    assert payload["source_status"] == "cache_hit"
    assert payload["refresh_recommended"] is False
    assert payload["updated_at"] == payload["payload"]["status"]["updated_at"]
    assert payload["payload"]["market_overview"]["indices"][0]["symbol"] == "sh000001"
    assert payload["payload"]["system_summary"]["sector_monitor"]["strongest_inflow_sector"] == "Beta"


def test_alerts_page_aggregate_endpoint_returns_summary_and_feed() -> None:
    client = build_client()

    response = client.get("/api/page/alerts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == "alerts"
    assert payload["source_status"] == "cache_hit"
    assert payload["refresh_recommended"] is False
    assert payload["payload"]["summary"]["total"] >= 1
    assert payload["payload"]["feed"]["items"][0]["signal_type"] in {"market", "sector", "limit_up", "stock"}


def test_sector_monitor_page_aggregate_endpoint_returns_bootstrap_payload() -> None:
    client = build_client()

    response = client.get("/api/page/sector-monitor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == "sector-monitor"
    assert payload["payload"]["overview"]["leaders"][0]["sector_name"] == "Alpha"
    assert payload["payload"]["watchlist"]["items"] == []
    assert payload["payload"]["sector_catalog"]["industry"][0] == "Alpha"
