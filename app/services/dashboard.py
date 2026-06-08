from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import FundFlowDailyHistory, FundFlowSnapshot


class DashboardService:
    def __init__(self, gateway: Any | None = None) -> None:
        self.gateway = gateway

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
        rank_view: str = "leaders",
        include_sector_names: list[str] | None = None,
        trading_date: date | None = None,
    ) -> dict:
        include_sector_names = include_sector_names or []
        descending = rank_view != "laggards"
        if granularity == "day":
            latest_time = self._latest_timestamp(session, sector_type)
            if latest_time is None:
                return {
                    "updated_at": None,
                    "metric": metric,
                    "granularity": granularity,
                    "series": [],
                    "invalid_watchlist": include_sector_names,
                    "missing_labels_count": 0,
                }

            latest_rows = self._rows_at_timestamp(session, sector_type, latest_time)
            effective_limit = self._normalize_limit(limit, len(latest_rows))
            ranked_sector_names = [
                row.sector_name
                for row in sorted(latest_rows, key=lambda row: self._metric_value(row, metric), reverse=descending)[:effective_limit]
            ]
            resolved = self._resolve_included_sector_names(session, sector_type, latest_rows, include_sector_names)
            ranked_sector_names = self._merge_included(ranked_sector_names, resolved["valid"])
            series = [
                self._build_daily_history_series(
                    session,
                    sector_type=sector_type,
                    sector_name=sector_name,
                    metric=metric,
                    lookback_days=lookback_days,
                )
                for sector_name in ranked_sector_names
            ]
            return {
                "updated_at": latest_time.isoformat(),
                "metric": metric,
                "granularity": granularity,
                "series": series,
                "invalid_watchlist": resolved["invalid"],
                "resolved_watchlist": resolved["mapped"],
                "missing_labels_count": 0,
            }

        target_date = trading_date or self._latest_trading_date(session, sector_type)
        if target_date is None:
            return {
                "updated_at": None,
                "metric": metric,
                "granularity": granularity,
                "series": [],
                "invalid_watchlist": include_sector_names,
                "missing_labels_count": 0,
            }

        # For minute granularity, check if the target date has sufficient data.
        # If the latest date has very few timestamps (e.g., partial day),
        # fall back to the previous trading date with more complete data.
        if granularity == "minute" and trading_date is None:
            target_date = self._resolve_minute_trading_date(session, sector_type, target_date)

        latest_time = self._latest_timestamp(session, sector_type, trading_date=target_date)
        if latest_time is None:
            return {
                "updated_at": None,
                "metric": metric,
                "granularity": granularity,
                "series": [],
                "invalid_watchlist": include_sector_names,
                "missing_labels_count": 0,
            }
        latest_rows = self._rows_at_timestamp(session, sector_type, latest_time)
        effective_limit = self._normalize_limit(limit, len(latest_rows))
        ranked_sector_names = [
            row.sector_name
            for row in sorted(latest_rows, key=lambda row: self._metric_value(row, metric), reverse=descending)[:effective_limit]
        ]
        resolved = self._resolve_included_sector_names(session, sector_type, latest_rows, include_sector_names)
        ranked_sector_names = self._merge_included(ranked_sector_names, resolved["valid"])

        rows = self._rows_for_sector_names_on_date(
            session,
            sector_type=sector_type,
            sector_names=ranked_sector_names,
            trading_date=target_date,
        )
        timeline = self._build_minute_timeline(rows, target_date=target_date)
        series = [
            self._build_minute_series(
                [row for row in rows if row.sector_name == sector_name],
                sector_name=sector_name,
                metric=metric,
                timeline=timeline,
            )
            for sector_name in ranked_sector_names
        ]
        observed_labels = {row.captured_at.strftime("%Y-%m-%d %H:%M") for row in rows}
        missing_labels_count = max(len(timeline) - len(observed_labels), 0)
        return {
            "updated_at": latest_time.isoformat(),
            "metric": metric,
            "granularity": granularity,
            "series": series,
            "invalid_watchlist": resolved["invalid"],
            "resolved_watchlist": resolved["mapped"],
            "missing_labels_count": missing_labels_count,
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
        canonical_name = self._resolve_sector_name(session, sector_type, sector_name)
        if canonical_name is None:
            return {"sector_name": sector_name, "metric": metric, "granularity": granularity, "points": []}
        if granularity == "day":
            return self._build_daily_history_series(
                session,
                sector_type=sector_type,
                sector_name=canonical_name,
                metric=metric,
                lookback_days=lookback_days,
            )

        rows = self._sector_rows_for_lookback(
            session,
            sector_type=sector_type,
            sector_name=canonical_name,
            lookback_days=lookback_days,
            trading_date=trading_date,
        )
        if not rows:
            return {"sector_name": canonical_name, "metric": metric, "granularity": granularity, "points": []}
        timeline = self._build_minute_timeline(rows, target_date=trading_date or rows[-1].captured_at.date())
        return self._build_minute_series(rows, sector_name=canonical_name, metric=metric, timeline=timeline)

    def get_sector_snapshot(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        metric: str = "net_strength",
        trading_date: date | None = None,
    ) -> dict | None:
        canonical_name = self._resolve_sector_name(session, sector_type, sector_name)
        if canonical_name is None:
            return None
        stmt = (
            select(FundFlowSnapshot)
            .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.sector_name == canonical_name)
            .order_by(FundFlowSnapshot.captured_at.desc())
        )
        if trading_date is not None:
            start_at = datetime.combine(trading_date, time(0, 0))
            end_at = start_at + timedelta(days=1)
            stmt = stmt.where(FundFlowSnapshot.captured_at >= start_at, FundFlowSnapshot.captured_at < end_at)
        row = session.scalars(stmt).first()
        if row is None:
            return None
        return self._snapshot_to_dict(row, metric)

    def get_sector_workspace(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        metric: str,
        granularity: str,
        lookback_days: int,
        trading_date: date | None = None,
    ) -> dict:
        canonical_name = self._resolve_sector_name(session, sector_type, sector_name)
        resolved_trading_date = self._resolve_trading_date(session, sector_type, trading_date)
        effective_trading_date = resolved_trading_date
        detail = self.get_sector_snapshot(
            session,
            sector_type=sector_type,
            sector_name=sector_name,
            metric=metric,
            trading_date=effective_trading_date,
        )
        history = self.get_sector_history(
            session,
            sector_type=sector_type,
            sector_name=sector_name,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            trading_date=effective_trading_date,
        )
        source_status = "cache_hit"
        if trading_date is not None and resolved_trading_date is not None and resolved_trading_date != trading_date:
            source_status = "stale_cache"
        elif detail is None:
            source_status = "unavailable"
        return {
            "detail": detail,
            "history": history,
            "resolved_sector_name": canonical_name,
            "requested_sector_name": sector_name,
            "requested_trading_date": trading_date.isoformat() if trading_date else None,
            "resolved_trading_date": resolved_trading_date.isoformat() if resolved_trading_date else None,
            "source_status": source_status,
            "analysis_cache": {
                "detail_updated_at": detail["captured_at"] if detail else None,
                "history_points": len(history.get("points", [])) if history else 0,
                "fallback_reason": "latest_cached_trading_date" if source_status == "stale_cache" else None,
            },
            "structure": {"metrics": [], "notes": []},
            "cache_meta": {
                "requested_trading_date": trading_date.isoformat() if trading_date else None,
                "resolved_trading_date": resolved_trading_date.isoformat() if resolved_trading_date else None,
                "fallback_reason": "latest_cached_trading_date" if source_status == "stale_cache" else None,
            },
        }

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

    def get_monitor_signals(
        self,
        session: Session,
        sector_type: str,
        metric: str,
        limit: int = 10,
        trading_date: date | None = None,
    ) -> dict:
        target_date = trading_date or self._latest_trading_date(session, sector_type)
        if target_date is None:
            return {"updated_at": None, "metric": metric, "items": []}

        timestamps = self._recent_timestamps(session, sector_type=sector_type, trading_date=target_date, limit=8)
        rows = self._rows_at_timestamps(session, sector_type=sector_type, timestamps=timestamps)
        if not rows:
            return {"updated_at": None, "metric": metric, "items": []}

        by_sector: dict[str, list[FundFlowSnapshot]] = defaultdict(list)
        for row in rows:
            by_sector[row.sector_name].append(row)

        items = []
        latest_time = max(row.captured_at for row in rows)
        for sector_name, sector_rows in by_sector.items():
            ordered = sorted(sector_rows, key=lambda row: row.captured_at)
            latest = ordered[-1]
            latest_value = self._metric_value(latest, metric)
            previous_value = self._metric_value(ordered[-2], metric) if len(ordered) >= 2 else latest_value
            baseline_index = max(0, len(ordered) - 4)
            baseline_value = self._metric_value(ordered[baseline_index], metric)
            breadth = self._value_sign(latest_value) * len(ordered)
            items.append(
                {
                    "sector_name": sector_name,
                    "captured_at": latest.captured_at.isoformat(),
                    "metric_value": latest_value,
                    "acceleration_1": round(latest_value - previous_value, 6),
                    "acceleration_3": round(latest_value - baseline_value, 6),
                    "persistence": self._persistence_count(ordered, metric),
                    "divergence": self._divergence_label(latest, latest_value),
                    "change_percent": latest.change_percent,
                    "net_amount": latest.net_amount,
                    "breadth_proxy": breadth,
                }
            )

        items.sort(
            key=lambda item: (
                1 if item["divergence"] != "aligned" else 0,
                abs(item["acceleration_1"]),
                abs(item["acceleration_3"]),
                abs(item["metric_value"]),
            ),
            reverse=True,
        )
        return {
            "updated_at": latest_time.isoformat(),
            "metric": metric,
            "trading_date": target_date.isoformat(),
            "items": items[: self._normalize_limit(limit, len(items))],
        }

    def get_available_trading_dates(self, session: Session, sector_type: str) -> list[str]:
        rows = session.scalars(
            select(func.date(FundFlowSnapshot.captured_at))
            .where(FundFlowSnapshot.sector_type == sector_type)
            .distinct()
            .order_by(desc(func.date(FundFlowSnapshot.captured_at)))
        )
        return [str(row) for row in rows if row is not None]

    def get_sector_names(self, session: Session, sector_type: str, trading_date: date | None = None) -> list[str]:
        latest_time = self._latest_timestamp(session, sector_type, trading_date=trading_date)
        if latest_time is None:
            return []
        return [row.sector_name for row in self._rows_at_timestamp(session, sector_type, latest_time)]

    def resolve_sector_name(self, sector_type: str, sector_name: str) -> str | None:
        if self.gateway is None:
            return sector_name
        return self.gateway.resolve_sector_name(sector_type, sector_name)

    def _resolve_sector_name(self, session: Session, sector_type: str, sector_name: str) -> str | None:
        if self._sector_name_exists(session, sector_type, sector_name):
            return sector_name
        return self.resolve_sector_name(sector_type, sector_name)

    @staticmethod
    def _sector_name_exists(session: Session, sector_type: str, sector_name: str) -> bool:
        return (
            session.scalar(
                select(FundFlowSnapshot.sector_name)
                .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.sector_name == sector_name)
                .limit(1)
            )
            is not None
        )

    def _resolve_included_sector_names(
        self,
        session: Session,
        sector_type: str,
        latest_rows: list[FundFlowSnapshot],
        include_sector_names: list[str],
    ) -> dict[str, Any]:
        available_names = {row.sector_name for row in latest_rows}
        valid: list[str] = []
        invalid: list[str] = []
        mapped: dict[str, str] = {}
        for requested_name in include_sector_names:
            canonical_name = requested_name if requested_name in available_names else self.resolve_sector_name(sector_type, requested_name)
            if canonical_name and canonical_name in available_names:
                if canonical_name not in valid:
                    valid.append(canonical_name)
                mapped[requested_name] = canonical_name
            else:
                invalid.append(requested_name)
        return {"valid": valid, "invalid": invalid, "mapped": mapped}

    def _build_minute_series(
        self,
        rows: list[FundFlowSnapshot],
        sector_name: str,
        metric: str,
        timeline: list[datetime],
    ) -> dict:
        ordered_rows = sorted(rows, key=lambda row: row.captured_at)
        row_map = {row.captured_at.replace(second=0, microsecond=0): row for row in ordered_rows}
        first_row = ordered_rows[0] if ordered_rows else None
        baseline = self._metric_value(first_row, metric) if first_row is not None else 0.0
        points: list[dict] = []
        seen_first = False
        last_row: FundFlowSnapshot | None = None

        for timestamp in timeline:
            source_row = row_map.get(timestamp)
            if source_row is not None:
                last_row = source_row
                seen_first = True
            label = timestamp.strftime("%Y-%m-%d %H:%M")
            if not seen_first or last_row is None:
                points.append(
                    {
                        "label": label,
                        "captured_at": timestamp.isoformat(),
                        "value": None,
                        "net_amount": None,
                        "inflow": None,
                        "outflow": None,
                        "is_filled": False,
                    }
                )
                continue
            metric_value = self._metric_value(last_row, metric) - baseline
            points.append(
                {
                    "label": label,
                    "captured_at": timestamp.isoformat(),
                    "value": round(metric_value, 6),
                    "net_amount": last_row.net_amount,
                    "inflow": last_row.inflow,
                    "outflow": last_row.outflow,
                    "is_filled": source_row is None,
                }
            )

        return {
            "sector_name": sector_name,
            "metric": metric,
            "granularity": "minute",
            "points": points,
        }

    def _build_daily_history_series(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        metric: str,
        lookback_days: int,
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
        if trading_date is not None:
            start_at, end_at = self._date_bounds(trading_date)
            stmt = (
                select(FundFlowSnapshot)
                .where(
                    FundFlowSnapshot.sector_type == sector_type,
                    FundFlowSnapshot.captured_at >= start_at,
                    FundFlowSnapshot.captured_at < end_at,
                )
                .order_by(FundFlowSnapshot.captured_at.asc())
            )
            return list(session.scalars(stmt))

        selected_days = self._latest_trading_dates(session, sector_type, limit=lookback_days)
        if not selected_days:
            return []
        start_at = datetime.combine(selected_days[-1], time(0, 0))
        stmt = (
            select(FundFlowSnapshot)
            .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.captured_at >= start_at)
            .order_by(FundFlowSnapshot.captured_at.asc())
        )
        return [row for row in session.scalars(stmt) if row.captured_at.date() in set(selected_days)]

    def _sector_rows_for_lookback(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        lookback_days: int,
        trading_date: date | None = None,
    ) -> list[FundFlowSnapshot]:
        filters = [FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.sector_name == sector_name]
        if trading_date is not None:
            start_at, end_at = self._date_bounds(trading_date)
            filters.extend([FundFlowSnapshot.captured_at >= start_at, FundFlowSnapshot.captured_at < end_at])
        else:
            selected_days = self._latest_trading_dates(session, sector_type, limit=lookback_days)
            if not selected_days:
                return []
            filters.append(FundFlowSnapshot.captured_at >= datetime.combine(selected_days[-1], time(0, 0)))
        rows = list(session.scalars(select(FundFlowSnapshot).where(*filters).order_by(FundFlowSnapshot.captured_at.asc())))
        if trading_date is None:
            selected = set(selected_days)
            rows = [row for row in rows if row.captured_at.date() in selected]
        return rows

    def _rows_at_timestamp(self, session: Session, sector_type: str, captured_at: datetime) -> list[FundFlowSnapshot]:
        return list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.captured_at == captured_at)
                .order_by(FundFlowSnapshot.sector_name.asc())
            )
        )

    def _rows_at_timestamps(self, session: Session, sector_type: str, timestamps: list[datetime]) -> list[FundFlowSnapshot]:
        if not timestamps:
            return []
        return list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(FundFlowSnapshot.sector_type == sector_type, FundFlowSnapshot.captured_at.in_(timestamps))
                .order_by(FundFlowSnapshot.captured_at.asc(), FundFlowSnapshot.sector_name.asc())
            )
        )

    def _rows_for_sector_names_on_date(
        self,
        session: Session,
        sector_type: str,
        sector_names: list[str],
        trading_date: date,
    ) -> list[FundFlowSnapshot]:
        if not sector_names:
            return []
        start_at, end_at = self._date_bounds(trading_date)
        return list(
            session.scalars(
                select(FundFlowSnapshot)
                .where(
                    FundFlowSnapshot.sector_type == sector_type,
                    FundFlowSnapshot.sector_name.in_(sector_names),
                    FundFlowSnapshot.captured_at >= start_at,
                    FundFlowSnapshot.captured_at < end_at,
                )
                .order_by(FundFlowSnapshot.captured_at.asc(), FundFlowSnapshot.sector_name.asc())
            )
        )

    def _latest_trading_date(self, session: Session, sector_type: str) -> date | None:
        latest_time = self._latest_timestamp(session, sector_type)
        return latest_time.date() if latest_time is not None else None

    def _latest_timestamp(self, session: Session, sector_type: str, trading_date: date | None = None) -> datetime | None:
        if trading_date is not None:
            start_at, end_at = self._date_bounds(trading_date)
            return session.scalar(
                select(FundFlowSnapshot.captured_at)
                .where(
                    FundFlowSnapshot.sector_type == sector_type,
                    FundFlowSnapshot.captured_at >= start_at,
                    FundFlowSnapshot.captured_at < end_at,
                )
                .order_by(desc(FundFlowSnapshot.captured_at))
                .limit(1)
            )
        return session.scalar(
            select(FundFlowSnapshot.captured_at)
            .where(FundFlowSnapshot.sector_type == sector_type)
            .order_by(desc(FundFlowSnapshot.captured_at))
            .limit(1)
        )

    def _latest_two_timestamps(self, session: Session, sector_type: str, trading_date: date | None = None) -> list[datetime]:
        stmt = (
            select(FundFlowSnapshot.captured_at)
            .where(FundFlowSnapshot.sector_type == sector_type)
            .distinct()
            .order_by(desc(FundFlowSnapshot.captured_at))
        )
        if trading_date is not None:
            start_at, end_at = self._date_bounds(trading_date)
            stmt = stmt.where(FundFlowSnapshot.captured_at >= start_at, FundFlowSnapshot.captured_at < end_at)
        return list(session.scalars(stmt.limit(2)))

    def _recent_timestamps(self, session: Session, sector_type: str, trading_date: date, limit: int) -> list[datetime]:
        start_at, end_at = self._date_bounds(trading_date)
        return list(
            reversed(
                list(
                    session.scalars(
                        select(FundFlowSnapshot.captured_at)
                        .where(
                            FundFlowSnapshot.sector_type == sector_type,
                            FundFlowSnapshot.captured_at >= start_at,
                            FundFlowSnapshot.captured_at < end_at,
                        )
                        .distinct()
                        .order_by(desc(FundFlowSnapshot.captured_at))
                        .limit(max(limit, 1))
                    )
                )
            )
        )

    def _resolve_trading_date(self, session: Session, sector_type: str, trading_date: date | None) -> date | None:
        if trading_date is not None and self._latest_timestamp(session, sector_type, trading_date=trading_date) is not None:
            return trading_date
        if trading_date is None:
            latest = self._latest_timestamp(session, sector_type)
            return latest.date() if latest is not None else None
        dates = self._latest_trading_dates(session, sector_type, limit=1)
        return dates[0] if dates else None

    def _latest_trading_dates(self, session: Session, sector_type: str, limit: int) -> list[date]:
        rows = session.scalars(
            select(func.date(FundFlowSnapshot.captured_at))
            .where(FundFlowSnapshot.sector_type == sector_type)
            .distinct()
            .order_by(desc(func.date(FundFlowSnapshot.captured_at)))
            .limit(max(limit, 1))
        )
        result: list[date] = []
        for row in rows:
            if row is None:
                continue
            result.append(row if isinstance(row, date) else date.fromisoformat(str(row)))
        return result

    def _resolve_minute_trading_date(self, session: Session, sector_type: str, candidate_date: date) -> date:
        """For minute-level comparisons, fall back to a previous date if the candidate has sparse data."""
        # Count distinct timestamps on the candidate date
        start_at, end_at = self._date_bounds(candidate_date)
        timestamp_count = session.scalar(
            select(func.count(func.distinct(FundFlowSnapshot.captured_at)))
            .where(
                FundFlowSnapshot.sector_type == sector_type,
                FundFlowSnapshot.captured_at >= start_at,
                FundFlowSnapshot.captured_at < end_at,
            )
        ) or 0
        # If fewer than 100 distinct timestamps (roughly 40% of a full trading day),
        # try the previous trading date
        if timestamp_count >= 100:
            return candidate_date
        previous_dates = self._latest_trading_dates(session, sector_type, limit=2)
        if len(previous_dates) >= 2:
            return previous_dates[1]
        return candidate_date

    @staticmethod
    def _date_bounds(trading_date: date) -> tuple[datetime, datetime]:
        start_at = datetime.combine(trading_date, time(0, 0))
        return start_at, start_at + timedelta(days=1)

    def _build_minute_timeline(self, rows: list[FundFlowSnapshot], target_date: date) -> list[datetime]:
        if not rows:
            return []
        last_timestamp = max(row.captured_at for row in rows).replace(second=0, microsecond=0)
        session_end = datetime.combine(target_date, time(15, 0))
        end_at = min(last_timestamp, session_end) if target_date == last_timestamp.date() and last_timestamp.time() < time(15, 0) else session_end
        labels: list[datetime] = []
        for start_time, end_time in ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))):
            current = datetime.combine(target_date, start_time)
            end = datetime.combine(target_date, end_time)
            while current <= end and current <= end_at:
                labels.append(current)
                current += timedelta(minutes=1)
        return labels

    def _persistence_count(self, rows: list[FundFlowSnapshot], metric: str) -> int:
        if not rows:
            return 0
        latest_sign = self._value_sign(self._metric_value(rows[-1], metric))
        if latest_sign == 0:
            return 0
        count = 0
        for row in reversed(rows):
            if self._value_sign(self._metric_value(row, metric)) != latest_sign:
                break
            count += 1
        return count

    @staticmethod
    def _divergence_label(row: FundFlowSnapshot, metric_value: float) -> str:
        flow_sign = DashboardService._value_sign(metric_value)
        price_sign = DashboardService._value_sign(float(row.change_percent or 0.0))
        if flow_sign > 0 and price_sign < 0:
            return "bullish_flow_vs_price"
        if flow_sign < 0 and price_sign > 0:
            return "bearish_flow_vs_price"
        return "aligned"

    @staticmethod
    def _value_sign(value: float) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

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
