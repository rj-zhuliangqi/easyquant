from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable


class MarketTemperatureService:
    WEIGHTS = {
        "highest_board_score": 0.16,
        "limit_up_total_score": 0.16,
        "first_board_breadth_score": 0.10,
        "broken_pressure_score": 0.20,
        "promotion_score": 0.22,
        "turnover_score": 0.16,
    }

    BANDS = (
        (20, "冰点"),
        (40, "偏冷"),
        (60, "中性"),
        (80, "偏热"),
        (100, "过热"),
    )

    def __init__(
        self,
        *,
        limit_up: Any,
        home_dashboard: Any,
        gateway: Any,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.limit_up = limit_up
        self.home_dashboard = home_dashboard
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now
        self._temperature_cache: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        self._history_cache: dict[tuple[str, int], tuple[str, dict[str, Any]]] = {}

    def get_temperature(self, trading_date: date, market_scope: str = "all") -> dict[str, Any]:
        cache_key = (trading_date.isoformat(), market_scope)
        cache_stamp = self._cache_stamp(trading_date)
        cached = self._temperature_cache.get(cache_key)
        if cached and cached[0] == cache_stamp:
            return cached[1]

        summary = self.limit_up.get_summary(trading_date, market_scope=market_scope)
        turnover_metrics = self._resolve_turnover_metrics(trading_date)
        raw_metrics = {
            "highest_board": summary.get("highest_board", 0),
            "limit_up_count": summary.get("limit_up_count", 0),
            "first_board_count": summary.get("first_board_count", 0),
            "high_board_count": summary.get("high_board_count", 0),
            "broken_count": summary.get("broken_count", 0),
            "promotion_rate": summary.get("promotion_rate", 0.0),
            "break_rate": summary.get("break_rate", 0.0),
            "market_turnover": turnover_metrics["market_turnover"],
            "market_turnover_ratio_20d": turnover_metrics["market_turnover_ratio_20d"],
        }
        factors = self._score_factors(raw_metrics)
        temperature_score = round(
            sum(factors[key] * weight for key, weight in self.WEIGHTS.items()),
            2,
        )
        band = self._band_for_score(temperature_score)
        signals = self._build_signals(raw_metrics, factors)
        adjusted_band = self._apply_band_overrides(band, raw_metrics, signals)
        summary_text = self._build_summary_text(adjusted_band, raw_metrics, signals)
        payload = {
            "trading_date": trading_date.isoformat(),
            "market_scope": market_scope,
            "temperature_score": temperature_score,
            "temperature_band": adjusted_band,
            "summary_text": summary_text,
            "risk_flag": self._build_risk_flag(raw_metrics, signals),
            "factors": factors,
            "raw_metrics": raw_metrics,
            "signals": signals[:3],
            "source_status": turnover_metrics["source_status"],
            "updated_at": self.now_provider().isoformat(),
        }
        self._temperature_cache[cache_key] = (cache_stamp, payload)
        return payload

    def get_temperature_history(self, lookback_days: int = 20, market_scope: str = "all") -> dict[str, Any]:
        safe_lookback = min(max(int(lookback_days), 1), 60)
        cache_key = (market_scope, safe_lookback)
        cache_stamp = self.now_provider().replace(minute=self.now_provider().minute, second=0, microsecond=0).isoformat()
        cached = self._history_cache.get(cache_key)
        if cached and cached[0] == cache_stamp:
            return cached[1]

        dates = self.limit_up.get_available_dates(count=safe_lookback).get("dates", [])[:safe_lookback]
        items = []
        for item in reversed(dates):
            payload = self.get_temperature(date.fromisoformat(item), market_scope=market_scope)
            raw = payload["raw_metrics"]
            items.append(
                {
                    "trading_date": payload["trading_date"],
                    "temperature_score": payload["temperature_score"],
                    "temperature_band": payload["temperature_band"],
                    "highest_board": raw["highest_board"],
                    "limit_up_count": raw["limit_up_count"],
                    "first_board_count": raw["first_board_count"],
                    "high_board_count": raw["high_board_count"],
                    "broken_count": raw["broken_count"],
                    "break_rate": raw["break_rate"],
                    "promotion_rate": raw["promotion_rate"],
                    "market_turnover": raw["market_turnover"],
                    "market_turnover_ratio_20d": raw["market_turnover_ratio_20d"],
                    "factors": payload["factors"],
                }
            )

        result = {
            "market_scope": market_scope,
            "lookback_days": safe_lookback,
            "items": items,
            "updated_at": self.now_provider().isoformat(),
        }
        self._history_cache[cache_key] = (cache_stamp, result)
        return result

    def _cache_stamp(self, trading_date: date) -> str:
        now = self.now_provider()
        if trading_date == now.date():
            return now.replace(second=0, microsecond=0).isoformat()
        return trading_date.isoformat()

    def _resolve_turnover_metrics(self, trading_date: date) -> dict[str, Any]:
        proxy_map = self._market_turnover_proxy_map(days=40)
        ratio = None
        market_turnover = None
        source_label = "derived"
        fallback_used = True
        degraded_fields: list[str] = []

        if trading_date == self.now_provider().date():
            overview = self.home_dashboard.get_market_overview()
            breadth = overview.get("breadth", {})
            market_turnover = breadth.get("market_turnover")
            source_label = overview.get("source_summary", {}).get("breadth", {}).get("source_label", "derived")
            fallback_used = overview.get("source_summary", {}).get("breadth", {}).get("fallback_used", True)
            degraded_fields = list(overview.get("source_summary", {}).get("breadth", {}).get("degraded_fields", []))
        if market_turnover is None:
            market_turnover = proxy_map.get(trading_date.isoformat())
            if market_turnover is not None:
                source_label = "index_volume_proxy"
                fallback_used = True
                degraded_fields = ["market_turnover_proxy"]

        series_values = [value for value in proxy_map.values() if isinstance(value, (int, float)) and value]
        if market_turnover is not None and series_values:
            base_values = series_values[-20:] if len(series_values) >= 20 else series_values
            baseline = sum(base_values) / max(len(base_values), 1)
            if baseline:
                ratio = round(float(market_turnover) / baseline, 4)

        return {
            "market_turnover": market_turnover,
            "market_turnover_ratio_20d": ratio,
            "source_status": {
                "source_label": source_label,
                "fallback_used": fallback_used,
                "degraded_fields": degraded_fields,
            },
        }

    def _market_turnover_proxy_map(self, days: int = 40) -> dict[str, float]:
        series_map: dict[str, float] = {}
        for symbol in ("sh000001", "sz399001", "sz399006"):
            frame = self.gateway.fetch_market_index_history(symbol=symbol, days=days)
            if frame.empty:
                continue
            for record in frame.to_dict(orient="records"):
                raw_date = record.get("date")
                label = raw_date.isoformat() if hasattr(raw_date, "isoformat") else str(raw_date)
                volume = self._to_float(record.get("volume"))
                if volume is None:
                    continue
                series_map[label] = series_map.get(label, 0.0) + volume
        return dict(sorted(series_map.items()))

    def _score_factors(self, raw_metrics: dict[str, Any]) -> dict[str, float]:
        highest_board = float(raw_metrics.get("highest_board") or 0)
        limit_up_count = float(raw_metrics.get("limit_up_count") or 0)
        high_board_count = float(raw_metrics.get("high_board_count") or 0)
        first_board_count = float(raw_metrics.get("first_board_count") or 0)
        promotion_rate = float(raw_metrics.get("promotion_rate") or 0)
        break_rate = float(raw_metrics.get("break_rate") or 0)
        turnover_ratio = raw_metrics.get("market_turnover_ratio_20d")

        total_ratio = high_board_count / max(limit_up_count, 1.0)
        first_ratio = first_board_count / max(limit_up_count, 1.0)

        highest_board_score = self._clamp_score(highest_board / 7.0 * 100.0)
        limit_up_total_score = self._clamp_score((limit_up_count / 50.0) * 70.0 + total_ratio * 30.0 * 100.0 / 100.0)
        first_board_breadth_score = self._balance_score(first_ratio, midpoint=0.42, tolerance=0.30)
        broken_pressure_score = self._clamp_score((1.0 - min(max(break_rate, 0.0), 0.8) / 0.8) * 100.0)
        promotion_score = self._clamp_score(min(max(promotion_rate, 0.0), 0.8) / 0.8 * 100.0)
        turnover_score = 50.0 if turnover_ratio is None else self._turnover_score(turnover_ratio)

        return {
            "highest_board_score": round(highest_board_score, 2),
            "limit_up_total_score": round(limit_up_total_score, 2),
            "first_board_breadth_score": round(first_board_breadth_score, 2),
            "broken_pressure_score": round(broken_pressure_score, 2),
            "promotion_score": round(promotion_score, 2),
            "turnover_score": round(turnover_score, 2),
        }

    def _build_signals(self, raw_metrics: dict[str, Any], factors: dict[str, float]) -> list[str]:
        highest_board = raw_metrics["highest_board"]
        limit_up_count = raw_metrics["limit_up_count"]
        first_ratio = raw_metrics["first_board_count"] / max(limit_up_count, 1)
        break_rate = raw_metrics["break_rate"]
        promotion_rate = raw_metrics["promotion_rate"]
        turnover_ratio = raw_metrics["market_turnover_ratio_20d"]
        high_board_count = raw_metrics["high_board_count"]

        signals: list[str] = []
        if highest_board >= 4 and break_rate >= 0.35:
            signals.append("高标仍在抬升，但炸板率偏高，追高容错下降。")
        if promotion_rate <= 0.2 and first_ratio >= 0.55:
            signals.append("首板扩散偏多，但晋级率偏低，更像轮动而不是主升。")
        if turnover_ratio is not None and turnover_ratio >= 1.08 and promotion_rate >= 0.3 and break_rate <= 0.2:
            signals.append("成交量放大且晋级率改善，短线情绪出现升温确认。")
        if high_board_count <= 1 and break_rate >= 0.4 and (turnover_ratio is None or turnover_ratio <= 0.95):
            signals.append("高标稀少、炸板偏多、量能未放大，更像退潮确认。")
        if not signals:
            if factors["promotion_score"] >= 65 and factors["broken_pressure_score"] >= 65:
                signals.append("晋级与容错尚可，情绪更偏进攻侧。")
            else:
                signals.append("结构没有明显共振，先观察情绪是否进一步确认。")
        return signals

    def _build_summary_text(self, band: str, raw_metrics: dict[str, Any], signals: list[str]) -> str:
        highest_board = raw_metrics["highest_board"]
        promotion_rate = raw_metrics["promotion_rate"]
        break_rate = raw_metrics["break_rate"]
        turnover_ratio = raw_metrics["market_turnover_ratio_20d"]

        if band in {"偏热", "过热"}:
            if break_rate >= 0.3:
                return f"空间板仍在，最高 {highest_board} 连板，但炸板率回升，属于{band}中的分歧结构。"
            if turnover_ratio is not None and turnover_ratio >= 1.0:
                return f"空间板上推、晋级率维持在 {promotion_rate:.0%} 左右，成交量也在配合，短线情绪{band}。"
            return f"高度和总量都不弱，但量能配合一般，当前是{band}中的抱团观察段。"
        if band == "中性":
            return "连板结构仍在，但扩散和承接没有形成明显共振，市场更像震荡中的择强阶段。"
        if band == "偏冷":
            return "首板仍有尝试，但高标延续不足，晋级率和容错都偏弱，情绪更偏防守。"
        return "空间压制、炸板偏多、成交配合不足，短线情绪处于明显退潮区。"

    def _build_risk_flag(self, raw_metrics: dict[str, Any], signals: list[str]) -> str:
        if raw_metrics["break_rate"] >= 0.35:
            return "炸板率抬升，追高容错下降"
        if raw_metrics["promotion_rate"] <= 0.2:
            return "晋级率偏低，隔日延续性不足"
        if raw_metrics["market_turnover_ratio_20d"] is not None and raw_metrics["market_turnover_ratio_20d"] < 0.95:
            return "成交量未明显放大，情绪确认仍不足"
        return signals[0] if signals else "情绪与量能暂时均衡"

    def _apply_band_overrides(self, band: str, raw_metrics: dict[str, Any], signals: list[str]) -> str:
        levels = ["冰点", "偏冷", "中性", "偏热", "过热"]
        index = levels.index(band)
        if raw_metrics["highest_board"] >= 4 and raw_metrics["break_rate"] >= 0.35:
            index = max(index - 1, 0)
        if raw_metrics["promotion_rate"] <= 0.2 and raw_metrics["limit_up_count"] > 0 and raw_metrics["first_board_count"] / max(raw_metrics["limit_up_count"], 1) >= 0.55:
            index = max(index - 1, 0)
        return levels[index]

    def _band_for_score(self, score: float) -> str:
        for threshold, label in self.BANDS:
            if score <= threshold:
                return label
        return "过热"

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(100.0, value))

    @staticmethod
    def _balance_score(value: float, midpoint: float, tolerance: float) -> float:
        deviation = abs(value - midpoint)
        if tolerance <= 0:
            return 50.0
        return max(0.0, min(100.0, (1.0 - min(deviation / tolerance, 1.0)) * 100.0))

    @staticmethod
    def _turnover_score(value: float) -> float:
        if value <= 0.75:
            return 20.0
        if value >= 1.35:
            return 100.0
        return max(0.0, min(100.0, 20.0 + (value - 0.75) / 0.60 * 80.0))

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value in (None, "", "None"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
