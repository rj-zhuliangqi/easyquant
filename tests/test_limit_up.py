"""limit_up 池加载层 TTL 缓存测试（B5）。"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.services.limit_up import LimitUpService


class _CountingGateway:
    """记录各 fetch_* 调用次数的 stub，返回空 DataFrame（normalize 后即空池）。"""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {
            "limit_up": 0,
            "previous": 0,
            "broken": 0,
            "strong": 0,
        }

    def fetch_limit_up_pool(self, *a, **kw):  # noqa: ANN001
        self.calls["limit_up"] += 1
        return pd.DataFrame()

    def fetch_previous_limit_up_pool(self, *a, **kw):  # noqa: ANN001
        self.calls["previous"] += 1
        return pd.DataFrame()

    def fetch_broken_limit_up_pool(self, *a, **kw):  # noqa: ANN001
        self.calls["broken"] += 1
        return pd.DataFrame()

    def fetch_strong_limit_up_pool(self, *a, **kw):  # noqa: ANN001
        self.calls["strong"] += 1
        return pd.DataFrame()


def test_pool_cache_hits_within_ttl() -> None:
    """TTL 内重复 get_summary 不应再打 gateway 的 fetch_*。"""
    gw = _CountingGateway()
    svc = LimitUpService(gateway=gw)
    td = date(2026, 7, 17)

    svc.get_summary(td, market_scope="all")
    first = dict(gw.calls)
    assert first["limit_up"] == 1, f"首次应调 1 次，实际 {first}"

    svc.get_summary(td, market_scope="all")
    second = dict(gw.calls)
    assert second["limit_up"] == 1, f"TTL 内应命中缓存，实际调 {second['limit_up']} 次"


def test_pool_cache_expires_after_ttl() -> None:
    """TTL 过期后应重新打 gateway。"""
    gw = _CountingGateway()
    svc = LimitUpService(gateway=gw)
    svc._pool_cache_ttl = 0  # 立即过期
    td = date(2026, 7, 17)

    svc.get_broken_pool(td, market_scope="all")
    assert gw.calls["broken"] == 1
    svc.get_broken_pool(td, market_scope="all")
    assert gw.calls["broken"] == 2, f"TTL=0 第二次应重打，实际 {gw.calls['broken']}"


def test_pool_cache_keys_isolate_by_date_and_scope() -> None:
    """不同 trading_date / market_scope 应分别缓存，互不串。"""
    gw = _CountingGateway()
    svc = LimitUpService(gateway=gw)
    td1 = date(2026, 7, 17)
    td2 = date(2026, 7, 16)

    svc.get_summary(td1, market_scope="all")
    svc.get_summary(td2, market_scope="all")  # 不同日期 -> 新请求
    svc.get_summary(td1, market_scope="mainboard")  # 不同 scope -> 新请求
    assert gw.calls["limit_up"] == 3, f"3 个不同 key 应各调 1 次，实际 {gw.calls['limit_up']}"
    # 重复同 key 应命中
    svc.get_summary(td1, market_scope="all")
    assert gw.calls["limit_up"] == 3, f"同 key 应命中缓存，实际 {gw.calls['limit_up']}"
