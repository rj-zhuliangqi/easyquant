from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import FundFlowDailyHistory, FundFlowSnapshot


class DashboardService:
    def get_latest_rankings(
        self,
        session: Session,
        sector_type: str,
        limit: int = 10,
        metric: str = "net_strength",
        trading_date: date | None = None,
    ) -> dict:
        latest_time = self._latest_timestamp(session, sector_type, trading_date=trading_date)
        if latest_time is None:
            return {"updated_at": None, "leaders": [], "laggards": [], "metric": metric}

        rows = self._rows_at_timestamp(session, sector_type, latest_time)
        ranked_rows = sorted(rows, key=lambda row: self._metric_value(row, metric), reverse=True)
        effective_limit = self._normalize_limit(limit, len(ranked_rows))
        leaders = [self._snapshot_to_dict(row, metric) for row in ranked_rows[:effective_limit]]
        laggards = [self._snapshot_to_dict(row, metric) for row in list(reversed(ranked_rows[-effective_limit:]))]
        return {
            "updated_at": latest_time.isoformat(),
            "metric": metric,
            "leaders": leaders,
            "laggards": laggards,
        }

    def get_comparison_series(
        self,
        session: Session,
        sector_type: str,
        metric: str,
        granularity: str,
        lookback_days: int,
        limit: int,
        include_sector_names: list[str] | None = None,
        trading_date: date | None = None,
    ) -> dict:
        if granularity == "day":
            latest_time = self._latest_timestamp(session, sector_type)
            if latest_time is None:
                return {"updated_at": None, "metric": metric, "granularity": granularity, "series": []}

            latest_rows = self._rows_at_timestamp(session, sector_type, latest_time)
            effective_limit = self._normalize_limit(limit, len(latest_rows))
            ranked_sector_names = [
                row.sector_name
                for row in sorted(latest_rows, key=lambda row: self._metric_value(row, metric), reverse=True)[:effective_limit]
            ]
            ranked_sector_names = self._merge_included(ranked_sector_names, include_sector_names or [])
            series = [
                self._build_daily_history_series(
                    session, sector_type=sector_type, sector_name=sector_name, metric=metric, lookback_days=lookback_days
                )
                for sector_name in ranked_sector_names
            ]
        else:
            rows = self._rows_for_lookback(session, sector_type, lookback_days, trading_date=trading_date)
            if not rows:
                return {"updated_at": None, "metric": metric, "granularity": granularity, "series": []}

            latest_time = max(row.captured_at for row in rows)
            latest_rows = [row for row in rows if row.captured_at == latest_time]
            effective_limit = self._normalize_limit(limit, len(latest_rows))
            ranked_sector_names = [
                row.sector_name
                for row in sorted(latest_rows, key=lambda row: self._metric_value(row, metric), reverse=True)[:effective_limit]
            ]
            ranked_sector_names = self._merge_included(ranked_sector_names, include_sector_names or [])
            series = [
                self._build_series(
                    [row for row in rows if row.sector_name == sector_name],
                    sector_name=sector_name,
                    metric=metric,
                    granularity=granularity,
                )
                for sector_name in ranked_sector_names
            ]
        return {
            "updated_at": latest_time.isoformat(),
            "metric": metric,
            "granularity": granularity,
            "series": series,
        }

    def get_sector_history(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        metric: str,
        granularity: str,
        lookback_days: int,
        trading_date: date | None = None,
    ) -> dict:
        if granularity == "day":
            return self._build_daily_history_series(
                session, sector_type=sector_type, sector_name=sector_name, metric=metric, lookback_days=lookback_days
            )
        rows = [
            row
            for row in self._rows_for_lookback(session, sector_type, lookback_days, trading_date=trading_date)
            if row.sector_name == sector_name
        ]
        return self._build_series(rows, sector_name=sector_name, metric=metric, granularity=granularity)

    def get_sector_snapshot(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        metric: str = "net_strength",
        trading_date: date | None = None,
    ) -> dict | None:
        rows = list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.sector_name == sector_name)
                .order_by(FundFlowSnapshot.captured_at.desc())
            )
        )
        if trading_date is not None:
            rows = [row for row in rows if row.captured_at.date() == trading_date]
        row = rows[0] if rows else None
        if row is None:
            return None
        return self._snapshot_to_dict(row, metric)

    def get_alerts(
        self,
        session: Session,
        sector_type: str,
        metric: str,
        limit: int = 10,
        trading_date: date | None = None,
    ) -> dict:
        timestamps = self._latest_two_timestamps(session, sector_type, trading_date=trading_date)
        if len(timestamps) < 2:
            return {"updated_at": timestamps[0].isoformat() if timestamps else None, "items": []}

        latest_rows = self._rows_at_timestamp(session, sector_type, timestamps[0])
        previous_rows = self._rows_at_timestamp(session, sector_type, timestamps[1])
        previous_by_name = {row.sector_name: row for row in previous_rows}
        latest_rank = self._rank_map(latest_rows, metric)
        previous_rank = self._rank_map(previous_rows, metric)

        items = []
        for row in latest_rows:
            previous = previous_by_name.get(row.sector_name)
            current_value = self._metric_value(row, metric)
            previous_value = self._metric_value(previous, metric) if previous else 0.0
            delta_value = round(current_value - previous_value, 6)
            rank_change = previous_rank.get(row.sector_name, len(previous_rank) + 1) - latest_rank[row.sector_name]
            items.append(
                {
                    "sector_name": row.sector_name,
                    "current_value": current_value,
                    "delta_value": delta_value,
                    "rank_change": rank_change,
                    "net_amount": row.net_amount,
                }
            )

        items.sort(key=lambda item: (abs(item["delta_value"]), abs(item["rank_change"])), reverse=True)
        return {
            "updated_at": timestamps[0].isoformat(),
            "metric": metric,
            "items": items[: self._normalize_limit(limit, len(items))],
        }

    def get_available_trading_dates(self, session: Session, sector_type: str) -> list[str]:
        rows = list(
            session.scalars(
                select(FundFlowSnapshot.captured_at)
                .where(FundFlowSnapshot.sector_type == sector_type)
                .order_by(FundFlowSnapshot.captured_at.desc())
            )
        )
        return [item.isoformat() for item in sorted({row.date() for row in rows}, reverse=True)]

    def get_sector_names(self, session: Session, sector_type: str, trading_date: date | None = None) -> list[str]:
        latest_time = self._latest_timestamp(session, sector_type, trading_date=trading_date)
        if latest_time is None:
            return []
        return [row.sector_name for row in self._rows_at_timestamp(session, sector_type, latest_time)]

    def _build_series(self, rows: list[FundFlowSnapshot], sector_name: str, metric: str, granularity: str) -> dict:
        ordered_rows = sorted(rows, key=lambda row: row.captured_at)
        points = [
            {
                "label": row.captured_at.strftime("%Y-%m-%d %H:%M"),
                "captured_at": row.captured_at.isoformat(),
                "value": self._metric_value(row, metric),
                "net_amount": row.net_amount,
                "inflow": row.inflow,
                "outflow": row.outflow,
            }
            for row in ordered_rows
        ]
        return {"sector_name": sector_name, "metric": metric, "granularity": granularity, "points": points}

    def _build_daily_history_series(
        self, session: Session, sector_type: str, sector_name: str, metric: str, lookback_days: int
    ) -> dict:
        rows = list(
            session.scalars(
                select(FundFlowDailyHistory)
                .where(FundFlowDailyHistory.sector_type == sector_type, FundFlowDailyHistory.sector_name == sector_name)
                .order_by(FundFlowDailyHistory.trading_date.asc())
            )
        )
        rows = rows[-lookback_days:]
        points = [
            {
                "label": row.trading_date.isoformat(),
                "captured_at": row.trading_date.isoformat(),
                "value": self._daily_metric_value(row, metric),
                "net_amount": row.main_net_amount,
            }
            for row in rows
        ]
        return {"sector_name": sector_name, "metric": metric, "granularity": "day", "points": points}

    @staticmethod
    def _merge_included(base_names: list[str], include_names: list[str]) -> list[str]:
        merged = list(base_names)
        for name in include_names:
            if name and name not in merged:
                merged.append(name)
        return merged

    def _rows_for_lookback(
        self,
        session: Session,
        sector_type: str,
        lookback_days: int,
        trading_date: date | None = None,
    ) -> list[FundFlowSnapshot]:
        all_rows = list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(FundFlowSnapshot.sector_type == sector_type)
                .order_by(FundFlowSnapshot.captured_at.asc())
            )
        )
        if trading_date is not None:
            return [row for row in all_rows if row.captured_at.date() == trading_date]
        unique_days = sorted({row.captured_at.date() for row in all_rows})
        selected_days = set(unique_days[-lookback_days:])
        return [row for row in all_rows if row.captured_at.date() in selected_days]

    def _rows_at_timestamp(self, session: Session, sector_type: str, captured_at: datetime) -> list[FundFlowSnapshot]:
        return list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.captured_at == captured_at)
                .order_by(FundFlowSnapshot.sector_name.asc())
            )
        )

    def _latest_timestamp(self, session: Session, sector_type: str, trading_date: date | None = None) -> datetime | None:
        timestamps = list(
            session.scalars(
                select(FundFlowSnapshot.captured_at)
                .where(FundFlowSnapshot.sector_type == sector_type)
                .order_by(FundFlowSnapshot.captured_at.desc())
            )
        )
        if trading_date is not None:
            timestamps = [timestamp for timestamp in timestamps if timestamp.date() == trading_date]
        return timestamps[0] if timestamps else None

    def _latest_two_timestamps(self, session: Session, sector_type: str, trading_date: date | None = None) -> list[datetime]:
        timestamps = list(
            session.scalars(
                select(FundFlowSnapshot.captured_at)
                .where(FundFlowSnapshot.sector_type == sector_type)
                .distinct()
                .order_by(FundFlowSnapshot.captured_at.desc())
            )
        )
        if trading_date is not None:
            timestamps = [timestamp for timestamp in timestamps if timestamp.date() == trading_date]
        return timestamps[:2]

    def _rank_map(self, rows: Iterable[FundFlowSnapshot], metric: str) -> dict[str, int]:
        ranked = sorted(rows, key=lambda row: self._metric_value(row, metric), reverse=True)
        return {row.sector_name: index + 1 for index, row in enumerate(ranked)}

    def _snapshot_to_dict(self, row: FundFlowSnapshot, metric: str) -> dict:
        return {
            "sector_type": row.sector_type,
            "sector_name": row.sector_name,
            "captured_at": row.captured_at.isoformat(),
            "sector_index": row.sector_index,
            "change_percent": row.change_percent,
            "inflow": row.inflow,
            "outflow": row.outflow,
            "net_amount": row.net_amount,
            "net_strength": self._metric_value(row, "net_strength"),
            "metric": metric,
            "metric_value": self._metric_value(row, metric),
            "company_count": row.company_count,
            "leading_stock": row.leading_stock,
            "leading_stock_change": row.leading_stock_change,
            "leading_stock_price": row.leading_stock_price,
        }

    @staticmethod
    def _metric_value(row: FundFlowSnapshot | None, metric: str) -> float:
        if row is None:
            return 0.0
        if metric == "net_amount":
            return float(row.net_amount or 0.0)
        inflow = float(row.inflow or 0.0)
        outflow = float(row.outflow or 0.0)
        denominator = inflow + outflow
        if denominator == 0:
            return 0.0
        return round(float(row.net_amount or 0.0) / denominator, 6)

    @staticmethod
    def _daily_metric_value(row: FundFlowDailyHistory, metric: str) -> float:
        if metric == "net_amount":
            return float(row.main_net_amount or 0.0)
        return float(row.main_net_ratio or 0.0)

    @staticmethod
    def _normalize_limit(limit: int, total: int) -> int:
        if total <= 0:
            return 0
        if limit <= 0:
            return total
        return min(limit, total)
