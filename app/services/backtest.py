"""信号统计法回测（P1-4）。

对每个历史交易日执行策略（screener.run with as_of_date，PIT 防未来数据泄漏），
统计入选股 T+1/3/5/10/20 收益分布与胜率，存 ``screen_runs``。策略卡片展示 T+N 胜率，
替代"近5日命中数"（后者太短且曾实测全 0）。

对标通达信"专家系统评测"和指标网站"次日最高价胜率"。

避坑（P1-4 部分实现，后续完善）：
- 前复权：收益用 stock_daily_bars.close（已 qfq）✓
- 涨跌停不可成交：暂用 close 算（信号日涨停买不进，后续按下一可成交价）TODO
- 幸存者偏差：universe 用当前快照（含退市股待补）TODO
- 交易成本：暂未扣（万2.5佣金+千0.5印花税）TODO
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScreenRun, StockDailyBar
from app.services.screener import ScreenerService

logger = logging.getLogger(__name__)

PERIODS = [1, 3, 5, 10, 20]


class BacktestService:
    """信号统计法回测：策略历史表现 T+N 胜率。"""

    def __init__(self, screener: ScreenerService, now_provider: Callable[[], datetime] | None = None) -> None:
        self.screener = screener
        self.now_provider = now_provider or datetime.now

    def run_backtest(self, session: Session, preset_id: int, days: int = 30) -> dict[str, Any]:
        """对最近 ``days`` 个交易日执行策略，算 T+N 胜率，存 ScreenRun。

        返回 ``{"run_id", "signal_count", "win_rates", "trade_dates"}``。
        """
        from app.models import ScreenerPreset

        preset = session.get(ScreenerPreset, preset_id)
        if preset is None:
            raise KeyError(f"preset_id {preset_id} 不存在")

        trade_dates = self._recent_trade_dates(session, days)
        if not trade_dates:
            return {"run_id": None, "signal_count": 0, "win_rates": {}, "trade_dates": []}

        # 对每个交易日执行策略（as_of_date=PIT 回放）
        signals: list[tuple[Any, str, float]] = []  # (signal_date, code, entry_close)
        for td in trade_dates:
            request = {
                "preset_id": preset_id,
                "universe": {"as_of_date": td.isoformat()},
                "limit": 0,  # 不截断，全量入选
            }
            try:
                result = self.screener.run(session, request)
                for r in result.get("results", []):
                    close = r.get("close")
                    if close is not None and not (isinstance(close, float) and pd.isna(close)):
                        signals.append((td, str(r["code"]).zfill(6), float(close)))
            except Exception:  # noqa: BLE001
                logger.exception("backtest run failed for %s", td)

        win_rates = self._compute_win_rates(session, signals)

        run = ScreenRun(
            preset_id=preset_id,
            ir_snapshot=preset.ir_json or preset.conditions_json,
            start_date=trade_dates[0],
            end_date=trade_dates[-1],
            run_at=self.now_provider(),
            signal_count=len(signals),
            win_rates=json.dumps(win_rates, ensure_ascii=False),
        )
        session.add(run)
        session.commit()
        logger.info(
            "backtest preset=%s days=%d signals=%d win_rates=%s",
            preset_id, len(trade_dates), len(signals), win_rates,
        )
        return {
            "run_id": run.id,
            "signal_count": len(signals),
            "win_rates": win_rates,
            "trade_dates": [d.isoformat() for d in trade_dates],
        }

    def _recent_trade_dates(self, session: Session, days: int) -> list:
        rows = list(session.execute(
            select(StockDailyBar.trading_date)
            .group_by(StockDailyBar.trading_date)
            .order_by(StockDailyBar.trading_date.desc())
            .limit(days)
        ).scalars())
        return sorted(set(rows))

    def _compute_win_rates(self, session: Session, signals: list[tuple[Any, str, float]]) -> dict:
        """对每个 signal 算 T+N 收益（stock_daily_bars.close，已 qfq），聚合胜率。"""
        if not signals:
            return {}
        codes = list({c for _, c, _ in signals})
        rows = list(session.execute(
            select(StockDailyBar.stock_code, StockDailyBar.trading_date, StockDailyBar.close)
            .where(StockDailyBar.stock_code.in_(codes))
            .order_by(StockDailyBar.stock_code, StockDailyBar.trading_date)
        ))
        price_map: dict[str, list[tuple]] = {}
        for code, td, close in rows:
            price_map.setdefault(code, []).append((td, float(close) if close is not None else None))

        returns: dict[str, list[float]] = {f"T+{n}": [] for n in PERIODS}
        for signal_date, code, entry_close in signals:
            prices = price_map.get(code, [])
            # 找 signal_date 位置
            idx = None
            for i, (d, _) in enumerate(prices):
                if d == signal_date:
                    idx = i
                    break
            if idx is None or not entry_close:
                continue
            for n in PERIODS:
                if idx + n < len(prices):
                    fc = prices[idx + n][1]
                    if fc:
                        returns[f"T+{n}"].append((fc - entry_close) / entry_close)

        win_rates: dict[str, dict] = {}
        for label, rets in returns.items():
            if rets:
                win_rates[label] = {
                    "win_rate": round(sum(1 for r in rets if r > 0) / len(rets), 4),
                    "avg_return": round(sum(rets) / len(rets), 4),
                    "count": len(rets),
                }
        return win_rates

    def latest_win_rates(self, session: Session, preset_id: int) -> dict:
        """策略卡片用：取该 preset 最新 ScreenRun 的 win_rates。"""
        run = session.scalar(
            select(ScreenRun)
            .where(ScreenRun.preset_id == preset_id)
            .order_by(ScreenRun.run_at.desc())
            .limit(1)
        )
        if not run or not run.win_rates:
            return {}
        try:
            return json.loads(run.win_rates)
        except Exception:  # noqa: BLE001
            return {}
