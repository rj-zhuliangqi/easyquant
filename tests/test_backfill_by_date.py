"""DailyBarsService.backfill_by_date 单测：按日期批量入库 4 表 + turnover 回填 +
main_net_ratio 自算 + 200 行 chunk + 无网关降级。

用 FakeTushareGateway（返回已换算单位的 DataFrame，与 TushareGateway 输出格式一致）
+ db_session（in-memory SQLite，create_all 建全部表）。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.models import StockDailyBar, StockDailyBasic, StockFundFlowDaily, StkLimitDaily
from app.services.daily_bars import DailyBarsService


class FakeTushareGateway:
    """mock TushareGateway：返回固定 DataFrame（已换算单位，元/股）。"""

    def __init__(self, *, daily=None, basic=None, flow=None) -> None:
        self._daily = daily
        self._basic = basic
        self._flow = flow

    def fetch_daily_by_date(self, trade_date, *, qfq_baseline_adj=None):
        if self._daily is not None:
            return self._daily
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "code": ["000725", "600519"],
            "trade_date": ["20260722", "20260722"],
            "open": [10.0, 1500.0],
            "close": [10.5, 1510.0],
            "high": [10.8, 1520.0],
            "low": [9.9, 1490.0],
            "volume": [1e7, 5e5],  # 股
            "amount": [5e7, 8e6],  # 元
            "change_pct": [2.94, 0.33],
            "adj_factor": [1.0, 1.0],
            "up_limit": [11.22, 1655.0],
            "down_limit": [9.18, 1355.0],
        })

    def fetch_daily_basic_by_date(self, trade_date):
        if self._basic is not None:
            return self._basic
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "code": ["000725", "600519"],
            "trade_date": ["20260722", "20260722"],
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
            "total_mv": [1e10, 1e11],
            "circ_mv": [1e10, 1e11],
            "total_share": [1e8, 1.25e8],
            "float_share": [1e8, 1e8],
            "free_share": [1e8, 1e8],
        })

    def fetch_fund_flow_by_date(self, trade_date):
        if self._flow is not None:
            return self._flow
        return pd.DataFrame({
            "ts_code": ["000725.SZ", "600519.SH"],
            "code": ["000725", "600519"],
            "trade_date": ["20260722", "20260722"],
            "main_net_amount": [1e6, -2e6],  # 元
            "main_net_ratio": [None, None],
            "super_large_net": [1e6, -2e6],
            "large_net": [1e6, 0.0],
        })


def test_backfill_by_date_four_tables(db_session):
    gw = FakeTushareGateway()
    svc = DailyBarsService(gateway=None, tushare_gateway=gw)
    stats = svc.backfill_by_date(db_session, date(2026, 7, 22))
    assert stats == {"date": "20260722", "bars": 2, "basic": 2, "flow": 2, "limit": 2}

    # stock_daily_bars：close/volume + turnover_rate 从 daily_basic 回填
    bars = db_session.query(StockDailyBar).all()
    assert len(bars) == 2
    b = next(b for b in bars if b.stock_code == "000725")
    assert b.close == pytest.approx(10.5)
    assert b.volume == pytest.approx(1e7)
    assert b.amount == pytest.approx(5e7)
    assert b.turnover_rate == pytest.approx(1.5)  # 回填自 daily_basic

    # stock_daily_basic
    basics = db_session.query(StockDailyBasic).all()
    assert len(basics) == 2
    bs0 = next(b for b in basics if b.stock_code == "000725")
    assert bs0.pe == pytest.approx(20.0)
    assert bs0.pe_ttm == pytest.approx(19.0)
    assert bs0.total_mv == pytest.approx(1e10)
    assert bs0.volume_ratio == pytest.approx(1.2)

    # stock_fund_flow_daily：main_net_ratio 自算 = main_net/amount*100 = 1e6/5e7*100 = 2.0
    flows = db_session.query(StockFundFlowDaily).all()
    assert len(flows) == 2
    f = next(f for f in flows if f.stock_code == "000725")
    assert f.main_net_amount == pytest.approx(1e6)
    assert f.main_net_ratio == pytest.approx(2.0)
    assert f.super_large_net == pytest.approx(1e6)

    # stk_limit_daily
    lims = db_session.query(StkLimitDaily).all()
    assert len(lims) == 2
    assert lims[0].up_limit == pytest.approx(11.22)
    assert lims[0].down_limit == pytest.approx(9.18)


def test_backfill_by_date_chunk_200(db_session):
    """250 行应分 2 chunk（200+50）入库，验证 chunk 边界不丢行。"""
    n = 250
    codes = [f"{i:06d}" for i in range(n)]
    daily = pd.DataFrame({
        "ts_code": [f"{c}.SZ" for c in codes],
        "code": codes,
        "trade_date": ["20260722"] * n,
        "open": [10.0] * n, "close": [10.5] * n, "high": [10.8] * n, "low": [9.9] * n,
        "volume": [1e6] * n, "amount": [1e7] * n, "change_pct": [1.0] * n,
        "adj_factor": [1.0] * n, "up_limit": [11.0] * n, "down_limit": [9.0] * n,
    })
    gw = FakeTushareGateway(daily=daily, basic=pd.DataFrame(), flow=pd.DataFrame())
    svc = DailyBarsService(gateway=None, tushare_gateway=gw)
    stats = svc.backfill_by_date(db_session, date(2026, 7, 22))
    assert stats["bars"] == n
    assert stats["limit"] == n
    assert db_session.query(StockDailyBar).count() == n


def test_backfill_by_date_no_gateway(db_session):
    svc = DailyBarsService(gateway=None)  # 无 tushare_gateway
    with pytest.raises(RuntimeError, match="TushareGateway"):
        svc.backfill_by_date(db_session, date(2026, 7, 22))


def test_backfill_by_date_empty(db_session):
    """TuShare 返回空（宕机/限流）时 stats 全 0，不报错。"""
    empty = pd.DataFrame()
    gw = FakeTushareGateway(daily=empty, basic=empty, flow=empty)
    svc = DailyBarsService(gateway=None, tushare_gateway=gw)
    stats = svc.backfill_by_date(db_session, date(2026, 7, 22))
    assert stats["bars"] == 0
    assert stats["basic"] == 0
    assert stats["flow"] == 0
    assert stats["limit"] == 0


def test_backfill_by_date_idempotent(db_session):
    """同一日期重复回补不产生重复行（upsert）。"""
    gw = FakeTushareGateway()
    svc = DailyBarsService(gateway=None, tushare_gateway=gw)
    svc.backfill_by_date(db_session, date(2026, 7, 22))
    svc.backfill_by_date(db_session, date(2026, 7, 22))
    assert db_session.query(StockDailyBar).count() == 2
    assert db_session.query(StockDailyBasic).count() == 2
