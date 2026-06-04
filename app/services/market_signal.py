from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy.orm import Session


class MarketSignalService:
    def __init__(
        self,
        *,
        dashboard: Any,
        limit_up: Any,
        market_temperature: Any,
        realtime_cache: Any,
        workspace: Any | None = None,
        now_provider: Any | None = None,
    ) -> None:
        self.dashboard = dashboard
        self.limit_up = limit_up
        self.market_temperature = market_temperature
        self.realtime_cache = realtime_cache
        self.workspace = workspace
        self.now_provider = now_provider or datetime.now

    def get_alerts_feed(
        self,
        session: Session,
        *,
        signal_type: str = "all",
        strength: str = "all",
        time_window: str = "today",
        limit: int = 20,
        trading_date: date | None = None,
    ) -> dict[str, Any]:
        target_date = trading_date or self.now_provider().date()
        items = self._build_signal_feed(session, trading_date=target_date)
        items = self._filter_signals(items, signal_type=signal_type, strength=strength, time_window=time_window)
        return {
            "trading_date": target_date.isoformat(),
            "signal_type": signal_type,
            "strength": strength,
            "time_window": time_window,
            "updated_at": self.now_provider().isoformat(),
            "items": items[: max(limit, 1)],
        }

    def get_alerts_summary(self, session: Session, trading_date: date | None = None) -> dict[str, Any]:
        target_date = trading_date or self.now_provider().date()
        items = self._build_signal_feed(session, trading_date=target_date)
        top = items[0] if items else None
        return {
            "trading_date": target_date.isoformat(),
            "updated_at": self.now_provider().isoformat(),
            "total": len(items),
            "high_priority_count": sum(1 for item in items if item["level"] == "high"),
            "top_signal": top,
            "title": top["title"] if top else "暂无高优先级信号",
        }

    def get_opportunities(
        self,
        session: Session,
        *,
        mode: str = "strong-sector",
        limit: int = 20,
        trading_date: date | None = None,
    ) -> dict[str, Any]:
        target_date = trading_date or self.now_provider().date()
        ladder = self.limit_up.get_ladder(target_date, market_scope="all")
        broken = self.limit_up.get_broken_pool(target_date, market_scope="all")
        overview = self.dashboard.get_latest_rankings(
            session,
            sector_type="industry",
            limit=8,
            metric="net_amount",
            trading_date=target_date,
        )
        leaders = overview.get("leaders", [])
        candidates: list[dict[str, Any]] = []

        if mode == "strong-sector":
            for item in leaders:
                candidates.append(
                    {
                        "candidate_type": "sector",
                        "mode": mode,
                        "sector_name": item["sector_name"],
                        "stock_code": None,
                        "stock_name": None,
                        "board_count": None,
                        "theme": item["sector_name"],
                        "sector_net_amount": item.get("net_amount"),
                        "stock_net_amount": None,
                        "turnover_rate": None,
                        "volume_ratio": None,
                        "risk_flag": "先确认成分股是否同步承接",
                        "entry_reason": f"{item['sector_name']} 位于资金流入前列，适合先看板块强度和成分股扩散。",
                        "action_url": self._sector_action_url(item["sector_name"]),
                        "freshness_level": self._freshness_level(overview.get("updated_at")),
                        "source_status": "cache",
                    }
                )
        elif mode == "high-conviction-limitup":
            for group in ladder.get("groups", []):
                for stock in group.get("stocks", []):
                    if stock.get("board_count", 0) < 2:
                        continue
                    candidates.append(
                        self._stock_candidate(
                            stock,
                            mode=mode,
                            entry_reason="高连板 + 净流入 + 低炸板次数，适合优先确认承接。",
                        )
                    )
        elif mode == "sector-limitup-resonance":
            for group in ladder.get("groups", []):
                for stock in group.get("stocks", []):
                    if stock.get("board_count", 0) < 2:
                        continue
                    industry = stock.get("industry") or "题材未分类"
                    candidates.append(
                        self._stock_candidate(
                            stock,
                            mode=mode,
                            entry_reason=f"{industry} 出现在连板梯队，适合回到板块页确认是否有资金共振。",
                        )
                    )
        elif mode == "low-first-board-expansion":
            for group in ladder.get("groups", []):
                if group.get("board_count") != 1:
                    continue
                for stock in group.get("stocks", []):
                    candidates.append(
                        self._stock_candidate(
                            stock,
                            mode=mode,
                            entry_reason="首板扩散样本，适合观察是否会成为次日晋级种子。",
                        )
                    )
        else:
            rebound_items: list[dict[str, Any]] = []
            for group in ladder.get("groups", []):
                rebound_items.extend([item for item in group.get("stocks", []) if (item.get("broken_board_count") or 0) > 0])
            rebound_items.extend(broken.get("items", []))
            for stock in rebound_items:
                candidates.append(
                    self._stock_candidate(
                        stock,
                        mode="rebound-watch",
                        entry_reason="出现炸板或回封行为，适合观察承接质量与再次封板能力。",
                    )
                )

        candidates.sort(
            key=lambda item: (
                item.get("board_count") or 0,
                item.get("stock_net_amount") or 0,
                item.get("sector_net_amount") or 0,
            ),
            reverse=True,
        )
        items = candidates[: max(limit, 1)]
        return {
            "mode": mode,
            "trading_date": target_date.isoformat(),
            "updated_at": self.now_provider().isoformat(),
            "title": self._opportunity_mode_title(mode),
            "items": items,
        }

    def get_review_day(self, session: Session, trading_date: date) -> dict[str, Any]:
        temperature = self.market_temperature.get_temperature(trading_date, market_scope="all")
        sectors = self.dashboard.get_latest_rankings(
            session,
            sector_type="industry",
            limit=6,
            metric="net_amount",
            trading_date=trading_date,
        )
        ladder_summary = self.limit_up.get_summary(trading_date, market_scope="all")
        return {
            "trading_date": trading_date.isoformat(),
            "updated_at": self.now_provider().isoformat(),
            "temperature": temperature,
            "top_sectors": sectors.get("leaders", []),
            "weak_sectors": sectors.get("laggards", []),
            "ladder_summary": ladder_summary,
            "review_text": temperature.get("summary_text"),
        }

    def get_review_timeline(self, session: Session, trading_date: date) -> dict[str, Any]:
        return {
            "trading_date": trading_date.isoformat(),
            "updated_at": self.now_provider().isoformat(),
            "items": self._build_signal_feed(session, trading_date=trading_date),
        }

    def build_action_priority(self, session: Session, trading_date: date | None = None) -> dict[str, Any]:
        target_date = trading_date or self.now_provider().date()
        temperature = self.market_temperature.get_temperature(target_date, market_scope="all")
        sector_overview = self.dashboard.get_latest_rankings(
            session,
            sector_type="industry",
            limit=3,
            metric="net_amount",
            trading_date=target_date,
        )
        leaders = sector_overview.get("leaders", [])
        strongest = leaders[0]["sector_name"] if leaders else None
        if temperature.get("temperature_band") in {"偏热", "过热"}:
            return {
                "primary_workspace": "limit-up-ladder",
                "title": "先看情绪与高标承接",
                "reason": temperature.get("summary_text"),
                "href": "/limit-up-ladder",
            }
        return {
            "primary_workspace": "sector-monitor",
            "title": f"先看 {strongest or '板块资金'} 的承接",
            "reason": "市场未进入高标主导阶段，优先确认主线板块和成分股共振。",
            "href": "/sector-monitor",
        }

    def build_home_alert_summary(self, session: Session, trading_date: date | None = None) -> dict[str, Any]:
        summary = self.get_alerts_summary(session, trading_date=trading_date)
        top = summary.get("top_signal") or {}
        return {
            "title": top.get("title") or "暂无高优先级预警",
            "count": summary.get("total", 0),
            "high_priority_count": summary.get("high_priority_count", 0),
            "action_url": top.get("action_url", "/alerts"),
        }

    def build_home_opportunity_summary(self, session: Session, trading_date: date | None = None) -> dict[str, Any]:
        payload = self.get_opportunities(session, mode="high-conviction-limitup", limit=6, trading_date=trading_date)
        top = payload["items"][0] if payload["items"] else None
        return {
            "title": top["stock_name"] if top and top.get("stock_name") else payload["title"],
            "mode": payload["mode"],
            "count": len(payload["items"]),
            "action_url": top.get("action_url", "/opportunity-pool") if top else "/opportunity-pool",
        }

    def _build_signal_feed(self, session: Session, *, trading_date: date) -> list[dict[str, Any]]:
        temperature = self.market_temperature.get_temperature(trading_date, market_scope="all")
        sector_alerts = self.dashboard.get_alerts(
            session,
            sector_type="industry",
            metric="net_amount",
            limit=6,
            trading_date=trading_date,
        )
        sector_signals = self.dashboard.get_monitor_signals(
            session,
            sector_type="industry",
            metric="net_amount",
            limit=6,
            trading_date=trading_date,
        )
        limit_summary = self.limit_up.get_summary(trading_date, market_scope="all")
        ladder = self.limit_up.get_ladder(trading_date, market_scope="all")
        stock_rank = self.realtime_cache.get_individual_rankings(
            session,
            limit=8,
            trading_date=trading_date,
            prefer_cache=True,
        )

        items: list[dict[str, Any]] = [
            {
                "signal_type": "market",
                "level": "high" if temperature.get("temperature_band") in {"偏热", "过热", "冰点"} else "medium",
                "strength": "confirmed",
                "title": f"市场温度 {temperature.get('temperature_band')}",
                "subject_type": "market",
                "subject_name": "全市场",
                "reason": temperature.get("summary_text"),
                "status": temperature.get("risk_flag"),
                "action_url": "/limit-up-ladder",
                "timestamp": temperature.get("updated_at"),
                "freshness_level": self._freshness_level(temperature.get("updated_at")),
                "source_label": temperature.get("source_status", {}).get("source_label", "derived"),
                "sort_weight": 100,
            }
        ]

        for item in sector_alerts.get("items", []):
            sector_name = item.get("sector_name")
            if not sector_name:
                continue
            items.append(
                {
                    "signal_type": "sector",
                    "level": "high" if abs(item.get("rank_change", 0)) >= 1 else "medium",
                    "strength": "confirmed" if abs(item.get("delta_value", 0)) >= 5 else "watch",
                    "title": f"{sector_name} 资金位次变化",
                    "subject_type": "sector",
                    "subject_name": sector_name,
                    "reason": f"净额变化 {item.get('delta_value', 0):.2f}，位次变化 {item.get('rank_change', 0)}。",
                    "status": "观察是否形成主线扩散",
                    "action_url": self._sector_action_url(sector_name),
                    "timestamp": sector_alerts.get("updated_at"),
                    "freshness_level": self._freshness_level(sector_alerts.get("updated_at")),
                    "source_label": "cache",
                    "sort_weight": 80 + abs(item.get("rank_change", 0)),
                }
            )

        for item in sector_signals.get("items", [])[:4]:
            sector_name = item.get("sector_name")
            if not sector_name:
                continue
            items.append(
                {
                    "signal_type": "sector",
                    "level": "high" if abs(item.get("acceleration_1", 0)) >= 3 else "medium",
                    "strength": "confirmed" if item.get("persistence", 0) >= 3 else "watch",
                    "title": f"{sector_name} 出现板块异动",
                    "subject_type": "sector",
                    "subject_name": sector_name,
                    "reason": f"1分钟加速度 {item.get('acceleration_1', 0):.2f}，延续 {item.get('persistence', 0)} 个采样点。",
                    "status": "看成分股是否同步承接",
                    "action_url": self._sector_action_url(sector_name),
                    "timestamp": sector_signals.get("updated_at"),
                    "freshness_level": self._freshness_level(sector_signals.get("updated_at")),
                    "source_label": "cache",
                    "sort_weight": 72 + abs(item.get("acceleration_1", 0)),
                }
            )

        if limit_summary.get("highest_board", 0) >= 3:
            items.append(
                {
                    "signal_type": "limit_up",
                    "level": "high",
                    "strength": "confirmed" if temperature.get("temperature_band") in {"偏热", "过热"} else "watch",
                    "title": f"最高板来到 {limit_summary['highest_board']} 连板",
                    "subject_type": "limit_up",
                    "subject_name": "连板梯队",
                    "reason": f"连板总数 {limit_summary.get('limit_up_count', 0)}，炸板 {limit_summary.get('broken_count', 0)}。",
                    "status": "先看抱团是否延续",
                    "action_url": "/limit-up-ladder",
                    "timestamp": temperature.get("updated_at"),
                    "freshness_level": self._freshness_level(temperature.get("updated_at")),
                    "source_label": "akshare",
                    "sort_weight": 88 + limit_summary.get("highest_board", 0),
                }
            )

        first_leader = next((group.get("stocks", [None])[0] for group in ladder.get("groups", []) if group.get("stocks")), None)
        if first_leader:
            items.append(
                {
                    "signal_type": "stock",
                    "level": "medium",
                    "strength": "watch",
                    "title": f"{first_leader['name']} 位于梯队前排",
                    "subject_type": "stock",
                    "subject_name": first_leader["name"],
                    "reason": f"{first_leader.get('board_count', 0)} 连板，净流入 {self._format_amount(first_leader.get('net_inflow'))}。",
                    "status": "结合板块共振继续确认",
                    "action_url": f"/limit-up-ladder?stock_code={quote_plus(str(first_leader['code']))}",
                    "timestamp": temperature.get("updated_at"),
                    "freshness_level": self._freshness_level(temperature.get("updated_at")),
                    "source_label": "akshare",
                    "sort_weight": 68 + first_leader.get("board_count", 0),
                }
            )

        for stock in stock_rank.get("stocks", [])[:4]:
            stock_code = stock.get("股票代码") or stock.get("stock_code") or stock.get("code")
            stock_name = stock.get("股票简称") or stock.get("stock_name") or stock.get("name") or stock_code
            net_amount = stock.get("净额") if "净额" in stock else stock.get("net_amount")
            change_percent = stock.get("涨跌幅") if "涨跌幅" in stock else stock.get("change_percent")
            if not stock_name:
                continue
            items.append(
                {
                    "signal_type": "stock",
                    "level": "medium",
                    "strength": "watch",
                    "title": f"{stock_name} 个股资金活跃",
                    "subject_type": "stock",
                    "subject_name": stock_name,
                    "reason": f"净额 {self._format_amount(net_amount)}，涨跌幅 {self._format_percent(change_percent)}。",
                    "status": "看是否和板块、连板共振",
                    "action_url": f"/sector-monitor?stock_code={quote_plus(str(stock_code))}" if stock_code else "/sector-monitor",
                    "timestamp": stock_rank.get("updated_at"),
                    "freshness_level": self._freshness_level(stock_rank.get("updated_at")),
                    "source_label": stock_rank.get("source_status", "cache"),
                    "sort_weight": 55 + max(net_amount or 0, 0) / 100000000,
                }
            )

        items.sort(
            key=lambda item: (self._level_weight(item["level"]), item.get("sort_weight", 0), item.get("timestamp") or ""),
            reverse=True,
        )
        return items

    @staticmethod
    def _filter_signals(items: list[dict[str, Any]], *, signal_type: str, strength: str, time_window: str) -> list[dict[str, Any]]:
        filtered = items
        if signal_type != "all":
            filtered = [item for item in filtered if item["signal_type"] == signal_type]
        if strength == "high-priority":
            filtered = [item for item in filtered if item["level"] == "high"]
        elif strength == "confirmed":
            filtered = [item for item in filtered if item["strength"] == "confirmed"]
        return filtered

    @staticmethod
    def _opportunity_mode_title(mode: str) -> str:
        return {
            "strong-sector": "强趋势板块",
            "high-conviction-limitup": "高承接连板",
            "sector-limitup-resonance": "板块 + 连板共振",
            "low-first-board-expansion": "低位首板扩散",
            "rebound-watch": "高标回封观察",
        }.get(mode, "机会池")

    def _stock_candidate(self, stock: dict[str, Any], *, mode: str, entry_reason: str) -> dict[str, Any]:
        broken_count = stock.get("broken_board_count") or 0
        risk_flag = "炸板次数偏多" if broken_count >= 2 else "优先看承接质量"
        code = stock.get("code")
        return {
            "candidate_type": "stock",
            "mode": mode,
            "sector_name": stock.get("industry"),
            "stock_code": code,
            "stock_name": stock.get("name"),
            "board_count": stock.get("board_count"),
            "theme": stock.get("industry"),
            "sector_net_amount": None,
            "stock_net_amount": stock.get("net_inflow"),
            "turnover_rate": stock.get("turnover_rate"),
            "volume_ratio": None,
            "risk_flag": risk_flag,
            "entry_reason": entry_reason,
            "action_url": f"/limit-up-ladder?stock_code={quote_plus(str(code))}" if code else "/limit-up-ladder",
            "freshness_level": "delayed",
            "source_status": stock.get("source_view", "akshare"),
        }

    @staticmethod
    def _level_weight(level: str) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(level, 0)

    def _freshness_level(self, updated_at: str | None) -> str:
        if not updated_at:
            return "stale"
        try:
            updated = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00").replace(" ", "T"))
        except ValueError:
            return "stale"
        delta = abs((self.now_provider() - updated).total_seconds())
        if delta <= 180:
            return "realtime"
        if delta <= 900:
            return "delayed"
        if delta <= 7200:
            return "cache"
        return "stale"

    @staticmethod
    def _format_amount(value: Any) -> str:
        try:
            numeric = float(value or 0)
        except (TypeError, ValueError):
            return "--"
        absolute = abs(numeric)
        if absolute >= 100000000:
            return f"{numeric / 100000000:.2f}亿"
        if absolute >= 10000:
            return f"{numeric / 10000:.2f}万"
        return f"{numeric:.2f}"

    @staticmethod
    def _format_percent(value: Any) -> str:
        try:
            numeric = float(value or 0)
        except (TypeError, ValueError):
            return "--"
        return f"{numeric:+.2f}%"

    @staticmethod
    def _sector_action_url(sector_name: str) -> str:
        return f"/sector-monitor?sector_type=industry&sector_name={quote_plus(str(sector_name))}"
