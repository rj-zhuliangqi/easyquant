"""LhbHistoryService 单测 + 选股器龙虎榜指标加载测试。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from app.models import StockLhbDetail
from app.services.lhb_history import LhbHistoryService


class FakeLhbGateway:
    """返回固定的龙虎榜 DataFrame（列名仿 fetch_lhb_detail 输出）。"""

    def __init__(self) -> None:
        self._frame: pd.DataFrame = pd.DataFrame()
        self.calls = 0

    def set_frame(self, df: pd.DataFrame) -> None:
        self._frame = df

    def fetch_lhb_detail(self, date_str: str) -> pd.DataFrame:
        self.calls += 1
        return self._frame.copy()


def _lhb_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ---------- LhbHistoryService ----------

def test_refresh_writes_rows(db_session) -> None:
    gw = FakeLhbGateway()
    gw.set_frame(_lhb_df([
        {"股票代码": "000767", "名称": "晋控电力", "上榜原因": "涨幅偏离20%",
         "解读": "3家机构买入", "龙虎榜净买额": -86652134.95,
         "机构买入席位": 3, "机构卖出席位": 0, "机构净席位": 3},
        {"股票代码": "000078", "名称": "ST海王", "上榜原因": "跌幅偏离7%",
         "解读": "西藏自治区资金卖出", "龙虎榜净买额": -9138838.40,
         "机构买入席位": 0, "机构卖出席位": 0, "机构净席位": 0},
    ]))
    svc = LhbHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 7, 22, 17, 30, 0))
    n = svc.refresh_for_date(db_session, date(2026, 7, 22))
    assert n == 2
    rows = db_session.query(StockLhbDetail).all()
    assert len(rows) == 2
    by_code = {r.stock_code: r for r in rows}
    assert by_code["000767"].inst_net_count == 3
    assert by_code["000078"].inst_net_count == 0


def test_refresh_pre_17_bails(db_session) -> None:
    """17:00 之前调用直接 bail，不写库。"""
    gw = FakeLhbGateway()
    gw.set_frame(_lhb_df([{"股票代码": "000767", "名称": "X", "上榜原因": "r"}]))
    svc = LhbHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 7, 22, 16, 0, 0))
    n = svc.refresh_for_date(db_session, date(2026, 7, 22))
    assert n == 0
    assert db_session.query(StockLhbDetail).count() == 0
    assert gw.calls == 0  # 时间门内不调 gateway


def test_refresh_force_bypasses_timegate(db_session) -> None:
    gw = FakeLhbGateway()
    gw.set_frame(_lhb_df([{"股票代码": "000767", "名称": "X", "上榜原因": "r"}]))
    svc = LhbHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 7, 22, 9, 0, 0))
    n = svc.refresh_for_date(db_session, date(2026, 7, 22), force=True)
    assert n == 1


def test_refresh_idempotent_replaces_same_date(db_session) -> None:
    """同日重跑全替换，不留旧记录。"""
    gw = FakeLhbGateway()
    gw.set_frame(_lhb_df([
        {"股票代码": "000767", "名称": "X", "上榜原因": "r1", "机构净席位": 1},
    ]))
    svc = LhbHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 7, 22, 17, 30, 0))
    svc.refresh_for_date(db_session, date(2026, 7, 22))
    # 再跑：换成另一只票
    gw.set_frame(_lhb_df([
        {"股票代码": "000001", "名称": "Y", "上榜原因": "r2", "机构净席位": 2},
    ]))
    svc.refresh_for_date(db_session, date(2026, 7, 22))
    rows = db_session.query(StockLhbDetail).all()
    assert len(rows) == 1
    assert rows[0].stock_code == "000001"


def test_refresh_keeps_multiple_reasons_per_stock(db_session) -> None:
    """一只票多个上榜原因 -> 多行保留（唯一约束含 reason）。"""
    gw = FakeLhbGateway()
    gw.set_frame(_lhb_df([
        {"股票代码": "000078", "名称": "ST海王", "上榜原因": "日跌幅偏离7%", "机构净席位": 0},
        {"股票代码": "000078", "名称": "ST海王", "上榜原因": "三日跌幅累计20%", "机构净席位": 0},
    ]))
    svc = LhbHistoryService(gateway=gw, now_provider=lambda: datetime(2026, 7, 22, 17, 30, 0))
    n = svc.refresh_for_date(db_session, date(2026, 7, 22))
    assert n == 2
    rows = db_session.query(StockLhbDetail).filter_by(stock_code="000078").all()
    assert len(rows) == 2


def test_refresh_gateway_exception_returns_zero(db_session) -> None:
    class BrokenGW(FakeLhbGateway):
        def fetch_lhb_detail(self, date_str):  # noqa: D401
            raise RuntimeError("network")

    svc = LhbHistoryService(gateway=BrokenGW(), now_provider=lambda: datetime(2026, 7, 22, 17, 30, 0))
    n = svc.refresh_for_date(db_session, date(2026, 7, 22))
    assert n == 0


def test_prune_old(db_session) -> None:
    db_session.add_all([
        StockLhbDetail(trading_date=date(2025, 1, 1), stock_code="000001", reason="r"),
        StockLhbDetail(trading_date=date(2026, 7, 22), stock_code="000002", reason="r"),
    ])
    db_session.commit()
    svc = LhbHistoryService()
    deleted = svc.prune_old(db_session, keep_trading_days=250)
    assert deleted == 1
    remaining = db_session.query(StockLhbDetail).all()
    assert len(remaining) == 1
    assert remaining[0].stock_code == "000002"


# ---------- 选股器龙虎榜指标加载 ----------

def test_screener_loads_lhb_indicators(db_session) -> None:
    """_load_lhb_indicators 按 stock_code 聚合 net_buy/inst_net_count，lhb_today=1。"""
    from app.services.screener import _load_lhb_indicators

    db_session.add_all([
        StockLhbDetail(trading_date=date(2026, 7, 22), stock_code="000767",
                       reason="r1", net_buy=1000.0, inst_net_count=3),
        StockLhbDetail(trading_date=date(2026, 7, 22), stock_code="000767",
                       reason="r2", net_buy=500.0, inst_net_count=-1),
        StockLhbDetail(trading_date=date(2026, 7, 22), stock_code="000001",
                       reason="r1", net_buy=-200.0, inst_net_count=0),
    ])
    db_session.commit()

    df = _load_lhb_indicators(db_session, ["000767", "000001", "000002"], date(2026, 7, 22))
    rec = df.set_index("stock_code")
    # 000767 两行聚合：净买 1500，机构净席位 2
    assert rec.loc["000767", "lhb_net_buy"] == 1500.0
    assert rec.loc["000767", "lhb_inst_net_buy"] == 2
    assert rec.loc["000767", "lhb_today"] == 1
    # 000001 也上榜
    assert rec.loc["000001", "lhb_today"] == 1
    # 000002 不在结果（未上榜）
    assert "000002" not in rec.index


def test_screener_lhb_preset_registers() -> None:
    """龙虎榜接力/涨停接力策略在 BUILTIN_PRESETS 且归类事件驱动。"""
    from app.services.screener import BUILTIN_PRESETS

    names = {p["name"] for p in BUILTIN_PRESETS}
    assert "龙虎榜接力" in names
    assert "涨停接力" in names
    for p in BUILTIN_PRESETS:
        if p["name"] in ("龙虎榜接力", "涨停接力"):
            assert p["category"] == "事件驱动"
