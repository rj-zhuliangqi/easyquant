from datetime import date

import pandas as pd
from sqlalchemy import select

from app.models import FundFlowDailyHistory
from app.services.history_cache import HistoryCacheService


class FakeGateway:
    def fetch_daily_history(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"日期": date(2026, 5, 7), "主力净流入-净额": 10.0, "主力净流入-净占比": 1.0},
                {"日期": date(2026, 5, 8), "主力净流入-净额": 20.0, "主力净流入-净占比": 2.0},
            ]
        )


def test_ensure_daily_history_adds_only_missing_dates(db_session) -> None:
    db_session.add(
        FundFlowDailyHistory(
            sector_type="industry",
            sector_name="Alpha",
            trading_date=date(2026, 5, 7),
            main_net_amount=10.0,
            main_net_ratio=0.01,
        )
    )
    db_session.commit()

    HistoryCacheService(FakeGateway()).ensure_daily_history(db_session, sector_type="industry", sector_names=["Alpha"])

    rows = list(
        db_session.scalars(
            select(FundFlowDailyHistory)
            .where(FundFlowDailyHistory.sector_name == "Alpha")
            .order_by(FundFlowDailyHistory.trading_date.asc())
        )
    )

    assert [(row.trading_date.isoformat(), row.main_net_amount, row.main_net_ratio) for row in rows] == [
        ("2026-05-07", 10.0, 0.01),
        ("2026-05-08", 20.0, 0.02),
    ]