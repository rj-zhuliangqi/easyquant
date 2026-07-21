"""日终聚合服务 (2026-07-21)。

把 ``individual_stock_snapshots`` 当日所有 tick 聚合成一行/股票/日，写入
``stock_realtime_eod``，供筛选器历史回放使用。

设计要点：
- 输入：trading_date 当日所有 snapshots + （可选）当日 realtime 扩展字段（PE/PB/市值）
- 输出：open/close/high/low/vwap/amount + 基础组字段
- 200 行一 commit（避免 2026-07-21 长事务截断事故）
- upsert 走 sqlite on_conflict_do_update
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import IndividualStockSnapshot, StockRealtimeEod

logger = logging.getLogger(__name__)


# 单批 commit 大小（防止长事务）
CHUNK_SIZE = 200

# 收盘判定时间窗：14:56 之后到 15:00 之前的最后一笔作为 EOD close
CLOSE_WINDOW_START = time(14, 56)
CLOSE_WINDOW_END = time(15, 0)
# 开盘判定：09:30 后的第一笔
OPEN_MARK = time(9, 30)


class DailyEodService:
    """每日 EOD 聚合服务。"""

    def __init__(self, gateway: Any | None = None, now_provider: Callable[[], datetime] | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    # ---------------- public API ----------------

    def aggregate_from_snapshots(
        self,
        session: Session,
        trading_date: date,
        *,
        realtime_frame: pd.DataFrame | None = None,
    ) -> int:
        """聚合 ``trading_date`` 当日所有 snapshot → ``stock_realtime_eod``。

        Args:
            session: SQLAlchemy session
            trading_date: 交易日期
            realtime_frame: 可选；当日 fetch_individual_realtime() 返回的全 11 列 DataFrame，
                用于填充 pe/pb/total_mv/float_mv/turnover_rate。如果为 None 且 gateway 可用，
                会尝试调用一次；都没有则这些列留 NULL。

        Returns:
            实际写入/更新的 (stock_code, trading_date) 行数
        """
        snapshots = self._load_snapshots(session, trading_date)
        if snapshots.empty:
            logger.info("DailyEodService: trading_date=%s 无 snapshot，跳过", trading_date)
            return 0

        # 聚合 OHLCV
        aggregated = self._aggregate_snapshots(snapshots)

        # 合入 realtime 扩展字段（pe/pb/mv/turnover_rate）
        if realtime_frame is None and self.gateway is not None:
            try:
                realtime_frame = self.gateway.fetch_individual_realtime()
            except Exception as exc:  # noqa: BLE001
                logger.warning("DailyEodService: gateway 拉取 realtime 失败: %s", exc)
                realtime_frame = None
        if realtime_frame is not None and not realtime_frame.empty:
            aggregated = self._merge_realtime_fields(aggregated, realtime_frame)

        # 计算 change_pct（需要 prev_close）
        aggregated = self._compute_change_pct(session, aggregated, trading_date)

        return self._upsert_chunks(session, aggregated)

    def backfill_range(
        self, session: Session, start_date: date, end_date: date
    ) -> dict[str, int]:
        """回填 [start_date, end_date] 区间所有交易日。

        Returns:
            {"dates": int, "rows": int}
        """
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        rows = 0
        dates = 0
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:  # Mon-Fri
                try:
                    rows += self.aggregate_from_snapshots(session, cur)
                    dates += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("DailyEodService: %s 聚合失败: %s", cur, exc)
            cur += timedelta(days=1)
        return {"dates": dates, "rows": rows}

    def prune_old(self, session: Session, keep_trading_days: int = 250) -> int:
        """删除早于 ``MAX(trading_date) - keep_trading_days`` 的 EOD 行。"""
        from sqlalchemy import delete, func
        latest = session.scalar(select(func.max(StockRealtimeEod.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockRealtimeEod).where(StockRealtimeEod.trading_date < cutoff)
        )
        session.commit()
        return result.rowcount or 0

    # ---------------- internals ----------------

    def _load_snapshots(self, session: Session, trading_date: date) -> pd.DataFrame:
        rows = list(
            session.execute(
                select(
                    IndividualStockSnapshot.stock_code,
                    IndividualStockSnapshot.stock_name,
                    IndividualStockSnapshot.trading_date,
                    IndividualStockSnapshot.captured_at,
                    IndividualStockSnapshot.latest_price,
                    IndividualStockSnapshot.change_percent,
                    IndividualStockSnapshot.net_amount,
                )
                .where(IndividualStockSnapshot.trading_date == trading_date)
                .order_by(
                    IndividualStockSnapshot.stock_code,
                    IndividualStockSnapshot.captured_at,
                )
            )
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(
            rows,
            columns=[
                "stock_code",
                "stock_name",
                "trading_date",
                "captured_at",
                "latest_price",
                "change_percent",
                "net_amount",
            ],
        )
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        df["captured_at"] = pd.to_datetime(df["captured_at"])
        return df

    def _aggregate_snapshots(self, df: pd.DataFrame) -> pd.DataFrame:
        """按 stock_code 聚合 OHLCV/vwap/amount/snapshot_count/first_last captured_at。"""
        df = df.dropna(subset=["latest_price"]).copy()
        if df.empty:
            return pd.DataFrame()
        # 记录 trading_date 用于后续 merge（一个 trading_date 调用一次聚合）
        trading_date = df["trading_date"].iloc[0]

        def _agg(group: pd.DataFrame) -> pd.Series:
            prices = group["latest_price"]
            net_amt = group["net_amount"].fillna(0.0)
            # VWAP：仅在 net_amount > 0 的行加权
            valid = net_amt > 0
            if valid.any():
                vwap = (prices[valid] * net_amt[valid]).sum() / net_amt[valid].sum()
            else:
                vwap = float(prices.iloc[-1])

            # open: 09:30 之后的第一笔
            open_mask = group["captured_at"].dt.time >= OPEN_MARK
            if open_mask.any():
                open_price = float(group.loc[open_mask].iloc[0]["latest_price"])
            else:
                open_price = float(prices.iloc[0])

            # close: 14:56–15:00 之间的最后一笔；否则全天最后一笔
            close_mask = (group["captured_at"].dt.time >= CLOSE_WINDOW_START) & (
                group["captured_at"].dt.time <= CLOSE_WINDOW_END
            )
            if close_mask.any():
                close_price = float(group.loc[close_mask].iloc[-1]["latest_price"])
            else:
                close_price = float(prices.iloc[-1])

            return pd.Series(
                {
                    "stock_name": group["stock_name"].iloc[-1],
                    "open": open_price,
                    "close": close_price,
                    "high": float(prices.max()),
                    "low": float(prices.min()),
                    "vwap": float(vwap),
                    "volume": float(net_amt.abs().sum()),  # |net_amount| 作为 volume 近似
                    "amount": float(net_amt.sum()),  # 净流入金额（注意：snapshot 只存净额）
                    "snapshot_count": int(len(group)),
                    "first_captured_at": group["captured_at"].min().to_pydatetime(),
                    "last_captured_at": group["captured_at"].max().to_pydatetime(),
                }
            )

        result = df.groupby("stock_code", as_index=False).apply(_agg, include_groups=False).reset_index(drop=True)
        result["trading_date"] = trading_date
        return result
    def _merge_realtime_fields(
        self, aggregated: pd.DataFrame, realtime: pd.DataFrame
    ) -> pd.DataFrame:
        """把 fetch_individual_realtime() 返回的扩展列（pe/pb/mv/turnover_rate）合入。"""
        rt = realtime.copy()
        # 列名匹配：INDIVIDUAL_EXTENDED_COLUMNS = ["股票代码", "股票简称", "最新价", "涨跌幅", "净额", "成交额", "换手率", "市盈率动", "市净率", "总市值", "流通市值"]
        rename = {
            "股票代码": "stock_code",
            "换手率": "turnover_rate",
            "市盈率动": "pe_dynamic",
            "市净率": "pb",
            "总市值": "total_mv",
            "流通市值": "float_mv",
        }
        rt = rt.rename(columns=rename)
        if "stock_code" not in rt.columns:
            return aggregated
        rt["stock_code"] = rt["stock_code"].astype(str).str.zfill(6)
        keep = ["stock_code"] + [c for c in ["turnover_rate", "pe_dynamic", "pb", "total_mv", "float_mv"] if c in rt.columns]
        rt = rt[keep].drop_duplicates(subset="stock_code", keep="last")
        return aggregated.merge(rt, on="stock_code", how="left")

    def _compute_change_pct(
        self, session: Session, aggregated: pd.DataFrame, trading_date: date
    ) -> pd.DataFrame:
        """用上一交易日 stock_realtime_eod.close 算 change_pct。"""
        if aggregated.empty or "close" not in aggregated.columns:
            return aggregated
        prev_date = trading_date - timedelta(days=1)
        # 回退找最近的 trading_date
        for _ in range(7):
            prev_close_map = dict(
                session.execute(
                    select(StockRealtimeEod.stock_code, StockRealtimeEod.close).where(
                        StockRealtimeEod.trading_date == prev_date
                    )
                ).all()
            )
            if prev_close_map:
                break
            prev_date -= timedelta(days=1)
        if not prev_close_map:
            # 没历史 → 不算 change_pct，留 NaN
            aggregated["change_pct"] = None
            return aggregated

        def _pct(row: pd.Series) -> float | None:
            prev = prev_close_map.get(row["stock_code"])
            if prev is None or row["close"] is None or prev == 0:
                return None
            return (row["close"] - prev) / prev * 100.0

        aggregated["change_pct"] = aggregated.apply(_pct, axis=1)
        return aggregated

    def _upsert_chunks(self, session: Session, df: pd.DataFrame) -> int:
        """分块 upsert；每块一次 commit。返回行数。"""
        if df.empty:
            return 0
        if "stock_name" not in df.columns:
            df["stock_name"] = None

        # 选择要写入的列
        write_cols = [
            "stock_code",
            "stock_name",
            "trading_date",
            "open",
            "close",
            "high",
            "low",
            "vwap",
            "volume",
            "amount",
            "change_pct",
            "turnover_rate",
            "pe_dynamic",
            "pb",
            "total_mv",
            "float_mv",
            "snapshot_count",
            "first_captured_at",
            "last_captured_at",
            "source_label",
            "updated_at",
        ]
        df = df.copy()
        df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
        df["updated_at"] = datetime.now()

        # 保证列存在
        for col in write_cols:
            if col not in df.columns:
                df[col] = None

        rows = df[write_cols].to_dict("records")
        written = 0
        now = datetime.now()
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i : i + CHUNK_SIZE]
            for r in chunk:
                r.setdefault("updated_at", now)
            stmt = sqlite_insert(StockRealtimeEod).values(chunk)
            update_dict = {
                c: stmt.excluded[c]
                for c in write_cols
                if c not in ("stock_code", "trading_date")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_code", "trading_date"],
                set_=update_dict,
            )
            session.execute(stmt)
            session.commit()
            written += len(chunk)
        return written


def _now_provider_safe(provider: Callable[[], datetime] | None) -> datetime:
    return provider() if provider is not None else datetime.now()
