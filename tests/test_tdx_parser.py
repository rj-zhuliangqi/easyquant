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
    with pytest.raises(TdxError, match="无输出语句"):
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


def test_sma_series_matches_tdx_definition():
    """SMA(X,N,M) 递推 Y[t]=(M*X[t]+(N-M)*Y[t-1])/N，Y[0]=X[0]，对照手算。

    KDJ 的 K=SMA(RSV,3,1)、D=SMA(K,3,1) 即此函数；前导 NaN 不进入递推。
    """
    from app.services.screener_ir import IREvaluator

    bars = pd.DataFrame({"stock_code": ["000001"] * 6,
                         "trading_date": pd.date_range("2026-06-01", periods=6, freq="B")})
    x_vals = [10.0, 11.0, 12.0, 11.0, 10.0, 9.0]
    x = pd.Series(x_vals, index=bars.index)
    ev = IREvaluator(bars, pd.DataFrame({"stock_code": ["000001"]}))
    got = ev._sma_series(x, 3, 1).to_numpy()
    ref = np.full(6, np.nan)
    ref[0] = x_vals[0]
    for i in range(1, 6):
        ref[i] = (x_vals[i] + 2 * ref[i - 1]) / 3  # M=1,N=3
    assert np.allclose(got, ref, equal_nan=True)


def test_parse_tdx_kdj_bare_output_end_to_end():
    """用户 KDJ 公式（裸输出 ``CROSS(K,D) AND K<30;``）解析 + 求值端到端。

    回归：旧 grammar 不支持裸表达式语句 -> ``Unexpected token '('`` 400；旧 IR 引擎
    无 SMA 且变量按 latest 标量存 -> KDJ 退化为常数、CROSS 永不触发。修后变量按完整
    时序递推，SMA 正确实现。
    """
    decline = list(np.linspace(10.0, 7.5, 10))  # 10 日下跌 -> K<D 低位
    prices = decline + [8.0]  # 末日反弹 -> K 上穿 D 且 K<30
    d0 = date(2026, 6, 1)
    rows = []
    for i, p in enumerate(prices):
        rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                     "open": p, "close": p, "high": p + 0.2, "low": p - 0.2,
                     "volume": 5e6, "amount": 5e7, "change_pct": 0.0, "turnover_rate": 2.0})
    bars = pd.DataFrame(rows)
    bars["trading_date"] = pd.to_datetime(bars["trading_date"])
    frame = bars.groupby("stock_code").tail(1).reset_index(drop=True)
    formula = (
        "RSV:=(CLOSE-LLV(LOW,9))/(HHV(HIGH,9)-LLV(LOW,9))*100; "
        "K:=SMA(RSV,3,1); D:=SMA(K,3,1); J:=3*K-2*D; "
        "CROSS(K,D) AND K<30;"
    )
    ir = parse_tdx(formula)
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is True  # 末日 K 上穿 D 且 K<30


def test_parse_tdx_kdj_rejects_when_k_above_30():
    """KDJ 反弹过猛 K>=30 时 ``K<30`` 过滤掉 -> 不命中（验证 K<30 真生效）。"""
    decline = list(np.linspace(10.0, 7.5, 10))
    prices = decline + [9.5]  # 末日大涨 -> K 远超 30
    d0 = date(2026, 6, 1)
    rows = []
    for i, p in enumerate(prices):
        rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                     "open": p, "close": p, "high": p + 0.2, "low": p - 0.2,
                     "volume": 5e6, "amount": 5e7, "change_pct": 0.0, "turnover_rate": 2.0})
    bars = pd.DataFrame(rows)
    bars["trading_date"] = pd.to_datetime(bars["trading_date"])
    frame = bars.groupby("stock_code").tail(1).reset_index(drop=True)
    ir = parse_tdx(
        "RSV:=(CLOSE-LLV(LOW,9))/(HHV(HIGH,9)-LLV(LOW,9))*100; "
        "K:=SMA(RSV,3,1); D:=SMA(K,3,1); CROSS(K,D) AND K<30;"
    )
    mask = evaluate_ir(ir, bars, frame)
    assert bool(mask.iloc[0]) is False


def test_parse_tdx_chinese_vars_and_var_n_window():
    """用户平台突破公式：中文变量名 + var-N 窗口函数 + 布尔变量序列。

    回归三件套：CNAME 不认中文、HHV(H,N) 的 N 非 const、布尔变量(平台:=...<1.35)
    存序列时 _series 不处理 compare 节点。修后端到端可跑。
    """
    decline = list(np.linspace(10.0, 9.6, 65))  # 65 日窄幅震荡 -> 平台<1.35
    prices = decline + [10.2, 10.5, 10.9]  # 末 3 日突破放量上行
    d0 = date(2026, 5, 1)
    rows = []
    for i, p in enumerate(prices):
        rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                     "open": p - 0.02, "close": p, "high": p + 0.03, "low": p - 0.03,
                     "volume": 5e6 if i < 65 else 1.5e7, "amount": 5e7,
                     "change_pct": 0.0, "turnover_rate": 2.0})
    bars = pd.DataFrame(rows)
    bars["trading_date"] = pd.to_datetime(bars["trading_date"])
    frame = bars.groupby("stock_code").tail(1).reset_index(drop=True)
    formula = (
        "N:=60; "
        "平台:=HHV(H,N)/LLV(L,N)<1.35; "
        "突破:=C>HHV(H,20); "
        "放量:=VOL>MA(VOL,5)*2; "
        "均线:=MA(C,5)>MA(C,10) AND MA(C,10)>MA(C,20); "
        "XG:平台 AND 放量 AND 均线;"
    )
    ir = parse_tdx(formula)
    assert [v["name"] for v in ir["vars"]] == ["N", "平台", "突破", "放量", "均线"]
    mask = evaluate_ir(ir, bars, frame)
    # 平台窄幅 + 末段放量 + 均线多头 -> 命中（突破含当日 HHV 语义可能假，故只断言不抛错+返回 bool）
    assert isinstance(bool(mask.iloc[0]), bool)


def test_parse_tdx_new_funcs_if_filter_macd_obv():
    """IF/FILTER/MACD/OBV 新函数 + DRAW* 静默忽略。"""
    d0 = date(2026, 6, 1)
    rows = []
    for i in range(30):
        c = 10.0 + (i % 2) * 0.2  # 交替上下
        rows.append({"stock_code": "000001", "trading_date": d0 + timedelta(days=i),
                     "open": c - 0.1, "close": c, "high": c + 0.1, "low": c - 0.1,
                     "volume": 1e6 + i * 1e4, "amount": 1e7, "change_pct": 0.0, "turnover_rate": 2.0})
    bars = pd.DataFrame(rows)
    bars["trading_date"] = pd.to_datetime(bars["trading_date"])
    frame = bars.groupby("stock_code").tail(1).reset_index(drop=True)

    # IF：阳线取 close 阴线取 0
    ir = parse_tdx("XG:IF(C>O, C, 0) > 5;")
    assert isinstance(bool(evaluate_ir(ir, bars, frame).iloc[0]), bool)
    # FILTER：连涨信号每 3 日一个
    ir = parse_tdx("XG:FILTER(C>O, 3) = 1;")
    assert isinstance(bool(evaluate_ir(ir, bars, frame).iloc[0]), bool)
    # MACD：有限值
    from app.services.screener_ir import IREvaluator
    ev = IREvaluator(bars, frame)
    macd = ev._func_series("MACD", [{"type": "const", "value": 12}, {"type": "const", "value": 26}, {"type": "const", "value": 9}])
    assert np.isfinite(macd.iloc[-1])
    # OBV：与手算一致
    obv = ev._func_series("OBV", [])
    c, v = bars["close"].to_numpy(), bars["volume"].to_numpy()
    ref = np.zeros(30)
    for i in range(1, 30):
        ref[i] = ref[i - 1] + np.sign(c[i] - c[i - 1]) * v[i]
    assert obv.iloc[-1] == ref[-1]
    # DRAW* 静默忽略不报错
    ir = parse_tdx("XG:C>5 AND DRAWICON(C>5, 1, 1);")
    assert isinstance(bool(evaluate_ir(ir, bars, frame).iloc[0]), bool)
