"""CompositeGateway 单测：TuShare 主 + AKShare 备的降级逻辑。

验证：主源成功直返、主源失败返回空 + fallback_used 标记、NotImplementedError 降级、
AKShare 独有方法直接转发、__getattr__ 兜底转发。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.gateway_composite import CompositeGateway


class FakePrimary:
    """mock TushareGateway。"""

    def __init__(self) -> None:
        self.raise_daily = False
        self.raise_history_notimpl = False

    def fetch_daily_by_date(self, trade_date, *, qfq_baseline_adj=None):
        if self.raise_daily:
            raise RuntimeError("tushare down")
        return pd.DataFrame({"code": ["000725"], "close": [10.5]})

    def fetch_daily_basic_by_date(self, trade_date):
        return pd.DataFrame({"code": ["000725"], "pe": [20.0]})

    def fetch_stock_daily_history(self, symbol, start, end, adjust=""):
        if self.raise_history_notimpl:
            raise NotImplementedError
        return pd.DataFrame({"primary": [True]})

    def fetch_individual_realtime(self):
        raise NotImplementedError  # TuShare 无盘中实时

    def get_source_snapshot(self, key):
        return {}


class FakeFallback:
    """mock AkshareGateway。"""

    def __init__(self) -> None:
        self.sector_calls: list[str] = []

    def fetch_stock_daily_history(self, symbol, start, end, adjust=""):
        return pd.DataFrame({"fallback": [True]})

    def fetch_individual_realtime(self):
        return pd.DataFrame({"fallback_realtime": [True]})

    def fetch_sector_catalog(self, sector_type):
        self.sector_calls.append(sector_type)
        return ["半导体", "锂电"]

    def get_source_snapshot(self, key):
        return {}


def test_daily_by_date_primary_ok():
    gw = CompositeGateway(FakePrimary(), FakeFallback())
    df = gw.fetch_daily_by_date(date(2026, 7, 22))
    assert not df.empty
    assert gw.get_source_snapshot("daily_by_date")["fallback_used"] is False


def test_daily_by_date_primary_fails_returns_empty():
    p = FakePrimary()
    p.raise_daily = True
    gw = CompositeGateway(p, FakeFallback())
    df = gw.fetch_daily_by_date(date(2026, 7, 22))
    assert df.empty  # 批量方法主源失败返回空，调用方降级逐只
    snap = gw.get_source_snapshot("daily_by_date")
    assert snap["fallback_used"] is True
    assert "daily" in snap["degraded_fields"]


def test_stock_daily_history_primary_ok():
    gw = CompositeGateway(FakePrimary(), FakeFallback())
    df = gw.fetch_stock_daily_history("000725", "20260101", "20260131", "qfq")
    assert "primary" in df.columns


def test_stock_daily_history_notimpl_fallback():
    p = FakePrimary()
    p.raise_history_notimpl = True
    gw = CompositeGateway(p, FakeFallback())
    df = gw.fetch_stock_daily_history("000725", "20260101", "20260131", "qfq")
    assert "fallback" in df.columns


def test_individual_realtime_direct_fallback():
    gw = CompositeGateway(FakePrimary(), FakeFallback())
    df = gw.fetch_individual_realtime()  # TuShare 无 -> 直接 AKShare
    assert "fallback_realtime" in df.columns


def test_getattr_fallback_for_akshare_only_method():
    f = FakeFallback()
    gw = CompositeGateway(FakePrimary(), f)
    result = gw.fetch_sector_catalog("industry")  # primary 无此方法 -> __getattr__ -> fallback
    assert result == ["半导体", "锂电"]
    assert f.sector_calls == ["industry"]


def test_get_source_snapshot_delegates_to_primary():
    class PrimaryWithSnap(FakePrimary):
        def get_source_snapshot(self, key):
            return {"source_label": "tushare", "fallback_used": False}
    gw = CompositeGateway(PrimaryWithSnap(), FakeFallback())
    # 未被 CompositeGateway 显式 snapshot 的 key -> 委托 primary
    snap = gw.get_source_snapshot("stock_daily_history:000725")
    assert snap["source_label"] == "tushare"
