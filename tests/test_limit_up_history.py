"""LimitUpHistoryService + LimitUpIndicatorsService 单测。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import pytest

from app.models import StockLimitUpHistory, StockLimitUpIndicator
from app.services.limit_up_history import LimitUpHistoryService
from app.services.limit_up_indicators import LimitUpIndicatorsService


class FakeLimitUpGateway:
    """每个 pool 返回一个固定的 DataFrame（列名仿东财）。"""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}
        self.call_counts: dict[str, int] = {}

    def set_pool(self, pool: str, df: pd.DataFrame) -> None:
        self._frames[pool] = df

    def fetch_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        self.call_counts["limit_up"] = self.call_counts.get("limit_up", 0) + 1
        return self._frames.get("limit_up", pd.DataFrame()).copy()

    def fetch_broken_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        self.call_counts["broken"] = self.call_counts.get("broken", 0) + 1
        return self._frames.get("broken", pd.DataFrame()).copy()

    def fetch_strong_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        self.call_counts["strong"] = self.call_counts.get("strong", 0) + 1
        return self._frames.get("strong", pd.DataFrame()).copy()

    def fetch_previous_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        self.call_counts["previous"] = self.call_counts.get("previous", 0) + 1
        return self._frames.get("previous", pd.DataFrame()).copy()


def _make_limit_up_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """rows 中键用中文东财列名。所有 row 必须有相同 keys（缺则 None 填充）。"""
    if not rows:
        return pd.DataFrame()
    all_keys = sorted({k for r in rows for k in r.keys()})
    base: dict[str, list[Any]] = {k: [r.get(k) for r in rows] for k in all_keys}
    return pd.DataFrame(base)


# ---------- LimitUpHistoryService ----------

def test_refresh_writes_4_pools(db_session) -> None:
    gw = FakeLimitUpGateway()
    gw.set_pool("limit_up", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 2, "封板资金": 1_000_000.0, "首次封板时间": "10:30:00"},
    ]))
    gw.set_pool("broken", _make_limit_up_df([
        {"代码": "000002", "名称": "万科", "连板数": 1, "炸板次数": 1},
    ]))
    gw.set_pool("strong", _make_limit_up_df([
        {"代码": "000003", "名称": "茅台", "换手率": 5.0, "量比": 3.5},
    ]))
    gw.set_pool("previous", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 1},
    ]))

    # now_provider = 16:00 跳过时间门
    svc = LimitUpHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    result = svc.refresh_for_date(db_session, date(2026, 5, 14))
    assert result == {"limit_up": 1, "broken": 1, "strong": 1, "previous": 1}
    rows = db_session.query(StockLimitUpHistory).all()
    assert len(rows) == 4
    pools = {r.pool_type for r in rows}
    assert pools == {"limit_up", "broken", "strong", "previous"}


def test_refresh_pre_eod_bails(db_session) -> None:
    """15:30 之前调用直接 bail，不写库。"""
    gw = FakeLimitUpGateway()
    gw.set_pool("limit_up", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 1},
    ]))
    svc = LimitUpHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 5, 14, 14, 0, 0))
    result = svc.refresh_for_date(db_session, date(2026, 5, 14))
    assert result == {"limit_up": 0, "broken": 0, "strong": 0, "previous": 0}
    assert db_session.query(StockLimitUpHistory).count() == 0


def test_refresh_force_bypasses_timegate(db_session) -> None:
    gw = FakeLimitUpGateway()
    gw.set_pool("limit_up", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 1},
    ]))
    svc = LimitUpHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 5, 14, 10, 0, 0))
    result = svc.refresh_for_date(db_session, date(2026, 5, 14), force=True)
    assert result["limit_up"] == 1


def test_refresh_idempotent_replaces_same_pool(db_session) -> None:
    gw = FakeLimitUpGateway()
    gw.set_pool("limit_up", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 1},
    ]))
    svc = LimitUpHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    svc.refresh_for_date(db_session, date(2026, 5, 14))
    # 再跑一次（连板数变 2）
    gw.set_pool("limit_up", _make_limit_up_df([
        {"代码": "000001", "名称": "平安", "连板数": 2},
    ]))
    svc.refresh_for_date(db_session, date(2026, 5, 14))
    rows = db_session.query(StockLimitUpHistory).filter_by(pool_type="limit_up").all()
    assert len(rows) == 1  # 全替换
    assert rows[0].board_count == 2


def test_refresh_pool_failure_does_not_block_others(db_session) -> None:
    """limit_up 抛异常时，其他 3 个池仍能写。"""
    class BrokenGW(FakeLimitUpGateway):
        def fetch_limit_up_pool(self, date_str):  # noqa: D401
            raise RuntimeError("network")

        def fetch_strong_limit_up_pool(self, date_str):  # noqa: D401
            return self._frames.get("strong", pd.DataFrame()).copy()

    gw = BrokenGW()
    gw.set_pool("strong", _make_limit_up_df([{"代码": "000003", "名称": "X"}]))
    svc = LimitUpHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    result = svc.refresh_for_date(db_session, date(2026, 5, 14))
    assert result["limit_up"] == 0
    assert result["strong"] == 1
    assert result["broken"] == 0
    assert result["previous"] == 0


# ---------- LimitUpIndicatorsService ----------

def test_indicators_rebuild_aggregates_4_pools(db_session) -> None:
    """先写 stock_limit_up_history，再 rebuild → stock_limit_up_indicators。"""
    # 直接插入 4 池历史
    db_session.add_all([
        StockLimitUpHistory(trading_date=date(2026, 5, 14), stock_code="000001",
                            stock_name="平安", pool_type="limit_up",
                            board_count=3, sealed_amount=5_000_000.0,
                            captured_at=datetime.now()),
        StockLimitUpHistory(trading_date=date(2026, 5, 14), stock_code="000002",
                            stock_name="万科", pool_type="broken",
                            broken_board_count=1, captured_at=datetime.now()),
        StockLimitUpHistory(trading_date=date(2026, 5, 14), stock_code="000003",
                            stock_name="茅台", pool_type="strong",
                            captured_at=datetime.now()),
        StockLimitUpHistory(trading_date=date(2026, 5, 14), stock_code="000001",
                            stock_name="平安", pool_type="previous",
                            captured_at=datetime.now()),
    ])
    db_session.commit()

    n = LimitUpIndicatorsService().rebuild_for_date(db_session, date(2026, 5, 14))
    assert n == 3  # 3 只股票
    rows = {r.stock_code: r for r in db_session.query(StockLimitUpIndicator).all()}
    assert rows["000001"].limit_up_today == 1
    assert rows["000001"].consecutive_limit_up_days == 3
    assert abs(rows["000001"].sealed_amount - 5_000_000.0) < 1e-9
    assert rows["000002"].broken_today == 1
    assert rows["000002"].limit_up_today == 0
    assert rows["000003"].strong_pool == 1


def test_indicators_rebuild_idempotent(db_session) -> None:
    db_session.add(StockLimitUpHistory(
        trading_date=date(2026, 5, 14), stock_code="000001", stock_name="X",
        pool_type="limit_up", board_count=1, captured_at=datetime.now(),
    ))
    db_session.commit()
    svc = LimitUpIndicatorsService()
    assert svc.rebuild_for_date(db_session, date(2026, 5, 14)) == 1
    assert svc.rebuild_for_date(db_session, date(2026, 5, 14)) == 1
    rows = db_session.query(StockLimitUpIndicator).all()
    assert len(rows) == 1  # truncate + 重写


def test_indicators_empty_when_no_history(db_session) -> None:
    n = LimitUpIndicatorsService().rebuild_for_date(db_session, date(2026, 5, 14))
    assert n == 0
