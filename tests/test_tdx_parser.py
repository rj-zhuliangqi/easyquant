"""TDX DSL 解析器单测（P2-1）：通达信公式 -> IR -> evaluate_ir 端到端。"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.screener_ir import evaluate_ir
from app.services.tdx_parser import TdxError, parse_tdx


def _make_test_bars(limit_up_day: int = 24, n_days: int = 30) -> pd.DataFrame:
    """合成 1 只股票 n_days 日。第 limit_up_day 日涨停，最后一日缩量回踩。"""
    d0 = date(2026, 6, 1)
    rows = []
    for i in range(n_days):
        if i == limit_up_day:
            rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                         "open": 10.5, "close": 11.0, "high": 11.0, "low": 10.5,
                         "volume": 1e7, "amount": 1e8, "change_pct": 10.0, "turnover_rate": 5.0})
        elif i == n_days - 1:
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


def test_parse_tdx_basic_structure():
    ir = parse_tdx("T:=BARSLAST(CHANGE_PCT>=9.8); XG:T>=3 AND T<=10;")
    assert "vars" in ir and "root" in ir
    assert ir["vars"][0]["name"] == "T"
    assert ir["root"]["type"] == "and"
    assert len(ir["root"]["children"]) == 2


def test_parse_tdx_field_mapping():
    """C/O/H/L/V/AMOUNT/CHANGE_PCT 字段映射。"""
    ir = parse_tdx("XG:C>O AND V>1000 AND CHANGE_PCT>=9.8;")
    root = ir["root"]
    # and([close>open, volume>1000, change_pct>=9.8])
    assert root["type"] == "and"
    assert root["children"][0]["left"]["name"] == "close"
    assert root["children"][0]["right"]["name"] == "open"
    assert root["children"][1]["left"]["name"] == "volume"
    assert root["children"][2]["left"]["name"] == "change_pct"


def test_parse_tdx_eq_op():
    """通达信 = 转 IR ==。"""
    ir = parse_tdx("XG:C=10;")
    assert ir["root"]["op"] == "=="


def test_parse_tdx_between():
    """BETWEEN(T,3,10) -> T>=3 AND T<=10。"""
    ir = parse_tdx("T:=BARSLAST(CHANGE_PCT>=9.8); XG:BETWEEN(T,3,10);")
    root = ir["root"]
    assert root["type"] == "and"
    assert root["children"][0]["op"] == ">="
    assert root["children"][1]["op"] == "<="


def test_parse_tdx_full_pullback_end_to_end():
    """完整涨停后缩量回踩公式 + evaluate_ir 端到端选中。"""
    bars = _make_test_bars(limit_up_day=24, n_days=30)
    frame = _frame_from_bars(bars)
    formula = (
        "T:=BARSLAST(CHANGE_PCT>=9.8); "
        "XG:T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92;"
    )
    ir = parse_tdx(formula)
    mask = evaluate_ir(ir, bars, frame)
    # latest: T=5, volume=3e6 < 1e7*0.5=5e6, low=10 <= 11*0.92=10.12 -> 命中
    assert bool(mask.iloc[0]) is True


def test_parse_tdx_cross_macd():
    """CROSS + EMA 函数解析（MACD 金叉风格）。"""
    ir = parse_tdx("XG:CROSS(EMA(C,12), EMA(C,26));")
    root = ir["root"]
    assert root["type"] == "func"
    assert root["name"] == "CROSS"
    assert root["args"][0]["name"] == "EMA"


def test_parse_tdx_no_output_error():
    with pytest.raises(TdxError, match="无 XG"):
        parse_tdx("T:=BARSLAST(CHANGE_PCT>=9.8);")


def test_parse_tdx_future_function_rejected():
    with pytest.raises(TdxError, match="未来函数"):
        parse_tdx("XG:BACKSET(C>O, 1);")


def test_parse_tdx_syntax_error():
    with pytest.raises(TdxError, match="解析失败"):
        parse_tdx("XG:C>5")  # 缺分号


def test_parse_tdx_empty():
    with pytest.raises(TdxError, match="为空"):
        parse_tdx("   ")
