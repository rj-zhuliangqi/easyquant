from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_app
from app.models import FundFlowDailyHistory, FundFlowSnapshot


class FakeGateway:
    def __init__(self) -> None:
        self.sector_stock_calls = 0
        self.individual_calls = 0

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


def test_sector_stocks_endpoint_supports_concept_type() -> None:
    client = build_client()

    response = client.get("/api/sector-stocks", params={"sector_type": "concept", "sector_name": "智能电网"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sector_type"] == "concept"
    assert payload["stocks"][0]["名称"] == "C1"


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
