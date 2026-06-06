from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Callable

from sqlalchemy.orm import Session


@dataclass
class CacheEntry:
    expires_at: datetime
    payload: dict[str, Any]


class PagePayloadService:
    def __init__(
        self,
        *,
        dashboard: Any,
        home_dashboard: Any,
        history_cache: Any,
        market_signal: Any,
        limit_up: Any,
        realtime_cache: Any,
        workspace: Any,
        ai_center: Any,
        now_provider: Callable[[], datetime],
        gateway: Any,
        ttl_seconds: int = 180,
    ) -> None:
        self.dashboard = dashboard
        self.home_dashboard = home_dashboard
        self.history_cache = history_cache
        self.market_signal = market_signal
        self.limit_up = limit_up
        self.realtime_cache = realtime_cache
        self.workspace = workspace
        self.ai_center = ai_center
        self.now_provider = now_provider
        self.gateway = gateway
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get_page_payload(self, page_name: str, session: Session) -> dict[str, Any]:
        builders = {
            "home": self.build_home_page,
            "alerts": self.build_alerts_page,
            "sector-monitor": self.build_sector_monitor_page,
            "limit-up-ladder": self.build_limit_up_page,
            "opportunity-pool": self.build_opportunity_page,
            "workspace": self.build_workspace_page,
            "ai-center": self.build_ai_center_page,
        }
        builder = builders.get(page_name)
        if builder is None:
            raise KeyError(page_name)
        return self._get_cached(page_name, lambda: builder(session))

    def _get_cached(self, cache_key: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        now = self.now_provider()
        with self._lock:
            entry = self._cache.get(cache_key)
            if entry is not None and entry.expires_at > now:
                return entry.payload
        payload = builder()
        with self._lock:
            self._cache[cache_key] = CacheEntry(
                expires_at=now + timedelta(seconds=self.ttl_seconds),
                payload=payload,
            )
        return payload

    def build_home_page(self, session: Session) -> dict[str, Any]:
        status = self.home_dashboard.get_status(session)
        market_overview = self.home_dashboard.get_market_overview(session)
        system_summary = self.home_dashboard.get_system_summary(session)
        return self._wrap(
            "home",
            {
                "status": status,
                "market_overview": market_overview,
                "system_summary": system_summary,
            },
            updated_candidates=[
                status.get("updated_at"),
                market_overview.get("updated_at"),
                system_summary.get("updated_at"),
            ],
        )

    def build_alerts_page(self, session: Session) -> dict[str, Any]:
        summary = self.market_signal.get_alerts_summary(session)
        feed = self.market_signal.get_alerts_feed(session, limit=20)
        return self._wrap(
            "alerts",
            {
                "filters": {
                    "signal_type": "all",
                    "strength": "all",
                    "time_window": "today",
                },
                "summary": summary,
                "feed": feed,
            },
            updated_candidates=[summary.get("updated_at"), feed.get("updated_at")],
        )

    def build_sector_monitor_page(self, session: Session) -> dict[str, Any]:
        overview = self.dashboard.get_latest_rankings(session, sector_type="industry", limit=8, metric="net_strength")
        status = {
            "scheduler_enabled": True,
            "market_open": self.home_dashboard.get_status(session).get("market_open"),
            "last_snapshot_at": overview.get("updated_at"),
            "server_time": self.now_provider().isoformat(),
            "watched_sector_count": len(self.realtime_cache.list_watched_sectors(session)),
        }
        selected_sector = (overview.get("leaders") or [{}])[0].get("sector_name")
        workspace_payload = (
            self.dashboard.get_sector_workspace(
                session=session,
                sector_type="industry",
                sector_name=selected_sector,
                metric="net_strength",
                granularity="minute",
                lookback_days=1,
                trading_date=None,
            )
            if selected_sector
            else {"detail": None, "resolved_sector_name": None}
        )
        watchlist = {"items": self.realtime_cache.list_watched_sectors(session)}
        sector_catalog = {
            "industry": self.gateway.fetch_sector_catalog("industry") or self.dashboard.get_sector_names(session, sector_type="industry"),
            "concept": self.gateway.fetch_sector_catalog("concept") or self.dashboard.get_sector_names(session, sector_type="concept"),
        }
        trading_dates = {
            "industry": self.dashboard.get_available_trading_dates(session, sector_type="industry"),
            "concept": self.dashboard.get_available_trading_dates(session, sector_type="concept"),
        }
        comparison = self.dashboard.get_comparison_series(
            session,
            sector_type="industry",
            metric="net_strength",
            granularity="minute",
            lookback_days=1,
            limit=8,
            rank_view="leaders",
            include_sector_names=[],
            trading_date=None,
        )
        signals = self.dashboard.get_monitor_signals(session, sector_type="industry", metric="net_strength", limit=8, trading_date=None)
        return self._wrap(
            "sector-monitor",
            {
                "overview": overview,
                "status": status,
                "signals": signals,
                "comparison": comparison,
                "workspace": workspace_payload,
                "watchlist": watchlist,
                "sector_catalog": sector_catalog,
                "trading_dates": trading_dates,
                "defaults": {
                    "sector_type": "industry",
                    "metric": "net_strength",
                    "granularity": "minute",
                    "lookback_days": 1,
                    "limit": 8,
                    "selected_sector": selected_sector,
                    "selected_trading_date": (trading_dates["industry"] or [None])[0],
                },
            },
            updated_candidates=[
                overview.get("updated_at"),
                signals.get("updated_at"),
                comparison.get("updated_at"),
                workspace_payload.get("detail_updated_at"),
            ],
        )

    def build_limit_up_page(self, session: Session) -> dict[str, Any]:
        trading_date = self.now_provider().date()
        summary = self.limit_up.get_summary(trading_date, market_scope="all")
        temperature = self.home_dashboard.market_temperature.get_temperature(trading_date, market_scope="all")
        temperature_history = self.home_dashboard.market_temperature.get_temperature_history(lookback_days=5, market_scope="all")
        ladder = self.limit_up.get_ladder(trading_date, market_scope="all")
        broken = self.limit_up.get_broken_pool(trading_date, market_scope="all")
        dates = self.limit_up.get_available_dates()
        return self._wrap(
            "limit-up-ladder",
            {
                "summary": summary,
                "temperature": temperature,
                "temperature_history": temperature_history,
                "ladder": ladder,
                "broken": broken,
                "dates": dates,
            },
            updated_candidates=[
                summary.get("trading_date"),
                temperature.get("updated_at"),
                temperature_history.get("updated_at"),
                ladder.get("updated_at"),
                broken.get("updated_at"),
            ],
        )

    def build_opportunity_page(self, session: Session) -> dict[str, Any]:
        default_mode = "strong-sector"
        opportunities = self.market_signal.get_opportunities(session, mode=default_mode, limit=20)
        ai_picks = self.ai_center.list_picks(session, run_type="production", trading_date=None)
        return self._wrap(
            "opportunity-pool",
            {
                "default_mode": default_mode,
                "opportunities": opportunities,
                "ai_picks": ai_picks,
            },
            updated_candidates=[opportunities.get("updated_at"), ai_picks.get("updated_at")],
        )

    def build_workspace_page(self, session: Session) -> dict[str, Any]:
        workspace_payload = self.workspace.get_workspace(session)
        return self._wrap(
            "workspace",
            workspace_payload,
            updated_candidates=[workspace_payload.get("updated_at")],
        )

    def build_ai_center_page(self, session: Session) -> dict[str, Any]:
        trading_date = self.now_provider().date()
        overview = self.ai_center.get_daily_overview(session, trading_date=trading_date)
        jobs = self.ai_center.list_jobs(session)
        runs = self.ai_center.list_runs(session, trading_date=trading_date)
        skills = self.ai_center.list_skills(session)
        rulepacks = self.ai_center.list_rulepacks(session)
        backtests = self.ai_center.list_backtests(session)
        return self._wrap(
            "ai-center",
            {
                "trading_date": trading_date.isoformat(),
                "overview": overview,
                "jobs": jobs,
                "runs": runs,
                "skills": skills,
                "rulepacks": rulepacks,
                "backtests": backtests,
            },
            updated_candidates=[
                overview.get("updated_at"),
                runs.get("updated_at"),
                skills.get("updated_at"),
                rulepacks.get("updated_at"),
                backtests.get("updated_at"),
            ],
        )

    def _wrap(self, page_name: str, payload: dict[str, Any], *, updated_candidates: list[Any]) -> dict[str, Any]:
        updated_at = self._pick_updated_at(updated_candidates)
        return {
            "page": page_name,
            "updated_at": updated_at or self.now_provider().isoformat(),
            "source_status": "cache_hit",
            "refresh_recommended": False,
            "payload": payload,
        }

    @staticmethod
    def _pick_updated_at(candidates: list[Any]) -> str | None:
        normalized: list[str] = []
        for value in candidates:
            if value in (None, "", []):
                continue
            if hasattr(value, "isoformat"):
                normalized.append(value.isoformat())
            else:
                normalized.append(str(value))
        if not normalized:
            return None
        return max(normalized)
