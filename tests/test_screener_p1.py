"""P1-1 单测：涨停精确化（stk_limit）+ 新指标 KDJ/BOLL/OBV/ATR/CCI/BIAS。"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.screener import INDICATOR_REGISTRY, compute_features


def _make_bars(n_days: int = 30, start_close: float = 10.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    d0 = date(2026, 6, 1)
    rows = []
    close = start_close
    for i in range(n_days):
        close = close * (1 + rng.normal(0, 0.02))
        rows.append({
            "stock_code": "000001",
            "trading_date": d0 + timedelta(days=i),
            "open": close * 0.99, "close": close,
            "high": close * 1.01, "low": close * 0.98,
            "volume": float(1e6 + rng.integers(0, 500000)),
            "amount": 1e7, "change_pct": float(rng.normal(0, 2)),
            "turnover_rate": 2.0,
        })
    df = pd.DataFrame(rows)
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df


def test_limit_up_precise_with_stk_limit():
    """传 limit_df 时用 close>=up_limit 精确判定，替代 change_pct 阈值。"""
    bars = _make_bars(30)
    last_date = bars["trading_date"].iloc[-1]
    last_close = bars["close"].iloc[-1]
    limit_df = pd.DataFrame({
        "stock_code": ["000001"] * 30,
        "trading_date": bars["trading_date"].tolist(),
        "up_limit": bars["close"] * 1.1,  # 默认 up_limit=close*1.1，不涨停
    })
    # 最后一日 up_limit = close -> 涨停
    limit_df.loc[29, "up_limit"] = last_close
    out = compute_features(bars, pd.DataFrame(), last_date, limit_df=limit_df)
    assert out.iloc[0]["limit_up_today"] == 1


def test_limit_up_precise_not_limit():
    """close < up_limit 时非涨停。"""
    bars = _make_bars(30)
    limit_df = pd.DataFrame({
        "stock_code": ["000001"] * 30,
        "trading_date": bars["trading_date"].tolist(),
        "up_limit": bars["close"] * 1.1,  # 全部 up_limit > close，无涨停
    })
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1], limit_df=limit_df)
    assert out.iloc[0]["limit_up_today"] == 0


def test_limit_up_fallback_without_limit_df():
    """不传 limit_df 时 fallback change_pct 阈值（向后兼容）。"""
    bars = _make_bars(30)
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1])
    assert "limit_up_today" in out.columns
    assert out.iloc[0]["limit_up_today"] in (0, 1)


def test_kdj_computed():
    bars = _make_bars(30)
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1])
    k = out.iloc[0]["kdj_k"]
    d = out.iloc[0]["kdj_d"]
    j = out.iloc[0]["kdj_j"]
    assert not np.isnan(k)
    assert not np.isnan(d)
    # J = 3K - 2D
    assert j == pytest.approx(3 * k - 2 * d, abs=0.01)


def test_boll_computed():
    bars = _make_bars(30)
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1])
    mid = out.iloc[0]["boll_mid"]
    up = out.iloc[0]["boll_up"]
    dn = out.iloc[0]["boll_dn"]
    assert not np.isnan(mid)
    # up = mid + 2σ >= mid >= mid - 2σ = dn
    assert up >= mid >= dn


def test_obv_atr_cci_computed():
    bars = _make_bars(30)
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1])
    for col in ("obv", "atr14", "cci14"):
        assert col in out.columns
        val = out.iloc[0][col]
        assert not np.isnan(val), f"{col} 为 NaN"


def test_bias_multi_period():
    bars = _make_bars(30)
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1])
    for col in ("bias6", "bias12", "bias24"):
        assert col in out.columns


def test_new_indicators_in_registry():
    for name in ("kdj_k", "kdj_d", "kdj_j", "boll_mid", "boll_up", "boll_dn",
                 "obv", "atr14", "cci14", "bias6", "bias12", "bias24"):
        assert name in INDICATOR_REGISTRY, f"{name} 未注册到 INDICATOR_REGISTRY"
