from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

import pandas as pd
from sqlalchemy.orm import Session

from app.models import FundFlowSnapshot
from app.services.dashboard import DashboardService
from app.services.limit_up import LimitUpService
from app.services.market_time import is_trading_time
from app.services.realtime_cache import RealtimeCacheService


class HomeDashboardService:
    INDEX_TARGETS = (
        ("sh000001", "上证指数"),
        ("sz399001", "深证成指"),
        ("sz399006", "创业板指"),
    )

    def __init__(
        self,
        *,
        gateway: Any,
        dashboard: DashboardService,
        limit_up: LimitUpService,
        realtime_cache: RealtimeCacheService,
        now_provider: Callable[[], datetime],
        market_temperature: Any | None = None,
        market_signal: Any | None = None,
    ) -> None:
        self.gateway = gateway
        self.dashboard = dashboard
        self.limit_up = limit_up
        self.realtime_cache = realtime_cache
        self.now_provider = now_provider
        self.market_temperature = market_temperature
        self.market_signal = market_signal

    def get_market_overview(self, session: Session | None = None) -> dict:
        spot = self._safe_frame(self.gateway.fetch_market_index_spot)
        breadth = self._safe_frame(self.gateway.fetch_market_breadth)
        breadth_records = breadth.to_dict(orient="records")
        breadth_map = {str(item.get("item", "")): item.get("value") for item in breadth_records}

        indices = []
        index_sources: list[dict[str, Any]] = []
        for symbol, fallback_name in self.INDEX_TARGETS:
            row = self._find_index_row(spot, symbol)
            history = self._safe_frame(lambda symbol=symbol: self.gateway.fetch_market_index_history(symbol=symbol, days=20))
            source_status = self._merge_source_snapshots(
                self._gateway_source(f"market_index_history:{symbol}"),
                self._gateway_source("market_index_spot"),
            )
            points = [
                {
                    "label": self._serialize_date(item.get("date")),
                    "value": self._to_float(item.get("close")),
                }
                for item in history.to_dict(orient="records")
            ]
            indices.append(
                {
                    "symbol": symbol,
                    "name": self._row_value(row, "name", 1, fallback_name),
                    "price": self._to_float(self._row_value(row, "price", 2)),
                    "change_amount": self._to_float(self._row_value(row, "change_amount", 3)),
                    "change_percent": self._to_float(self._row_value(row, "change_percent", 4)),
                    "turnover": self._to_float(self._row_value(row, "turnover", 5)),
                    "points": points,
                    "source_status": source_status,
                }
            )
            index_sources.append(source_status)

        updated_at = self._parse_datetime(breadth_map.get("updated_at") or self._breadth_value(breadth_records, 6))
        market_turnover = self._to_float(breadth_map.get("market_turnover") or self._breadth_value(breadth_records, 7))
        if market_turnover is None:
            market_turnover = sum(
                item["turnover"] for item in indices[:2] if isinstance(item.get("turnover"), (int, float)) and item["turnover"] is not None
            )
            if market_turnover == 0:
                market_turnover = None

        up_count = self._to_float(breadth_map.get("up_count"))
        down_count = self._to_float(breadth_map.get("down_count"))
        flat_count = self._to_float(breadth_map.get("flat_count"))
        limit_up_count = self._to_float(breadth_map.get("limit_up_count"))
        limit_down_count = self._to_float(breadth_map.get("limit_down_count"))
        market_activity = self._parse_percent(breadth_map.get("market_activity"))

        if up_count is None:
            up_count = self._to_float(self._breadth_value(breadth_records, 0))
        if down_count is None:
            down_count = self._to_float(self._breadth_value(breadth_records, 1))
        if flat_count is None:
            flat_count = self._to_float(self._breadth_value(breadth_records, 2))
        if limit_up_count is None:
            limit_up_count = self._to_float(self._breadth_value(breadth_records, 3))
        if limit_down_count is None:
            limit_down_count = self._to_float(self._breadth_value(breadth_records, 4))
        if market_activity is None:
            market_activity = self._parse_percent(self._breadth_value(breadth_records, 5))

        breadth_source = self._gateway_source("market_breadth")
        degraded_fields = sorted({*self._collect_degraded_fields(index_sources), *breadth_source.get("degraded_fields", [])})

        return {
            "updated_at": updated_at.isoformat() if updated_at else None,
            "indices": indices,
            "breadth": {
                "up_count": int(up_count or 0),
                "down_count": int(down_count or 0),
                "flat_count": int(flat_count or 0),
                "limit_up_count": int(limit_up_count or 0),
                "limit_down_count": int(limit_down_count or 0),
                "up_down_ratio": self._compute_ratio(up_count, down_count),
                "market_activity": market_activity,
                "market_turnover": market_turnover,
            },
            "source_summary": {
                "indices": self._combine_sources(index_sources),
                "breadth": breadth_source,
                "degraded_fields": degraded_fields,
            },
        }

    def get_system_summary(self, session: Session) -> dict:
        sector_snapshot = self.dashboard.get_latest_rankings(
            session,
            sector_type="industry",
            limit=10,
            metric="net_amount",
        )
        limit_summary = self.limit_up.get_summary(self.now_provider().date(), market_scope="all")
        watched_count = len(self.realtime_cache.list_watched_sectors(session))

        leaders = sector_snapshot.get("leaders", [])
        laggards = sector_snapshot.get("laggards", [])
        strongest = leaders[0] if leaders else None
        weakest = laggards[0] if laggards else None
        temperature = (
            self.market_temperature.get_temperature(self.now_provider().date(), market_scope="all")
            if self.market_temperature is not None
            else None
        )
        action_priority = (
            self.market_signal.build_action_priority(session, trading_date=self.now_provider().date())
            if self.market_signal is not None
            else {"primary_workspace": "sector-monitor", "title": "先看板块资金", "reason": "等待行动建议", "href": "/sector-monitor"}
        )
        alert_summary = (
            self.market_signal.build_home_alert_summary(session, trading_date=self.now_provider().date())
            if self.market_signal is not None
            else {"title": "暂无预警摘要", "count": 0, "high_priority_count": 0, "action_url": "/alerts"}
        )
        opportunity_summary = (
            self.market_signal.build_home_opportunity_summary(session, trading_date=self.now_provider().date())
            if self.market_signal is not None
            else {"title": "暂无候选摘要", "mode": "strong-sector", "count": 0, "action_url": "/opportunity-pool"}
        )

        return {
            "updated_at": sector_snapshot.get("updated_at") or self.now_provider().isoformat(),
            "sector_monitor": {
                "current_sector_type": "industry",
                "strongest_inflow_sector": strongest["sector_name"] if strongest else None,
                "strongest_inflow_amount": strongest["net_amount"] if strongest else None,
                "weakest_outflow_sector": weakest["sector_name"] if weakest else None,
                "weakest_outflow_amount": weakest["net_amount"] if weakest else None,
                "last_snapshot_at": sector_snapshot.get("updated_at"),
                "watched_sector_count": watched_count,
            },
            "limit_up_ladder": {
                "highest_board": limit_summary.get("highest_board"),
                "high_board_count": limit_summary.get("high_board_count"),
                "limit_up_count": limit_summary.get("limit_up_count"),
                "first_board_count": limit_summary.get("first_board_count"),
                "broken_count": limit_summary.get("broken_count"),
                "promotion_rate": limit_summary.get("promotion_rate"),
                "trading_date": limit_summary.get("trading_date"),
                "market_temperature": {
                    "temperature_score": temperature.get("temperature_score") if temperature else None,
                    "temperature_band": temperature.get("temperature_band") if temperature else None,
                    "summary_text": temperature.get("summary_text") if temperature else None,
                    "risk_flag": temperature.get("risk_flag") if temperature else None,
                },
            },
            "action_priority": action_priority,
            "alert_summary": alert_summary,
            "opportunity_summary": opportunity_summary,
            "source_summary": {
                "sector_monitor": {
                    "source_label": "cache",
                    "updated_at": sector_snapshot.get("updated_at"),
                    "fallback_used": False,
                    "degraded_fields": [] if strongest or weakest else ["sector_rankings"],
                },
                "limit_up_ladder": {
                    "source_label": "akshare",
                    "updated_at": self._serialize_date(limit_summary.get("trading_date")),
                    "fallback_used": False,
                    "degraded_fields": [] if limit_summary else ["limit_up_summary"],
                },
            },
        }

    def get_status(self, session: Session) -> dict:
        now = self.now_provider()
        latest_snapshot = session.query(FundFlowSnapshot).order_by(FundFlowSnapshot.captured_at.desc()).first()
        limit_available = self._limit_up_available(now.date())
        sector_available = latest_snapshot is not None
        return {
            "market_open": is_trading_time(now),
            "updated_at": now.isoformat(),
            "server_time": now.isoformat(),
            "subsystems": {
                "sector_monitor": sector_available,
                "limit_up_ladder": limit_available,
            },
        }

    def _limit_up_available(self, trading_date: date) -> bool:
        try:
            summary = self.limit_up.get_summary(trading_date, market_scope="all")
        except Exception:
            return False
        return bool(summary)

    @staticmethod
    def _safe_frame(fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        try:
            frame = fetcher()
        except Exception:
            return pd.DataFrame()
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()

    @staticmethod
    def _find_index_row(frame: pd.DataFrame, symbol: str) -> dict[str, Any]:
        if frame.empty:
            return {}
        key = "symbol" if "symbol" in frame.columns else frame.columns[0]
        matched = frame[frame[key].astype(str) == symbol]
        if matched.empty:
            return {}
        return matched.iloc[0].to_dict()

    @staticmethod
    def _row_value(row: dict[str, Any], key: str, index: int, default: Any = None) -> Any:
        if not row:
            return default
        if key in row:
            return row.get(key, default)
        values = list(row.values())
        return values[index] if index < len(values) else default

    @staticmethod
    def _breadth_value(records: list[dict[str, Any]], index: int) -> Any:
        if index >= len(records):
            return None
        return records[index].get("value")

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, "", "--"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).replace(",", "").replace("%", "").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @classmethod
    def _compute_ratio(cls, up_value: Any, down_value: Any) -> float | None:
        up = cls._to_float(up_value)
        down = cls._to_float(down_value)
        if up is None or down in (None, 0):
            return None
        return round(up / down, 4)

    @classmethod
    def _parse_percent(cls, value: Any) -> float | None:
        number = cls._to_float(value)
        return round(number, 2) if number is not None else None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value in (None, "", "--"):
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _serialize_date(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        text = str(value).strip()
        return text or None

    def _gateway_source(self, key: str) -> dict[str, Any]:
        getter = getattr(self.gateway, "get_source_snapshot", None)
        if callable(getter):
            source = getter(key) or {}
            return {
                "source_label": source.get("source_label", "akshare"),
                "updated_at": source.get("updated_at"),
                "fallback_used": bool(source.get("fallback_used", False)),
                "degraded_fields": list(source.get("degraded_fields", [])),
            }
        return {
            "source_label": "akshare",
            "updated_at": None,
            "fallback_used": False,
            "degraded_fields": [],
        }

    @classmethod
    def _merge_source_snapshots(cls, primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
        degraded_fields = sorted({*(primary.get("degraded_fields", [])), *(secondary.get("degraded_fields", []))})
        source_label = primary.get("source_label") or secondary.get("source_label") or "akshare"
        if primary.get("fallback_used"):
            source_label = primary.get("source_label", source_label)
        elif secondary.get("fallback_used"):
            source_label = secondary.get("source_label", source_label)
        return {
            "source_label": source_label,
            "updated_at": primary.get("updated_at") or secondary.get("updated_at"),
            "fallback_used": bool(primary.get("fallback_used") or secondary.get("fallback_used")),
            "degraded_fields": degraded_fields,
        }

    @classmethod
    def _combine_sources(cls, sources: list[dict[str, Any]]) -> dict[str, Any]:
        if not sources:
            return {
                "source_label": "akshare",
                "updated_at": None,
                "fallback_used": False,
                "degraded_fields": [],
            }
        fallback_source = next((item.get("source_label") for item in sources if item.get("fallback_used")), None)
        updated_at = next((item.get("updated_at") for item in sources if item.get("updated_at")), None)
        return {
            "source_label": fallback_source or sources[0].get("source_label", "akshare"),
            "updated_at": updated_at,
            "fallback_used": any(item.get("fallback_used") for item in sources),
            "degraded_fields": cls._collect_degraded_fields(sources),
        }

    @staticmethod
    def _collect_degraded_fields(sources: list[dict[str, Any]]) -> list[str]:
        degraded: set[str] = set()
        for item in sources:
            degraded.update(item.get("degraded_fields", []))
        return sorted(degraded)
