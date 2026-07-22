"""涨停池历史持久化服务 (2026-07-21)。

把东财 4 个池（涨停 / 炸板 / 强势 / 昨涨停）EOD 数据落库到
``stock_limit_up_history``，为筛选器连板/封单/强势等指标提供历史查询。

设计要点：
- 4 池独立 try/except + 独立 commit（单池失败不阻塞其他）
- 时间门：盘前/盘中调用直接 bail（涨停是 15:00 后的数据）
- upsert key=(trading_date, stock_code, pool_type)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import StockLimitUpHistory

logger = logging.getLogger(__name__)


# 时间门：收盘 + 30min 后才入库（避免盘中半截数据）
EOD_READY_TIME = time(15, 30)

# 4 个池对应 gateway 方法 + 数据库 pool_type
POOL_FETCHERS = (
    ("limit_up", "fetch_limit_up_pool"),
    ("broken", "fetch_broken_limit_up_pool"),
    ("strong", "fetch_strong_limit_up_pool"),
    ("previous", "fetch_previous_limit_up_pool"),
)


class LimitUpHistoryService:
    """涨停池 EOD 持久化服务。"""

    def __init__(self, gateway: Any = None, now_provider: Callable[[], datetime] | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    # ---------------- public API ----------------

    def refresh_for_date(
        self, session: Session, trading_date: date, *, force: bool = False
    ) -> dict[str, int]:
        """刷新 ``trading_date`` 当日 4 个池到 ``stock_limit_up_history``。

        Returns:
            {"limit_up": n, "broken": n, "strong": n, "previous": n}
        """
        # 时间门
        if not force and self.now_provider().time() < EOD_READY_TIME:
            logger.info(
                "LimitUpHistoryService: 当前 %s 早于 %s，跳过 trading_date=%s",
                self.now_provider().time(), EOD_READY_TIME, trading_date,
            )
            return {pool: 0 for pool, _ in POOL_FETCHERS}

        results: dict[str, int] = {}
        for pool_type, method_name in POOL_FETCHERS:
            try:
                fetcher = getattr(self.gateway, method_name, None)
                if fetcher is None:
                    logger.warning("LimitUpHistoryService: gateway 缺少 %s", method_name)
                    results[pool_type] = 0
                    continue
                raw = fetcher(trading_date.strftime("%Y%m%d"))
                if raw is None or raw.empty:
                    logger.info("LimitUpHistoryService: %s %s 返回空", trading_date, pool_type)
                    results[pool_type] = 0
                    continue
                normalized = self._normalize_frame(raw, pool_type)
                if normalized.empty:
                    results[pool_type] = 0
                    continue
                n = self._upsert(session, trading_date, pool_type, normalized)
                results[pool_type] = n
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "LimitUpHistoryService: %s pool=%s 失败: %s",
                    trading_date, pool_type, exc,
                )
                results[pool_type] = 0
                # 单池失败不阻塞其他池
                continue

        # 降级：东财 limit_up 池为空且是今天 -> 用实时行情+涨幅阈值判定 (2026-07-21)
        # 复用 gateway.fetch_limit_up_from_realtime()，它内部走东财->新浪->akshare fallback
        if results.get("limit_up", 0) == 0:
            today = self.now_provider().date()
            if trading_date == today:
                try:
                    degraded = self.gateway.fetch_limit_up_from_realtime()
                    if degraded is not None and not degraded.empty:
                        normalized = self._normalize_frame(degraded, "limit_up")
                        if not normalized.empty:
                            n = self._upsert(session, trading_date, "limit_up", normalized)
                            results["limit_up"] = n
                            logger.info(
                                "LimitUpHistoryService: %s 东财涨停池空，降级用实时行情 +%d 行",
                                trading_date, n,
                            )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LimitUpHistoryService: 降级涨停判定失败: %s", exc)
        return results

    def backfill_range(
        self, session: Session, start_date: date, end_date: date
    ) -> dict[str, int]:
        """回填 [start_date, end_date] 区间所有交易日。force=True 跳过时间门。"""
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        total = {pool: 0 for pool, _ in POOL_FETCHERS}
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                try:
                    daily = self.refresh_for_date(session, cur, force=True)
                    for pool, n in daily.items():
                        total[pool] += n
                except Exception as exc:  # noqa: BLE001
                    logger.error("LimitUpHistoryService: %s 整体失败: %s", cur, exc)
            cur = _next_day(cur)
        return total

    def prune_old(self, session: Session, keep_trading_days: int = 250) -> int:
        """删除早于 ``MAX(trading_date) - keep_trading_days`` 的涨停池历史。"""
        from datetime import timedelta
        from sqlalchemy import func, select as _select
        latest = session.scalar(_select(func.max(StockLimitUpHistory.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockLimitUpHistory).where(StockLimitUpHistory.trading_date < cutoff)
        )
        session.commit()
        return result.rowcount or 0

    # ---------------- internals ----------------

    def _normalize_frame(self, frame: pd.DataFrame, pool_type: str) -> pd.DataFrame:
        """复用 LimitUpService 的列名映射规则，但只保留 stock_limit_up_history 的列。"""
        if frame is None or frame.empty:
            return pd.DataFrame()
        col_map = {
            "代码": "stock_code", "名称": "stock_name",
            "连板数": "board_count",
            "首次封板时间": "first_limit_up_time", "最后封板时间": "last_limit_up_time",
            "涨停价": "limit_up_price",
            "封单金额": "sealed_amount", "封板资金": "sealed_amount",
            "成交额": "turnover", "换手率": "turnover_rate", "涨跌幅": "change_pct",
            "所属行业": "industry", "量比": "volume_ratio", "振幅": "amplitude",
            "流通市值": "float_market_value", "总市值": "total_market_value",
            "封板资金": "net_inflow", "炸板次数": "broken_board_count",
        }
        out = pd.DataFrame()
        for src, dst in col_map.items():
            if src in frame.columns:
                out[dst] = frame[src]
        if "stock_code" not in out.columns:
            return pd.DataFrame()
        out["stock_code"] = out["stock_code"].astype(str).str.zfill(6)
        if "stock_name" not in out.columns:
            out["stock_name"] = ""
        else:
            out["stock_name"] = out["stock_name"].astype(str)
        # 类型转换
        for col in ("board_count", "broken_board_count"):
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
        for col in (
            "limit_up_price", "sealed_amount", "turnover", "turnover_rate",
            "change_pct", "volume_ratio", "amplitude",
            "float_market_value", "total_market_value", "net_inflow",
        ):
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
        # 保证所有列都存在
        for col in (
            "stock_code", "stock_name", "board_count",
            "first_limit_up_time", "last_limit_up_time",
            "limit_up_price", "sealed_amount", "turnover", "turnover_rate",
            "change_pct", "industry", "volume_ratio", "amplitude",
            "float_market_value", "total_market_value",
            "net_inflow", "broken_board_count",
        ):
            if col not in out.columns:
                out[col] = None
        return out

    def _upsert(
        self, session: Session, trading_date: date, pool_type: str, df: pd.DataFrame
    ) -> int:
        """upsert 到 stock_limit_up_history（先清同 (date, pool_type) → 再 add_all）。"""
        # 先清同 (date, pool_type) 旧记录（全替换语义；4 池各自 EOD 一次）
        session.execute(
            delete(StockLimitUpHistory).where(
                StockLimitUpHistory.trading_date == trading_date,
                StockLimitUpHistory.pool_type == pool_type,
            )
        )
        rows = df.to_dict("records")
        now = datetime.now()
        write_rows = []
        for r in rows:
            write_rows.append({
                "trading_date": trading_date,
                "stock_code": r["stock_code"],
                "stock_name": r.get("stock_name") or "",
                "pool_type": pool_type,
                "board_count": _to_int_or_none(r.get("board_count")),
                "first_limit_up_time": r.get("first_limit_up_time"),
                "last_limit_up_time": r.get("last_limit_up_time"),
                "limit_up_price": _to_float_or_none(r.get("limit_up_price")),
                "sealed_amount": _to_float_or_none(r.get("sealed_amount")),
                "turnover": _to_float_or_none(r.get("turnover")),
                "turnover_rate": _to_float_or_none(r.get("turnover_rate")),
                "change_pct": _to_float_or_none(r.get("change_pct")),
                "industry": r.get("industry"),
                "volume_ratio": _to_float_or_none(r.get("volume_ratio")),
                "amplitude": _to_float_or_none(r.get("amplitude")),
                "float_market_value": _to_float_or_none(r.get("float_market_value")),
                "total_market_value": _to_float_or_none(r.get("total_market_value")),
                "net_inflow": _to_float_or_none(r.get("net_inflow")),
                "broken_board_count": _to_int_or_none(r.get("broken_board_count")),
                "captured_at": now,
            })
        if not write_rows:
            return 0
        # 直接 add_all（已 delete 旧记录，无冲突）
        session.add_all([StockLimitUpHistory(**r) for r in write_rows])
        session.commit()
        return len(write_rows)


def _next_day(d: date) -> date:
    from datetime import timedelta
    return d + timedelta(days=1)


def _to_float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        f = float(v)
        if pd.isna(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None
