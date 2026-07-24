"""龙虎榜明细持久化服务 (2026-07-22)。

把东财 ``stock_lhb_detail_em`` 当日明细落库到 ``stock_lhb_detail``，为筛选器
``lhb_today`` / ``lhb_net_buy`` / ``lhb_inst_net_buy`` 指标提供数据。

设计要点（对齐 ``limit_up_history``）：
- 时间门：17:00 后才入库（龙虎榜一般 17:00 后出齐）
- 全替换语义：刷新某日先删该日全部 -> 再 add_all（一只票一日可多行多原因）
- 200 行一 commit（防长事务截断，2026-07-21 硬约定）
- upsert key=(trading_date, stock_code, reason)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import StockLhbDetail

logger = logging.getLogger(__name__)

# 时间门：17:00 后龙虎榜出齐
LHB_READY_TIME = time(17, 0)

CHUNK_SIZE = 200


class LhbHistoryService:
    """龙虎榜明细 EOD 持久化服务。"""

    def __init__(self, gateway: Any = None, now_provider: Callable[[], datetime] | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    # ---------------- public API ----------------

    def refresh_for_date(
        self, session: Session, trading_date: date, *, force: bool = False
    ) -> int:
        """刷新 ``trading_date`` 当日龙虎榜明细到 ``stock_lhb_detail``。

        Returns:
            写入行数
        """
        if not force and self.now_provider().time() < LHB_READY_TIME:
            logger.info(
                "LhbHistoryService: 当前 %s 早于 %s，跳过 trading_date=%s",
                self.now_provider().time(), LHB_READY_TIME, trading_date,
            )
            return 0

        try:
            raw = self.gateway.fetch_lhb_detail(trading_date.strftime("%Y%m%d"))
        except Exception as exc:  # noqa: BLE001
            logger.error("LhbHistoryService: %s 拉取失败: %s", trading_date, exc)
            return 0
        if raw is None or raw.empty:
            logger.info("LhbHistoryService: %s 返回空", trading_date)
            return 0
        return self._upsert(session, trading_date, raw)

    def backfill_range(
        self, session: Session, start_date: date, end_date: date
    ) -> dict[str, int]:
        """回填 [start_date, end_date] 区间所有交易日。force=True 跳过时间门。"""
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        total = 0
        dates = 0
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                try:
                    n = self.refresh_for_date(session, cur, force=True)
                    total += n
                    if n > 0:
                        dates += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("LhbHistoryService: %s 失败: %s", cur, exc)
            cur += timedelta(days=1)
        return {"dates": dates, "rows": total}

    def prune_old(self, session: Session, keep_trading_days: int = 250) -> int:
        """删除早于 ``MAX(trading_date) - keep_trading_days`` 的龙虎榜明细。"""
        latest = session.scalar(select(func.max(StockLhbDetail.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockLhbDetail).where(StockLhbDetail.trading_date < cutoff)
        )
        session.commit()
        return result.rowcount or 0

    # ---------------- internals ----------------

    def _upsert(self, session: Session, trading_date: date, df: pd.DataFrame) -> int:
        """全替换：先删该日全部 -> 再分块 add_all（200 行/commit）。"""
        session.execute(
            delete(StockLhbDetail).where(StockLhbDetail.trading_date == trading_date)
        )
        session.commit()

        rows = df.to_dict("records")
        now = datetime.now()
        write_rows = [self._row_to_payload(r, trading_date, now) for r in rows]
        write_rows = [r for r in write_rows if r is not None]
        if not write_rows:
            return 0

        written = 0
        for i in range(0, len(write_rows), CHUNK_SIZE):
            chunk = write_rows[i : i + CHUNK_SIZE]
            session.add_all([StockLhbDetail(**r) for r in chunk])
            session.commit()
            written += len(chunk)
        return written

    @staticmethod
    def _row_to_payload(r: dict, trading_date: date, now: datetime) -> dict | None:
        code = str(r.get("股票代码") or "").strip()
        if not code:
            return None
        return {
            "trading_date": trading_date,
            "stock_code": code,
            "stock_name": str(r.get("名称") or ""),
            "reason": str(r.get("上榜原因") or ""),
            "interpretation": _or_none(r.get("解读")),
            "close": _to_float(r.get("收盘价")),
            "change_pct": _to_float(r.get("涨跌幅")),
            "net_buy": _to_float(r.get("龙虎榜净买额")),
            "buy_amount": _to_float(r.get("龙虎榜买入额")),
            "sell_amount": _to_float(r.get("龙虎榜卖出额")),
            "trading_value": _to_float(r.get("龙虎榜成交额")),
            "net_buy_ratio": _to_float(r.get("净买额占总成交比")),
            "turnover_rate": _to_float(r.get("换手率")),
            "float_mv": _to_float(r.get("流通市值")),
            "inst_buy_count": _to_int(r.get("机构买入席位")),
            "inst_sell_count": _to_int(r.get("机构卖出席位")),
            "inst_net_count": _to_int(r.get("机构净席位")),
            "source_label": "eastmoney",
            "updated_at": now,
        }


def _or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        f = float(v)
        if pd.isna(f):
            return 0
        return int(f)
    except (TypeError, ValueError):
        return 0
