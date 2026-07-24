"""BacktestService 单测（P1-4）：T+N 胜率计算 + latest_win_rates 取回。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from app.models import ScreenRun, StockDailyBar
from app.services.backtest import BacktestService
from app.services.screener import ScreenerService


def _seed_bars(db_session, code: str = "000001", n_days: int = 30, start: date = date(2026, 6, 1)) -> None:
    """合成 n_days 日 bars，close 每日递增 0.1（T+N 必涨）。"""
    for i in range(n_days):
        db_session.add(StockDailyBar(
            stock_code=code, trading_date=start + timedelta(days=i),
            open=10.0, close=10.0 + i * 0.1, high=10.5, low=9.5,
            volume=1e6, amount=1e7, change_pct=1.0, turnover_rate=2.0,
        ))
    db_session.commit()


def test_compute_win_rates_rising(db_session):
    """close 递增：T+N 必涨，win_rate=1.0。"""
    _seed_bars(db_session, "000001")
    screener = ScreenerService()
    bt = BacktestService(screener=screener)
    # 第 5 日（close=10.5）买入
    signal_date = date(2026, 6, 1) + timedelta(days=5)
    win_rates = bt._compute_win_rates(db_session, [(signal_date, "000001", 10.5)])
    assert "T+1" in win_rates
    assert win_rates["T+1"]["win_rate"] == 1.0  # T+1 close=10.6 > 10.5
    assert win_rates["T+1"]["count"] == 1
    assert win_rates["T+10"]["win_rate"] == 1.0  # T+10 close=11.5 > 10.5


def test_compute_win_rates_falling(db_session):
    """close 递减：T+N 必跌，win_rate=0.0。"""
    start = date(2026, 6, 1)
    for i in range(30):
        db_session.add(StockDailyBar(
            stock_code="000002", trading_date=start + timedelta(days=i),
            open=20.0, close=20.0 - i * 0.1, high=20.5, low=19.5,
            volume=1e6, amount=1e7, change_pct=-1.0, turnover_rate=2.0,
        ))
    db_session.commit()
    screener = ScreenerService()
    bt = BacktestService(screener=screener)
    signal_date = start + timedelta(days=5)  # close=19.5
    win_rates = bt._compute_win_rates(db_session, [(signal_date, "000002", 19.5)])
    assert win_rates["T+1"]["win_rate"] == 0.0  # T+1 close=19.4 < 19.5


def test_compute_win_rates_empty_signals(db_session):
    """无信号返回空 dict。"""
    screener = ScreenerService()
    bt = BacktestService(screener=screener)
    assert bt._compute_win_rates(db_session, []) == {}


def test_latest_win_rates(db_session):
    """存 ScreenRun 后 latest_win_rates 取回。"""
    db_session.add(ScreenRun(
        preset_id=1,
        win_rates=json.dumps({"T+1": {"win_rate": 0.6, "avg_return": 0.01, "count": 10}}),
        run_at=datetime.now(),
        signal_count=10,
    ))
    db_session.commit()
    screener = ScreenerService()
    bt = BacktestService(screener=screener)
    wr = bt.latest_win_rates(db_session, 1)
    assert wr["T+1"]["win_rate"] == 0.6
    assert wr["T+1"]["count"] == 10


def test_latest_win_rates_none(db_session):
    """无 ScreenRun 返回空。"""
    screener = ScreenerService()
    bt = BacktestService(screener=screener)
    assert bt.latest_win_rates(db_session, 999) == {}
