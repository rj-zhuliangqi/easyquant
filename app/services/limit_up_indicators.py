"""涨停指标扁平视图服务 (2026-07-21)。

从 ``stock_limit_up_history`` GROUP BY (trading_date, stock_code) 聚合成
``stock_limit_up_indicators`` 一行/股票/日，供筛选器快速读取：
- limit_up_today: 0/1
- consecutive_limit_up_days: 当日连板数
- sealed_amount: 当日封单金额（sum over limit_up pool）
- broken_today: 0/1
- strong_pool: 0/1
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import StockLimitUpHistory, StockLimitUpIndicator

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200


class LimitUpIndicatorsService:
    """涨停指标扁平视图服务。"""

    # ---------------- public API ----------------

    def rebuild_for_date(self, session: Session, trading_date: date) -> int:
        """基于 stock_limit_up_history 重建 trading_date 的 stock_limit_up_indicators。"""
        rows = list(
            session.execute(
                select(
                    StockLimitUpHistory.stock_code,
                    StockLimitUpHistory.pool_type,
                    StockLimitUpHistory.board_count,
                    StockLimitUpHistory.sealed_amount,
                )
                .where(StockLimitUpHistory.trading_date == trading_date)
            )
        )
        if not rows:
            # 没历史 → 写空（truncate 当日）
            session.execute(
                delete(StockLimitUpIndicator).where(
                    StockLimitUpIndicator.trading_date == trading_date
                )
            )
            session.commit()
            return 0

        # group by stock_code
        agg: dict[str, dict[str, Any]] = {}
        for code, pool, board, sealed in rows:
            entry = agg.setdefault(code, {
                "limit_up_today": 0,
                "broken_today": 0,
                "strong_pool": 0,
                "_max_board": 0,
                "_sealed_sum": 0.0,
            })
            if pool == "limit_up":
                entry["limit_up_today"] = 1
                if board is not None and board > entry["_max_board"]:
                    entry["_max_board"] = board
                if sealed is not None:
                    entry["_sealed_sum"] += sealed
            elif pool == "broken":
                entry["broken_today"] = 1
            elif pool == "strong":
                entry["strong_pool"] = 1

        # 先 truncate 当日
        session.execute(
            delete(StockLimitUpIndicator).where(
                StockLimitUpIndicator.trading_date == trading_date
            )
        )
        now = datetime.now()
        write_rows = []
        for code, e in agg.items():
            write_rows.append({
                "stock_code": str(code).zfill(6),
                "trading_date": trading_date,
                "limit_up_today": e["limit_up_today"],
                "consecutive_limit_up_days": int(e["_max_board"]) if e["_max_board"] > 0 else 0,
                "sealed_amount": float(e["_sealed_sum"]) if e["_sealed_sum"] > 0 else None,
                "broken_today": e["broken_today"],
                "strong_pool": e["strong_pool"],
                "updated_at": now,
            })

        # 分块 commit
        written = 0
        for i in range(0, len(write_rows), CHUNK_SIZE):
            chunk = write_rows[i : i + CHUNK_SIZE]
            session.add_all([StockLimitUpIndicator(**r) for r in chunk])
            session.commit()
            written += len(chunk)
        return written

    def backfill_range(
        self, session: Session, start_date: date, end_date: date
    ) -> dict[str, int]:
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        total_rows = 0
        dates = 0
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                try:
                    total_rows += self.rebuild_for_date(session, cur)
                    dates += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("LimitUpIndicatorsService: %s 重建失败: %s", cur, exc)
            cur += timedelta(days=1)
        return {"dates": dates, "rows": total_rows}

    def prune_old(self, session: Session, keep_trading_days: int = 250) -> int:
        """删除早于 ``MAX(trading_date) - keep_trading_days`` 的涨停指标行。"""
        from sqlalchemy import delete, func, select as _select
        latest = session.scalar(_select(func.max(StockLimitUpIndicator.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockLimitUpIndicator).where(StockLimitUpIndicator.trading_date < cutoff)
        )
        session.commit()
        return result.rowcount or 0
