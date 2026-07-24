"""IndicatorsDailyService 单测：43 列预计算、data_hash、idempotent upsert。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.models import StockDailyBar, StockFundFlowDaily, StockIndicatorDaily
from app.services.indicators_daily import COMPUTE_VERSION, _PERSIST_COLUMNS, IndicatorsDailyService


def _make_bars(code: str, n_days: int = 120, start: date = date(2026, 1, 5), trend: float = 0.05, seed: int = 0) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n_days, freq="B")
    rng = np.random.default_rng(seed)
    base = 10.0 + np.cumsum(np.full(n_days, trend)) + rng.normal(0, 0.1, n_days)
    rows = []
    for i, d in enumerate(dates):
        prev = base[i - 1] if i > 0 else base[0]
        rows.append({
            "stock_code": code,
            "trading_date": d.date(),
            "open": float(base[i] - 0.05),
            "close": float(base[i]),
            "high": float(base[i] + 0.1),
            "low": float(base[i] - 0.1),
            "volume": float(1_000_000 + i * 10_000),
            "amount": float(10_000_000 + i * 100_000),
            "change_pct": float(0.0 if i == 0 else (base[i] - prev) / prev * 100),
            "turnover_rate": float(1.5 + i * 0.05),
        })
    return pd.DataFrame(rows)


def _seed_bars(session, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        session.add(StockDailyBar(
            stock_code=row["stock_code"],
            trading_date=row["trading_date"],
            open=float(row["open"]), close=float(row["close"]),
            high=float(row["high"]), low=float(row["low"]),
            volume=float(row["volume"]), amount=float(row["amount"]),
            change_pct=float(row["change_pct"]), turnover_rate=float(row["turnover_rate"]),
        ))
    session.commit()


def _seed_flow(session, code: str, dates: list[date], amounts: list[float]) -> None:
    for d, amt in zip(dates, amounts):
        session.add(StockFundFlowDaily(
            stock_code=code, trading_date=d,
            main_net_amount=amt, main_net_ratio=5.0,
            super_large_net=amt / 2, large_net=amt / 4,
        ))
    session.commit()


# 1. 基本：120 日 bars → 43 列落库
def test_compute_writes_43_columns(db_session) -> None:
    bars = _make_bars("000001", n_days=120, trend=0.1)
    _seed_bars(db_session, bars)
    target = bars["trading_date"].iloc[-1]
    result = IndicatorsDailyService().compute_for_date(db_session, target)
    assert result["rows"] == 1
    assert result["stocks"] == 1
    row = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").one()
    # 核心指标非空
    for col in ("ma5", "ma10", "ma20", "ma60", "rsi14", "macd_dif", "volume_ratio"):
        assert getattr(row, col) is not None, f"{col} should not be None"
    # compute_version
    assert row.compute_version == COMPUTE_VERSION
    # data_hash 非空
    assert len(row.data_hash) == 40  # sha1


# 2. 只有 30 日 bars：ma60 / high_60d_break 应为 None / 0，ma20 应有
def test_compute_with_short_history_nan_60d(db_session) -> None:
    bars = _make_bars("000001", n_days=30, trend=0.1)
    _seed_bars(db_session, bars)
    target = bars["trading_date"].iloc[-1]
    IndicatorsDailyService().compute_for_date(db_session, target)
    row = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").one()
    assert row.ma20 is not None
    assert row.ma60 is None
    # high_60d_break: screener 缺数据时填 0（非 None）；只校验不大于 1
    assert row.high_60d_break in (0, None)


# 3. data_hash 稳定
def test_data_hash_stable_on_repeat(db_session) -> None:
    bars = _make_bars("000001", n_days=60, trend=0.05)
    _seed_bars(db_session, bars)
    target = bars["trading_date"].iloc[-1]
    svc = IndicatorsDailyService()
    svc.compute_for_date(db_session, target)
    h1 = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").one().data_hash
    # 再算一次（bars 没变）
    svc.compute_for_date(db_session, target)
    h2 = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").one().data_hash
    assert h1 == h2


# 4. data_hash 随 bars 更新而变
def test_data_hash_changes_when_bars_extended(db_session) -> None:
    bars1 = _make_bars("000001", n_days=60, trend=0.05, seed=1)
    _seed_bars(db_session, bars1)
    target = bars1["trading_date"].iloc[-1]
    IndicatorsDailyService().compute_for_date(db_session, target)
    h1 = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").one().data_hash
    # 加一行 bar（trading_date 更新）
    db_session.add(StockDailyBar(
        stock_code="000001", trading_date=target + timedelta(days=1),
        open=10.5, close=10.7, high=10.8, low=10.4,
        volume=1_000_000, amount=10_000_000, change_pct=1.0, turnover_rate=1.5,
    ))
    db_session.commit()
    IndicatorsDailyService().compute_for_date(db_session, target + timedelta(days=1))
    h2 = db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").filter(
        StockIndicatorDaily.trading_date == target + timedelta(days=1)
    ).one().data_hash
    assert h1 != h2


# 5. 多只股票同时落库
def test_multi_stock_compute(db_session) -> None:
    for code, seed in [("000001", 1), ("000002", 2), ("600000", 3)]:
        bars = _make_bars(code, n_days=60, trend=0.05, seed=seed)
        _seed_bars(db_session, bars)
    target = bars["trading_date"].iloc[-1]
    result = IndicatorsDailyService().compute_for_date(db_session, target)
    assert result["rows"] == 3
    codes = {r.stock_code for r in db_session.query(StockIndicatorDaily).all()}
    assert codes == {"000001", "000002", "600000"}


# 6. 无 bars 时返回 0
def test_no_bars_returns_zero(db_session) -> None:
    result = IndicatorsDailyService().compute_for_date(db_session, date(2026, 5, 14))
    assert result["rows"] == 0
    assert db_session.query(StockIndicatorDaily).count() == 0


# 7. idempotent upsert
def test_idempotent_compute(db_session) -> None:
    bars = _make_bars("000001", n_days=60, trend=0.05)
    _seed_bars(db_session, bars)
    target = bars["trading_date"].iloc[-1]
    svc = IndicatorsDailyService()
    svc.compute_for_date(db_session, target)
    svc.compute_for_date(db_session, target)
    assert db_session.query(StockIndicatorDaily).filter_by(stock_code="000001").count() == 1


# 8. 列数恒为 44（防御 regression）
def test_persist_columns_count_is_44() -> None:
    assert len(_PERSIST_COLUMNS) == 44
    # 检查每个列都在 StockIndicatorDaily 模型中
    from app.models import StockIndicatorDaily
    model_cols = {c.name for c in StockIndicatorDaily.__table__.columns}
    for col in _PERSIST_COLUMNS:
        assert col in model_cols, f"{col} not in StockIndicatorDaily model"
