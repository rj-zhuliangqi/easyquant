"""DailyEodService 单测：snapshot 聚合、OHLCV 边界、idempotent upsert、realtime merge。"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from app.models import IndividualStockSnapshot, StockRealtimeEod
from app.services.daily_eod import DailyEodService


def _seed_snapshots(session, rows: list[dict]) -> None:
    for r in rows:
        session.add(IndividualStockSnapshot(
            trading_date=r["trading_date"],
            captured_at=r["captured_at"],
            stock_code=r["stock_code"],
            stock_name=r.get("stock_name", ""),
            latest_price=r.get("latest_price"),
            change_percent=r.get("change_percent"),
            net_amount=r.get("net_amount"),
        ))
    session.commit()


# 1. 基本聚合：单只单日多 tick → 一行
def test_aggregate_single_stock_multi_tick(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 9, 31), "stock_code": "000001", "stock_name": "平安银行", "latest_price": 10.0, "net_amount": 1_000_000.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 10, 0), "stock_code": "000001", "stock_name": "平安银行", "latest_price": 10.2, "net_amount": 1_500_000.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 57), "stock_code": "000001", "stock_name": "平安银行", "latest_price": 10.5, "net_amount": 2_000_000.0},
    ])
    svc = DailyEodService()
    n = svc.aggregate_from_snapshots(db_session, date(2026, 5, 14))
    assert n == 1
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    assert row.stock_name == "平安银行"
    assert row.open == 10.0
    assert row.close == 10.5
    assert row.high == 10.5
    assert row.low == 10.0
    assert row.snapshot_count == 3


# 2. 开盘判定：09:30 之前不取（防御极端情况）
def test_open_skips_pre_open_ticks(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 9, 0), "stock_code": "000001", "latest_price": 9.5, "net_amount": 0.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 9, 31), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1_000_000.0},
    ])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    assert row.open == 10.0  # 09:31 那笔


# 3. 收盘判定：14:56–15:00 之间的最后一笔为 close
def test_close_picks_1456_1500_window(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 9, 31), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 13, 0), "stock_code": "000001", "latest_price": 10.3, "net_amount": 1.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 55), "stock_code": "000001", "latest_price": 10.4, "net_amount": 1.0},  # 14:55 不在窗口
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 58), "stock_code": "000001", "latest_price": 10.6, "net_amount": 1.0},  # 窗口内
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 59), "stock_code": "000001", "latest_price": 10.5, "net_amount": 1.0},  # 窗口内最后一笔
    ])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    assert row.close == 10.5


# 4. 收盘窗口外：全天最后一笔为 close（fallback）
def test_close_fallback_when_no_close_window(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 9, 31), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 0), "stock_code": "000001", "latest_price": 10.2, "net_amount": 1.0},
    ])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    assert row.close == 10.2  # fallback 到最后一笔


# 5. VWAP：净流入加权
def test_vwap_weighted_by_net_amount(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 10, 0), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1_000_000.0},
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 11, 0), "stock_code": "000001", "latest_price": 12.0, "net_amount": 3_000_000.0},
    ])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    # VWAP = (10*1M + 12*3M) / (1M + 3M) = 46M / 4M = 11.5
    assert abs(row.vwap - 11.5) < 1e-9


# 6. change_pct：基于上一交易日 close
def test_change_pct_uses_prev_close(db_session) -> None:
    # 先写前一日
    db_session.add(StockRealtimeEod(
        stock_code="000001", trading_date=date(2026, 5, 13),
        close=10.0, updated_at=datetime.now(),
    ))
    db_session.commit()
    # 当日
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 58), "stock_code": "000001", "latest_price": 11.0, "net_amount": 1.0},
    ])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001", trading_date=date(2026, 5, 14)).one()
    assert abs(row.change_pct - 10.0) < 1e-9  # (11-10)/10 * 100 = 10


# 7. 幂等：重跑同一日不增行
def test_idempotent_aggregate(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 58), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1.0},
    ])
    svc = DailyEodService()
    assert svc.aggregate_from_snapshots(db_session, date(2026, 5, 14)) == 1
    # 第二次 upsert
    assert svc.aggregate_from_snapshots(db_session, date(2026, 5, 14)) == 1
    rows = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").all()
    assert len(rows) == 1


# 8. 多只股票同时聚合
def test_multi_stock_aggregate(db_session) -> None:
    base_dt = datetime(2026, 5, 14, 14, 58)
    for code, name in [("000001", "平安"), ("000002", "万科A"), ("600000", "浦发")]:
        _seed_snapshots(db_session, [
            {"trading_date": date(2026, 5, 14), "captured_at": base_dt, "stock_code": code, "stock_name": name, "latest_price": 10.0, "net_amount": 1.0},
        ])
    n = DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    assert n == 3
    rows = db_session.query(StockRealtimeEod).all()
    assert {r.stock_code for r in rows} == {"000001", "000002", "600000"}


# 9. 空数据：返回 0，不报错
def test_empty_snapshots_returns_zero(db_session) -> None:
    n = DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14))
    assert n == 0
    assert db_session.query(StockRealtimeEod).count() == 0


# 10. realtime_frame 注入：合入 pe/pb
def test_realtime_frame_merges_extended_columns(db_session) -> None:
    _seed_snapshots(db_session, [
        {"trading_date": date(2026, 5, 14), "captured_at": datetime(2026, 5, 14, 14, 58), "stock_code": "000001", "latest_price": 10.0, "net_amount": 1.0},
    ])
    rt = pd.DataFrame([{
        "股票代码": "000001",
        "换手率": 1.5,
        "市盈率动": 8.5,
        "市净率": 0.8,
        "总市值": 200_000_000_000.0,
        "流通市值": 150_000_000_000.0,
    }])
    DailyEodService().aggregate_from_snapshots(db_session, date(2026, 5, 14), realtime_frame=rt)
    row = db_session.query(StockRealtimeEod).filter_by(stock_code="000001").one()
    assert row.pe_dynamic == 8.5
    assert row.pb == 0.8
    assert row.total_mv == 200_000_000_000.0
    assert row.float_mv == 150_000_000_000.0
    assert row.turnover_rate == 1.5


# 11. backfill_range 跨日 + 跳周末
def test_backfill_range_skips_weekends(db_session) -> None:
    # 5/15 是周五，5/16-5/17 周末跳过，5/18 周一
    for d in [date(2026, 5, 15), date(2026, 5, 18)]:
        _seed_snapshots(db_session, [
            {"trading_date": d, "captured_at": datetime.combine(d, datetime.min.time()).replace(hour=14, minute=58),
             "stock_code": "000001", "latest_price": 10.0, "net_amount": 1.0},
        ])
    result = DailyEodService().backfill_range(db_session, date(2026, 5, 15), date(2026, 5, 18))
    assert result["dates"] == 2
    assert result["rows"] == 2
