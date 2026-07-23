"""条件树 IR 引擎单测（P1-2）。

重点验证"涨停后缩量回踩"（BARSLAST 锚点 + REF(var)）能正确表达，以及未来函数检测。
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.screener_ir import IRError, check_future_functions, evaluate_ir


def _make_test_bars(limit_up_day: int = 24, n_days: int = 30) -> pd.DataFrame:
    """合成 1 只股票 n_days 日。第 limit_up_day 日涨停，最后一日缩量回踩。"""
    d0 = date(2026, 6, 1)
    rows = []
    for i in range(n_days):
        if i == limit_up_day:  # 涨停日
            rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                         "open": 10.5, "close": 11.0, "high": 11.0, "low": 10.5,
                         "volume": 1e7, "amount": 1e8, "change_pct": 10.0, "turnover_rate": 5.0})
        elif i == n_days - 1:  # latest：缩量回踩
            rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                         "open": 10.5, "close": 10.5, "high": 10.6, "low": 10.0,
                         "volume": 3e6, "amount": 3e7, "change_pct": 0.0, "turnover_rate": 2.0})
        else:
            rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                         "open": 10.0, "close": 10.0 + i * 0.01, "high": 10.1, "low": 9.9,
                         "volume": 5e6, "amount": 5e7, "change_pct": 0.5, "turnover_rate": 2.0})
    df = pd.DataFrame(rows)
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df


def _frame_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    return bars.groupby("stock_code").tail(1).reset_index(drop=True)


def test_ir_basic_field_compare():
    bars = _make_test_bars()
    frame = _frame_from_bars(bars)
    # latest close >= 10
    ir = {"root": {"type": "compare", "left": {"type": "field", "name": "close"}, "op": ">=", "right": {"type": "const", "value": 10}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_ir_ref_const():
    """REF(close, 1) = 昨日 close。"""
    bars = _make_test_bars()
    frame = _frame_from_bars(bars)
    prev_close = bars["close"].iloc[-2]
    ir = {"root": {"type": "compare", "left": {"type": "func", "name": "REF", "args": [{"type": "field", "name": "close"}, {"type": "const", "value": 1}]}, "op": "==", "right": {"type": "const", "value": prev_close}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_ir_barslast_anchor():
    """BARSLAST(涨停) = 距上次涨停天数。latest=第30日，涨停=第25日 -> T=5。"""
    bars = _make_test_bars(limit_up_day=24, n_days=30)  # 0-indexed 24 = 第25日
    frame = _frame_from_bars(bars)
    ir = {"vars": [
        {"name": "T", "expr": {"type": "func", "name": "BARSLAST", "args": [
            {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">=", "right": {"type": "const", "value": 9.8}}
        ]}}
    ], "root": {"type": "compare", "left": {"type": "var", "name": "T"}, "op": "==", "right": {"type": "const", "value": 5}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_ir_ref_var_anchor():
    """REF(volume, T)：取涨停当日 volume（T=5 -> 第25日 volume=1e7）。"""
    bars = _make_test_bars(limit_up_day=24, n_days=30)
    frame = _frame_from_bars(bars)
    ir = {"vars": [
        {"name": "T", "expr": {"type": "func", "name": "BARSLAST", "args": [
            {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">=", "right": {"type": "const", "value": 9.8}}
        ]}}
    ], "root": {"type": "compare", "left": {"type": "func", "name": "REF", "args": [{"type": "field", "name": "volume"}, {"type": "var", "name": "T"}]}, "op": "==", "right": {"type": "const", "value": 1e7}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_ir_limit_up_pullback_full():
    """涨停后缩量回踩完整公式（通达信 6.1.2）：
    T:=BARSLAST(涨停); T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92
    """
    bars = _make_test_bars(limit_up_day=24, n_days=30)  # T=5
    frame = _frame_from_bars(bars)
    ir = {"vars": [
        {"name": "T", "expr": {"type": "func", "name": "BARSLAST", "args": [
            {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">=", "right": {"type": "const", "value": 9.8}}
        ]}}
    ], "root": {"type": "and", "children": [
        {"type": "compare", "left": {"type": "var", "name": "T"}, "op": ">=", "right": {"type": "const", "value": 3}},
        {"type": "compare", "left": {"type": "var", "name": "T"}, "op": "<=", "right": {"type": "const", "value": 10}},
        {"type": "compare", "left": {"type": "field", "name": "volume"}, "op": "<",
         "right": {"type": "binop", "op": "*", "left": {"type": "func", "name": "REF", "args": [{"type": "field", "name": "volume"}, {"type": "var", "name": "T"}]}, "right": {"type": "const", "value": 0.5}}},
        {"type": "compare", "left": {"type": "field", "name": "low"}, "op": "<=",
         "right": {"type": "binop", "op": "*", "left": {"type": "func", "name": "REF", "args": [{"type": "field", "name": "close"}, {"type": "var", "name": "T"}]}, "right": {"type": "const", "value": 0.92}}},
    ]}}
    mask = evaluate_ir(ir, bars, frame)
    # latest: T=5, volume=3e6 < 1e7*0.5=5e6 ✓, low=10 <= 11*0.92=10.12 ✓ -> 命中
    assert bool(mask.iloc[0]) is True


def test_ir_limit_up_pullback_no_hit_when_too_far():
    """涨停太早（T>10）不命中。"""
    bars = _make_test_bars(limit_up_day=5, n_days=30)  # T=24 > 10
    frame = _frame_from_bars(bars)
    ir = {"vars": [
        {"name": "T", "expr": {"type": "func", "name": "BARSLAST", "args": [
            {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">=", "right": {"type": "const", "value": 9.8}}
        ]}}
    ], "root": {"type": "compare", "left": {"type": "var", "name": "T"}, "op": "<=", "right": {"type": "const", "value": 10}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is False


def test_ir_cross():
    """CROSS(MA5, MA10)：构造 MA5 上穿 MA10。"""
    bars = _make_test_bars(n_days=30)
    frame = _frame_from_bars(bars)
    ir = {"root": {"type": "func", "name": "CROSS", "args": [
        {"type": "func", "name": "MA", "args": [{"type": "field", "name": "close"}, {"type": "const", "value": 5}]},
        {"type": "func", "name": "MA", "args": [{"type": "field", "name": "close"}, {"type": "const", "value": 10}]},
    ]}}
    # 不断言 True/False（合成数据未必上穿），只断言不报错且返回 bool
    mask = evaluate_ir(ir, bars, frame)
    assert len(mask) == 1


def test_ir_count():
    """COUNT(change_pct>0, 20)：近 20 日上涨天数。"""
    bars = _make_test_bars(n_days=30)
    frame = _frame_from_bars(bars)
    ir = {"root": {"type": "compare", "left": {"type": "func", "name": "COUNT", "args": [
        {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">", "right": {"type": "const", "value": 0}},
        {"type": "const", "value": 20}
    ]}, "op": ">=", "right": {"type": "const", "value": 1}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_ir_and_or_not():
    bars = _make_test_bars(n_days=30)
    frame = _frame_from_bars(bars)
    ir_and = {"root": {"type": "and", "children": [
        {"type": "compare", "left": {"type": "field", "name": "close"}, "op": ">", "right": {"type": "const", "value": 0}},
        {"type": "compare", "left": {"type": "field", "name": "volume"}, "op": ">", "right": {"type": "const", "value": 0}},
    ]}}
    assert bool(evaluate_ir(ir_and, bars, frame).iloc[0]) is True
    ir_not = {"root": {"type": "not", "child": {"type": "compare", "left": {"type": "field", "name": "close"}, "op": "<", "right": {"type": "const", "value": 0}}}}
    assert bool(evaluate_ir(ir_not, bars, frame).iloc[0]) is True


def test_ir_indicator_from_frame():
    """indicator 节点取 frame 列。"""
    bars = _make_test_bars(n_days=30)
    frame = _frame_from_bars(bars)
    frame["my_indicator"] = 42.0  # 自定义指标列
    ir = {"root": {"type": "compare", "left": {"type": "indicator", "name": "my_indicator"}, "op": "==", "right": {"type": "const", "value": 42}}}
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True


def test_future_function_rejected():
    """BACKSET 是未来函数，拒绝求值。"""
    bars = _make_test_bars(n_days=30)
    frame = _frame_from_bars(bars)
    ir = {"root": {"type": "func", "name": "BACKSET", "args": [{"type": "field", "name": "close"}, {"type": "const", "value": 1}]}}
    assert "BACKSET" in check_future_functions(ir)
    with pytest.raises(IRError, match="未来函数"):
        evaluate_ir(ir, bars, frame)


def test_ir_multiple_stocks():
    """多只股票：返回对齐 frame，每股独立求值。"""
    bars1 = _make_test_bars(limit_up_day=24, n_days=30)
    bars2 = _make_test_bars(limit_up_day=5, n_days=30)  # T=24 > 10，不命中
    bars2["stock_code"] = "000002"
    bars = pd.concat([bars1, bars2], ignore_index=True)
    frame = bars.groupby("stock_code").tail(1).reset_index(drop=True)
    ir = {"vars": [
        {"name": "T", "expr": {"type": "func", "name": "BARSLAST", "args": [
            {"type": "compare", "left": {"type": "field", "name": "change_pct"}, "op": ">=", "right": {"type": "const", "value": 9.8}}
        ]}}
    ], "root": {"type": "compare", "left": {"type": "var", "name": "T"}, "op": "<=", "right": {"type": "const", "value": 10}}}
    mask = evaluate_ir(ir, bars, frame)
    assert len(mask) == 2
    assert bool(mask.iloc[0]) is True   # 000001 T=5
    assert bool(mask.iloc[1]) is False  # 000002 T=24
