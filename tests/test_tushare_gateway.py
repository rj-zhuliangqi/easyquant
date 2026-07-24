"""TushareGateway 单测：用 fake pro 注入，不真调 TuShare API。

重点验证：单位换算（vol/amount/市值/moneyflow）、列契约、龙虎榜机构席位重建、qfq 复权、
空响应降级、不可用接口 raise NotImplementedError。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.tushare_client import (
    TushareGateway,
    _from_ts_code,
    _index_symbol_to_ts,
    _to_trade_date_str,
    _to_ts_code,
)


class FakePro:
    """mock TuShare pro_api：返回固定 DataFrame，记录调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def daily(self, trade_date=None, **kw):
        self.calls.append(("daily", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "trade_date": [trade_date, trade_date],
            "open": [10.0, 1500.0],
            "close": [10.5, 1510.0],
            "high": [10.8, 1520.0],
            "low": [9.9, 1490.0],
            "pre_close": [10.2, 1505.0],
            "change": [0.3, 5.0],
            "pct_chg": [2.94, 0.33],
            "vol": [100000.0, 5000.0],  # 手
            "amount": [50000.0, 8000.0],  # 千元
        })

    def adj_factor(self, trade_date=None, **kw):
        self.calls.append(("adj_factor", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "trade_date": [trade_date, trade_date],
            "adj_factor": [1.0, 1.0],
        })

    def stk_limit(self, trade_date=None, **kw):
        self.calls.append(("stk_limit", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "trade_date": [trade_date, trade_date],
            "up_limit": [11.22, 1655.0],
            "down_limit": [9.18, 1355.0],
        })

    def daily_basic(self, trade_date=None, **kw):
        self.calls.append(("daily_basic", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "trade_date": [trade_date, trade_date],
            "close": [10.5, 1510.0],
            "turnover_rate": [1.5, 0.3],
            "turnover_rate_f": [1.6, 0.35],
            "volume_ratio": [1.2, 0.8],
            "pe": [20.0, 30.0],
            "pe_ttm": [19.0, 28.0],
            "pb": [3.0, 10.0],
            "ps": [2.0, 15.0],
            "ps_ttm": [1.9, 14.0],
            "dv_ratio": [1.0, 0.5],
            "dv_ttm": [1.1, 0.55],
            "total_share": [1e8, 1.25e8],
            "float_share": [1e8, 1e8],
            "free_share": [1e8, 1e8],
            "total_mv": [1e6, 1e7],  # 万元
            "circ_mv": [1e6, 1e7],  # 万元
        })

    def moneyflow(self, trade_date=None, **kw):
        self.calls.append(("moneyflow", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "trade_date": [trade_date, trade_date],
            "net_mf_amount": [100.0, -200.0],  # 万元
            "buy_elg_amount": [300.0, 100.0],
            "sell_elg_amount": [200.0, 300.0],
            "buy_lg_amount": [400.0, 200.0],
            "sell_lg_amount": [300.0, 200.0],
        })

    def top_list(self, trade_date=None, **kw):
        self.calls.append(("top_list", {"trade_date": trade_date}))
        return pd.DataFrame({
            "ts_code": ["000725.SZ"],
            "trade_date": [trade_date],
            "name": ["京东方A"],
            "close": [10.5],
            "pct_change": [9.98],
            "turnover_rate": [5.0],
            "amount": [1e9],
            "l_buy": [5e8],
            "l_sell": [3e8],
            "l_amount": [8e8],
            "net_amount": [2e8],
            "net_rate": [20.0],
            "reason": ["日涨幅偏离值达到7%"],
        })

    def top_inst(self, trade_date=None, **kw):
        self.calls.append(("top_inst", {"trade_date": trade_date}))
        # 000725.SZ 三行：机构专用买、机构专用卖、深股通专用买（不计机构）
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "000725.SZ", "000725.SZ"],
            "trade_date": [trade_date, trade_date, trade_date],
            "exalter": ["机构专用", "机构专用", "深股通专用"],
            "buy": [1e8, 0, 5e7],
            "sell": [0, 8e7, 0],
            "net_buy": [1e8, -8e7, 5e7],
            "side": ["0", "1", "0"],  # 0 买 1 卖
            "reason": ["日涨幅偏离值达到7%"] * 3,
        })

    def stock_basic(self, **kw):
        self.calls.append(("stock_basic", kw))
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "symbol": ["000725", "600519"],
            "name": ["京东方A", "贵州茅台"],
            "area": ["北京", "贵州"],
            "industry": ["元器件", "白酒"],
            "cnspell": ["JDF", "GZMT"],
            "market": ["主板", "主板"],
            "list_date": ["20010801", "20010827"],
        })

    def index_daily(self, ts_code=None, start_date=None, end_date=None, **kw):
        self.calls.append(("index_daily", {"ts_code": ts_code}))
        return pd.DataFrame({
            "ts_code": [ts_code],
            "trade_date": ["20260722"],
            "close": [3000.0],
            "open": [2990.0],
            "high": [3010.0],
            "low": [2980.0],
            "vol": [1e8],
            "amount": [1e9],
        })


@pytest.fixture
def gw():
    return TushareGateway(token="fake-token", pro=FakePro())


# ---------------- 工具函数 ----------------


def test_to_ts_code():
    assert _to_ts_code("000725") == "000725.SZ"
    assert _to_ts_code("600519") == "600519.SH"
    assert _to_ts_code("688008") == "688008.SH"
    assert _to_ts_code("300750") == "300750.SZ"
    assert _to_ts_code("830799") == "830799.BJ"


def test_from_ts_code():
    assert _from_ts_code("000725.SZ") == "000725"
    assert _from_ts_code("600519.SH") == "600519"


def test_to_trade_date_str():
    assert _to_trade_date_str(date(2026, 7, 22)) == "20260722"
    assert _to_trade_date_str("2026-07-22") == "20260722"
    assert _to_trade_date_str("20260722") == "20260722"
    assert _to_trade_date_str(None) == ""


def test_index_symbol_to_ts():
    assert _index_symbol_to_ts("sh000001") == "000001.SH"
    assert _index_symbol_to_ts("sz399001") == "399001.SZ"


# ---------------- fetch_daily_by_date：单位换算 + 列契约 + qfq ----------------


def test_fetch_daily_by_date_unit_conversion(gw):
    df = gw.fetch_daily_by_date(date(2026, 7, 22))
    assert len(df) == 2
    row = df[df["code"] == "000725"].iloc[0]
    # vol 手 -> 股 ×100
    assert row["volume"] == pytest.approx(100000.0 * 100)
    # amount 千元 -> 元 ×1000
    assert row["amount"] == pytest.approx(50000.0 * 1000)
    assert row["change_pct"] == pytest.approx(2.94)
    # 列契约
    for col in ("ts_code", "code", "trade_date", "open", "close", "high", "low",
                "volume", "amount", "change_pct", "adj_factor", "up_limit", "down_limit"):
        assert col in df.columns
    assert row["up_limit"] == pytest.approx(11.22)
    assert row["adj_factor"] == pytest.approx(1.0)
    # 默认 raw（最新日 qfq=raw）
    assert row["close"] == pytest.approx(10.5)
    snap = gw.get_source_snapshot("daily_by_date")
    assert snap["source_label"] == "tushare"


def test_fetch_daily_by_date_qfq_baseline(gw):
    # baseline adj=2.0, 当日 adj=1.0 -> ratio=0.5, qfq close=10.5*0.5=5.25
    df = gw.fetch_daily_by_date(date(2026, 7, 22), qfq_baseline_adj={"000725.SZ": 2.0, "600519.SH": 1.0})
    row = df[df["code"] == "000725"].iloc[0]
    assert row["close"] == pytest.approx(10.5 * 0.5)
    assert row["open"] == pytest.approx(10.0 * 0.5)
    # 600519 baseline=1.0=adj, ratio=1.0, 不变
    row2 = df[df["code"] == "600519"].iloc[0]
    assert row2["close"] == pytest.approx(1510.0)


# ---------------- fetch_daily_basic_by_date：市值换算 ----------------


def test_fetch_daily_basic_by_date_mv_conversion(gw):
    df = gw.fetch_daily_basic_by_date(date(2026, 7, 22))
    assert len(df) == 2
    row = df[df["code"] == "000725"].iloc[0]
    # total_mv 万元 -> 元 ×10000
    assert row["total_mv"] == pytest.approx(1e6 * 10000)
    assert row["circ_mv"] == pytest.approx(1e6 * 10000)
    for col in ("pe", "pe_ttm", "pb", "ps", "turnover_rate", "volume_ratio", "dv_ratio"):
        assert col in df.columns


# ---------------- fetch_fund_flow_by_date：资金流换算 ----------------


def test_fetch_fund_flow_by_date_conversion(gw):
    df = gw.fetch_fund_flow_by_date(date(2026, 7, 22))
    assert len(df) == 2
    row = df[df["code"] == "000725"].iloc[0]
    # net_mf_amount 万元 -> 元 ×10000
    assert row["main_net_amount"] == pytest.approx(100.0 * 10000)
    # 超大单净额 = (buy_elg - sell_elg) ×10000 = (300-200)*10000
    assert row["super_large_net"] == pytest.approx((300.0 - 200.0) * 10000)
    # 大单净额 = (buy_lg - sell_lg) ×10000 = (400-300)*10000
    assert row["large_net"] == pytest.approx((400.0 - 300.0) * 10000)
    # 600519 主力净流出
    row2 = df[df["code"] == "600519"].iloc[0]
    assert row2["main_net_amount"] == pytest.approx(-200.0 * 10000)


# ---------------- fetch_lhb_by_date：机构席位重建 ----------------


def test_fetch_lhb_by_date_inst_seats(gw):
    df = gw.fetch_lhb_by_date(date(2026, 7, 22))
    assert len(df) == 1
    row = df.iloc[0]
    # 机构专用 side=0 买 -> inst_buy_count=1；机构专用 side=1 卖 -> inst_sell_count=1
    # 深股通专用 side=0 买但不含"机构" -> 不计
    assert row["inst_buy_count"] == 1
    assert row["inst_sell_count"] == 1
    assert row["inst_net_count"] == 0
    assert row["net_amount"] == pytest.approx(2e8)
    assert row["reason"] == "日涨幅偏离值达到7%"


# ---------------- fetch_stock_basic：缓存 + 列 ----------------


def test_fetch_stock_basic_cache(gw):
    df1 = gw.fetch_stock_basic()
    assert len(df1) == 2
    assert "code" in df1.columns
    assert df1.iloc[0]["code"] == "000725"
    # 第二次走缓存（不再调 pro）
    n_calls = len([c for c in gw._pro.calls if c[0] == "stock_basic"])
    df2 = gw.fetch_stock_basic()
    n_calls_after = len([c for c in gw._pro.calls if c[0] == "stock_basic"])
    assert n_calls_after == n_calls  # 缓存命中，未增加调用


# ---------------- fetch_stk_limit_by_date ----------------


def test_fetch_stk_limit_by_date(gw):
    df = gw.fetch_stk_limit_by_date(date(2026, 7, 22))
    assert len(df) == 2
    assert df.iloc[0]["up_limit"] == pytest.approx(11.22)
    for col in ("ts_code", "code", "trade_date", "up_limit", "down_limit"):
        assert col in df.columns


# ---------------- 不可用接口 ----------------


def test_fetch_individual_realtime_not_implemented(gw):
    with pytest.raises(NotImplementedError):
        gw.fetch_individual_realtime()


def test_fetch_limit_up_pool_not_implemented(gw):
    with pytest.raises(NotImplementedError):
        gw.fetch_limit_up_pool("20260722")


# ---------------- 空响应降级 ----------------


class EmptyPro(FakePro):
    def daily(self, trade_date=None, **kw):
        return pd.DataFrame()

    def adj_factor(self, trade_date=None, **kw):
        return pd.DataFrame()

    def stk_limit(self, trade_date=None, **kw):
        return pd.DataFrame()


def test_fetch_daily_by_date_empty_degraded():
    gw = TushareGateway(token="fake", pro=EmptyPro())
    df = gw.fetch_daily_by_date(date(2026, 7, 22))
    assert df.empty
    snap = gw.get_source_snapshot("daily_by_date")
    assert "daily" in snap["degraded_fields"]


# ---------------- token 缺失 ----------------


def test_tushare_gateway_no_token_no_pro(monkeypatch):
    monkeypatch.setattr("app.config.TUSHARE_TOKEN", "")
    with pytest.raises(ValueError, match="EQ_TUSHARE_TOKEN"):
        TushareGateway()
