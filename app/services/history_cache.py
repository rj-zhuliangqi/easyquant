from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FundFlowDailyHistory


class HistoryCacheService:
    def __init__(self, gateway: Any) -> None:
        self.gateway = gateway

    def ensure_daily_history(self, session: Session, sector_type: str, sector_names: list[str]) -> None:
        for sector_name in sector_names:
            existing = session.scalar(
                select(FundFlowDailyHistory.id)
                .where(FundFlowDailyHistory.sector_type == sector_type, FundFlowDailyHistory.sector_name == sector_name)
                .limit(1)
            )
            if existing:
                continue
            frame = self.gateway.fetch_daily_history(sector_type, sector_name)
            if frame.empty:
                continue
            rows = []
            for record in frame.to_dict(orient="records"):
                trading_date = record.get("日期")
                if trading_date is None:
                    continue
                rows.append(
                    FundFlowDailyHistory(
                        sector_type=sector_type,
                        sector_name=sector_name,
                        trading_date=trading_date,
                        main_net_amount=self._to_float(record.get("主力净流入-净额")),
                        main_net_ratio=self._to_ratio(record.get("主力净流入-净占比")),
                    )
                )
            if rows:
                session.add_all(rows)
                session.commit()

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _to_ratio(value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value) / 100
