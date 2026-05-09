from datetime import date, datetime

import pandas as pd

from app.models import IndividualStockSnapshot, SectorStockSnapshot
from app.services.realtime_cache import RealtimeCacheService


class FakeGateway:
    def __init__(self) -> None:
        self.sector_stock_calls = 0
        self.individual_calls = 0

    def fetch_sector_stocks(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        self.sector_stock_calls += 1
        return pd.DataFrame(
            [
                {
                    "代码": "000001",
                    "名称": f"{sector_name}-A",
                    "最新价": 12.3,
                    "今日涨跌幅": 1.23,
                    "今日主力净流入-净额": 8.8,
                }
            ]
        )

    def fetch_individual_realtime(self) -> pd.DataFrame:
        self.individual_calls += 1
        return pd.DataFrame(
            [
                {
                    "股票代码": "000001",
                    "股票简称": "平安银行",
                    "最新价": 11.2,
                    "涨跌幅": 0.56,
                    "净额": 5.4,
                },
                {
                    "股票代码": "600036",
                    "股票简称": "招商银行",
                    "最新价": 42.5,
                    "涨跌幅": -0.12,
                    "净额": 3.1,
                },
            ]
        )


def test_sector_stock_cache_reads_from_database_after_first_fetch(db_session) -> None:
    gateway = FakeGateway()
    service = RealtimeCacheService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 9, 14, 59, 0))

    first = service.get_sector_stocks(db_session, sector_type="industry", sector_name="军民融合")
    second = service.get_sector_stocks(db_session, sector_type="industry", sector_name="军民融合")

    assert gateway.sector_stock_calls == 1
    assert first["updated_at"] == "2026-05-09T14:59:00"
    assert second["stocks"][0]["名称"] == "军民融合-A"
    rows = db_session.query(SectorStockSnapshot).all()
    assert len(rows) == 1
    assert rows[0].sector_name == "军民融合"


def test_individual_rankings_cache_reads_from_database_after_first_fetch(db_session) -> None:
    gateway = FakeGateway()
    service = RealtimeCacheService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 9, 14, 59, 0))

    first = service.get_individual_rankings(db_session, limit=1)
    second = service.get_individual_rankings(db_session, limit=2)

    assert gateway.individual_calls == 1
    assert first["stocks"][0]["股票简称"] == "平安银行"
    assert len(second["stocks"]) == 2
    rows = db_session.query(IndividualStockSnapshot).all()
    assert len(rows) == 2
    assert rows[0].trading_date == date(2026, 5, 9)


def test_sector_stock_cache_reports_unavailable_when_gateway_returns_no_rows(db_session) -> None:
    class EmptyGateway(FakeGateway):
        def fetch_sector_stocks(self, sector_type: str, sector_name: str) -> pd.DataFrame:
            self.sector_stock_calls += 1
            return pd.DataFrame(columns=["代码", "名称", "最新价", "今日涨跌幅", "今日主力净流入-净额"])

    service = RealtimeCacheService(gateway=EmptyGateway(), now_provider=lambda: datetime(2026, 5, 9, 14, 59, 0))

    payload = service.get_sector_stocks(db_session, sector_type="industry", sector_name="军民融合")

    assert payload["stocks"] == []
    assert payload["source_status"] == "unavailable"


def test_sector_stock_cache_supports_sorting_and_pagination(db_session) -> None:
    gateway = FakeGateway()
    service = RealtimeCacheService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 9, 14, 59, 0))
    service.get_sector_stocks(db_session, sector_type="industry", sector_name="军民融合")

    db_session.add_all(
        [
            SectorStockSnapshot(
                sector_type="industry",
                sector_name="军民融合",
                trading_date=date(2026, 5, 9),
                captured_at=datetime(2026, 5, 9, 14, 59, 0),
                stock_code="000002",
                stock_name="军民融合-B",
                latest_price=18.8,
                change_percent=8.6,
                main_net_amount=2.1,
            ),
            SectorStockSnapshot(
                sector_type="industry",
                sector_name="军民融合",
                trading_date=date(2026, 5, 9),
                captured_at=datetime(2026, 5, 9, 14, 59, 0),
                stock_code="000003",
                stock_name="军民融合-C",
                latest_price=22.3,
                change_percent=-1.4,
                main_net_amount=12.5,
            ),
        ]
    )
    db_session.commit()

    payload = service.get_sector_stocks(
        db_session,
        sector_type="industry",
        sector_name="军民融合",
        sort_by="change_percent",
        sort_order="asc",
        page=2,
        page_size=1,
    )

    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["sort_by"] == "change_percent"
    assert payload["sort_order"] == "asc"
    assert len(payload["stocks"]) == 1
    assert payload["stocks"][0]["代码"] == "000001"


def test_individual_rankings_support_sorting_and_pagination(db_session) -> None:
    gateway = FakeGateway()
    service = RealtimeCacheService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 9, 14, 59, 0))

    payload = service.get_individual_rankings(
        db_session,
        limit=100,
        sort_by="change_percent",
        sort_order="asc",
        page=2,
        page_size=1,
    )

    assert payload["total"] == 2
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["sort_by"] == "change_percent"
    assert payload["sort_order"] == "asc"
    assert len(payload["stocks"]) == 1
    assert payload["stocks"][0]["股票代码"] == "000001"
