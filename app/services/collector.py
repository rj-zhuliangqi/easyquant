from __future__ import annotations

from app.time_utils import now_cn
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FundFlowSnapshot


class FundFlowCollector:
    def __init__(self, gateway: Any) -> None:
        self.gateway = gateway

    def collect_snapshot(self, session: Session, captured_at: datetime | None = None) -> dict[str, int]:
        captured_at = captured_at or now_cn().replace(tzinfo=None).replace(second=0, microsecond=0)
        industry_rows = self._normalize(self.gateway.fetch_industry_realtime(), "industry", captured_at)
        concept_rows = self._normalize(self.gateway.fetch_concept_realtime(), "concept", captured_at)
        session.add_all(industry_rows + concept_rows)
        session.commit()
        return {"industry": len(industry_rows), "concept": len(concept_rows)}

    def list_snapshots(self, session: Session) -> list[FundFlowSnapshot]:
        return list(session.scalars(select(FundFlowSnapshot).order_by(FundFlowSnapshot.id)))

    def _normalize(
        self,
        frame: pd.DataFrame,
        sector_type: str,
        captured_at: datetime,
    ) -> list[FundFlowSnapshot]:
        rows: list[FundFlowSnapshot] = []
        for row in frame.to_dict(orient="records"):
            name_key = self._pick_key(row, "行业", "概念")
            index_key = self._pick_key(row, "行业指数", "概念指数")
            change_key = self._pick_key(row, "行业-涨跌幅", "概念-涨跌幅")
            rows.append(
                FundFlowSnapshot(
                    sector_type=sector_type,
                    sector_name=str(row.get(name_key, "")),
                    captured_at=captured_at,
                    sector_index=self._to_float(row.get(index_key)),
                    change_percent=self._to_percent(row.get(change_key)),
                    inflow=self._to_float(row.get("流入资金")),
                    outflow=self._to_float(row.get("流出资金")),
                    net_amount=self._to_float(row.get("净额")),
                    company_count=self._to_int(row.get("公司家数")),
                    leading_stock=self._to_str(row.get("领涨股")),
                    leading_stock_change=self._to_percent(row.get("领涨股-涨跌幅")),
                    leading_stock_price=self._to_float(row.get("当前价")),
                )
            )
        return rows

    @staticmethod
    def _to_percent(value: Any) -> float | None:
        if value is None or value == "" or value == "--":
            return None
        try:
            if isinstance(value, str):
                return float(value.replace("%", ""))
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "" or value == "--":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @staticmethod
    def _to_str(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    @staticmethod
    def _pick_key(row: dict[str, Any], *candidates: str) -> str:
        for key in candidates:
            if key in row:
                return key
        return candidates[0]
