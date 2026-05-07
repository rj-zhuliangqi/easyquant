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
                    "概念": "Concept-X",
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

    def fetch_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"代码": "002371", "名称": "A1", "最新价": 320.55, "今日主力净流入-净额": 6.8, "今天涨跌幅": 4.12},
                {"代码": "688256", "名称": "A2", "最新价": 188.18, "今日主力净流入-净额": 3.5, "今天涨跌幅": 2.22},
            ]
        )

    def fetch_individual_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"股票代码": "002371", "股票简称": "A1", "最新价": 320.55, "净额": 6.8, "涨跌幅": 4.12}]
        )


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    with TestingSessionLocal() as session:
        session.add_all(
            [
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

    app = create_app(
        session_factory=TestingSessionLocal,
        gateway=FakeGateway(),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 7, 16, 0, 0),
    )
    return TestClient(app)


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


def test_sector_stocks_endpoint_returns_drilldown_rows() -> None:
    client = build_client()

    response = client.get("/api/sector-stocks", params={"sector_name": "Alpha"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sector_name"] == "Alpha"
    assert payload["stocks"][0]["名称"] == "A1"
