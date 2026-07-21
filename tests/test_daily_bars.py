"""DailyBarsService 单测：universe 过滤、ensure_recent_bars 幂等、prune 窗口、
qfq 复权口径、互斥锁。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pytest

from app.models import IndividualStockSnapshot, StockDailyBar, StockFundFlowDaily
from app.services.daily_bars import DailyBarsService


class FakeGateway:
    """仅覆盖 daily_bars 用到的两个接口；adjust 透传被记录以便断言。"""

    def __init__(self) -> None:
        self.daily_calls: list[tuple[str, str, str, str]] = []
        self.flow_calls: list[tuple[str, str]] = []
        self._daily_frame = pd.DataFrame()
        self._flow_frame = pd.DataFrame()

    def set_daily(self, frame: pd.DataFrame) -> None:
        self._daily_frame = frame

    def set_flow(self, frame: pd.DataFrame) -> None:
        self._flow_frame = frame

    def fetch_stock_daily_history(self, symbol, start_date, end_date, adjust=""):
        self.daily_calls.append((symbol, start_date, end_date, adjust))
        return self._daily_frame.copy()

    def fetch_stock_fund_flow_history(self, stock, market):
        self.flow_calls.append((stock, market))
        return self._flow_frame.copy()


def _make_bars_frame(n_days: int = 5, start: date = date(2026, 5, 1)) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n_days, freq="B")
    rows = []
    base = 10.0
    for i, d in enumerate(dates):
        close = base + i * 0.1
        rows.append({
            "日期": d.date(),
            "开盘": close - 0.05,
            "收盘": close,
            "最高": close + 0.1,
            "最低": close - 0.1,
            "成交量": float(1_000_000 + i * 10_000),
            "成交额": float(100_000_000 + i * 1_000_000),
            "振幅": 1.5,
            "涨跌幅": 0.5,
            "涨跌额": 0.05,
            "换手率": 2.0,
        })
    return pd.DataFrame(rows)


def _make_flow_frame(n_days: int = 5, start: date = date(2026, 5, 1)) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n_days, freq="B")
    rows = []
    for i, d in enumerate(dates):
        rows.append({
            "日期": d.date(),
            "收盘价": 10.0,
            "涨跌幅": 0.5,
            "主力净流入-净额": float(1_000_000 + i * 100_000),
            "主力净流入-净占比": 5.0,
            "超大单净流入-净额": 500_000.0,
            "大单净流入-净额": 500_000.0,
        })
    return pd.DataFrame(rows)


# ---------------- universe 过滤 -----------------


def _seed_snapshots(session, captured_at: datetime, rows: list[dict]) -> None:
    for row in rows:
        session.add(IndividualStockSnapshot(
            trading_date=row["trading_date"],
            captured_at=captured_at,
            stock_code=row["code"],
            stock_name=row["name"],
            latest_price=row.get("price"),
            change_percent=row.get("change_pct"),
            net_amount=row.get("net_amount"),
        ))
    session.commit()


def test_universe_filters_st_bj_suspended_low_amount(db_session) -> None:
    captured_at = datetime(2026, 5, 14, 15, 0, 0)
    rows = [
        # 主板 + 高成交额 -> 保留
        {"trading_date": date(2026, 5, 14), "code": "000001", "name": "平安银行", "price": 10.0, "change_pct": 1.2, "net_amount": 200_000_000.0},
        # ST -> 剔除
        {"trading_date": date(2026, 5, 14), "code": "000002", "name": "*ST 某股", "price": 5.0, "change_pct": -2.0, "net_amount": 300_000_000.0},
        # 北交所（8 开头） -> 剔除
        {"trading_date": date(2026, 5, 14), "code": "830001", "name": "北交某股", "price": 7.0, "change_pct": 0.5, "net_amount": 300_000_000.0},
        # 停牌 (net_amount=0) -> 剔除
        {"trading_date": date(2026, 5, 14), "code": "000003", "name": "停牌股", "price": 9.0, "change_pct": 0.0, "net_amount": 0.0},
        # 低成交额 -> 剔除（min_amount=50_000_000）
        {"trading_date": date(2026, 5, 14), "code": "000004", "name": "小盘股", "price": 11.0, "change_pct": 0.3, "net_amount": 10_000_000.0},
    ]
    _seed_snapshots(db_session, captured_at, rows)

    service = DailyBarsService(gateway=FakeGateway(), now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    universe = service.get_universe(db_session, min_amount=50_000_000.0)

    codes = set(universe["code"].astype(str))
    assert codes == {"000001"}


def test_universe_empty_when_no_snapshots(db_session) -> None:
    service = DailyBarsService(gateway=FakeGateway(), now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    universe = service.get_universe(db_session)
    assert universe.empty


# ---------------- ensure_recent_bars 幂等 + qfq 守护 -----------------


def test_ensure_recent_bars_idempotent_and_uses_qfq(db_session) -> None:
    gateway = FakeGateway()
    gateway.set_daily(_make_bars_frame(n_days=5))
    service = DailyBarsService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))

    # 跑两次
    service.ensure_recent_bars(db_session, ["000001"], days=10)
    service.ensure_recent_bars(db_session, ["000001"], days=10)

    rows = db_session.query(StockDailyBar).filter_by(stock_code="000001").all()
    assert len(rows) == 5  # 幂等：无重复
    # qfq 守护：每次调用 adjust="qfq"
    assert all(call[3] == "qfq" for call in gateway.daily_calls)


def test_ensure_recent_bars_gap_detection_only_backfills_missing(db_session) -> None:
    """断点续跑：已存在的日期不重复插入（由 upsert 保证）。"""
    gateway = FakeGateway()
    gateway.set_daily(_make_bars_frame(n_days=5))
    service = DailyBarsService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))

    service.ensure_recent_bars(db_session, ["000001"], days=10)
    first_count = db_session.query(StockDailyBar).filter_by(stock_code="000001").count()

    # 第二次相同数据
    service.ensure_recent_bars(db_session, ["000001"], days=10)
    second_count = db_session.query(StockDailyBar).filter_by(stock_code="000001").count()

    assert first_count == second_count == 5


# ---------------- prune -----------------


def test_prune_old_bars_keeps_window(db_session) -> None:
    """prune_old_bars 删除早于 latest-keep_trading_days 的行。"""
    today = date(2026, 5, 14)
    # 注入 200 天历史
    for i in range(200):
        d = today - timedelta(days=199 - i)
        db_session.add(StockDailyBar(
            stock_code="000001",
            trading_date=d,
            open=10.0, close=10.0, high=10.0, low=10.0,
            volume=1e6, amount=1e8, change_pct=0.0, turnover_rate=1.0,
        ))
    db_session.commit()

    service = DailyBarsService(gateway=FakeGateway(), now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    deleted = service.prune_old_bars(db_session, keep_trading_days=120)
    remaining = db_session.query(StockDailyBar).filter_by(stock_code="000001").count()
    # cutoff = latest - 120 天；删除 trading_date < cutoff 的行（即索引 0..78 共 79 条）
    assert deleted == 79
    assert remaining == 121  # 200 - 79


# ---------------- 互斥锁 -----------------


def test_backfill_all_mutex_rejects_second_run(db_session) -> None:
    gateway = FakeGateway()
    gateway.set_daily(_make_bars_frame(n_days=3))
    gateway.set_flow(_make_flow_frame(n_days=3))
    # 准备 universe（一只股票）
    _seed_snapshots(db_session, datetime(2026, 5, 14, 15, 0, 0), [
        {"trading_date": date(2026, 5, 14), "code": "000001", "name": "测试", "price": 10.0, "change_pct": 1.0, "net_amount": 200_000_000.0},
    ])
    service = DailyBarsService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))

    # 模拟 running 状态
    service.progress.running = True
    result = service.backfill_all(db_session, code_limit=1)
    assert result["started"] is False
    assert result["already_running"] is True


# ---------------- coverage -----------------


def test_coverage_reports_counts(db_session) -> None:
    db_session.add(StockDailyBar(
        stock_code="000001", trading_date=date(2026, 5, 14),
        open=10.0, close=10.0, high=10.0, low=10.0,
        volume=1e6, amount=1e8, change_pct=0.0, turnover_rate=1.0,
    ))
    db_session.add(StockFundFlowDaily(
        stock_code="000001", trading_date=date(2026, 5, 14),
        main_net_amount=1e6, main_net_ratio=5.0, super_large_net=5e5, large_net=5e5,
    ))
    db_session.commit()

    service = DailyBarsService(gateway=FakeGateway())
    cov = service.coverage(db_session)
    assert cov["bar_rows"] == 1
    assert cov["flow_rows"] == 1
    assert cov["stock_count"] == 1
    assert cov["flow_stock_count"] == 1
    assert cov["latest_date"] == "2026-05-14"


# ---------------- backfill_all 完整路径 -----------------


def test_backfill_all_writes_bars_and_flow(db_session) -> None:
    gateway = FakeGateway()
    gateway.set_daily(_make_bars_frame(n_days=3))
    gateway.set_flow(_make_flow_frame(n_days=3))
    _seed_snapshots(db_session, datetime(2026, 5, 14, 15, 0, 0), [
        {"trading_date": date(2026, 5, 14), "code": "000001", "name": "测试", "price": 10.0, "change_pct": 1.0, "net_amount": 200_000_000.0},
    ])
    service = DailyBarsService(gateway=gateway, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))

    result = service.backfill_all(db_session, code_limit=1)
    assert result["started"] is True
    assert result["already_running"] is False
    # 写入日线
    bars = db_session.query(StockDailyBar).filter_by(stock_code="000001").all()
    assert len(bars) == 3
    # 写入资金流
    flows = db_session.query(StockFundFlowDaily).filter_by(stock_code="000001").all()
    assert len(flows) == 3
    # qfq 守护
    assert gateway.daily_calls[0][3] == "qfq"
