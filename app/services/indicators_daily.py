"""技术指标每日预计算服务 (2026-07-21)。

复用 ``app.services.screener.compute_features`` 把每只股票每交易日的
bars/fundflow 派生指标算好，落库到 ``stock_indicators_daily``。筛选器
读取时优先 hit 预计算表，未命中再 fallback 现场算。

设计要点：
- 直接复用 screener.compute_features 模块级函数（避免重复实现 60+ 指标）
- 43 个核心 float 列 + compute_version + data_hash（失效检测）
- 200 行一 commit（防长事务）
- 仅对 bars 表覆盖到的股票落库（向后兼容 193/5500 限制）
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import StockDailyBar, StockFundFlowDaily, StockIndicatorDaily
from app.services.screener import INDICATOR_REGISTRY, compute_features

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200
COMPUTE_VERSION = "bars.v2.indicators.v1"

# 持久化的指标列（排除 source=realtime/limit_up_indicators 的）
_PERSIST_COLUMNS: list[str] = [
    # MA
    "ma5", "ma10", "ma20", "ma60",
    "close_vs_ma5", "close_vs_ma10", "close_vs_ma20", "close_vs_ma60",
    # 形态
    "ma_bullish", "golden_cross_recent", "death_cross_recent",
    "high_20d_break", "high_60d_break", "low_20d_break",
    # 动量
    "change_3d", "change_5d", "change_10d", "change_20d",
    "consecutive_up_days", "consecutive_down_days",
    "rsi6", "rsi14", "macd_dif", "macd_dea", "macd_hist",
    "macd_golden_recent", "bias20",
    # 量能
    "volume_ratio", "amount_ma5", "turnover_ma5", "volume_up_days",
    # 形态
    "limit_up_today", "limit_up_count_5d", "platform_breakout",
    "gap_up_pct", "lower_shadow_ratio",
    # 资金流
    "main_net_inflow", "main_net_inflow_5d", "main_net_inflow_10d",
    "main_net_inflow_days", "main_net_ratio", "super_large_net",
    "main_net_inflow_5d_pct_mv",
]
assert len(_PERSIST_COLUMNS) == 43, f"expected 43 columns, got {len(_PERSIST_COLUMNS)}"


class IndicatorsDailyService:
    """技术指标每日预计算服务。"""

    def __init__(self, now_provider: Any = None) -> None:
        self.now_provider = now_provider or datetime.now

    # ---------------- public API ----------------

    def compute_for_date(self, session: Session, trading_date: date) -> dict[str, int]:
        """为 ``trading_date`` 计算所有有 bars 的股票的 43 个核心指标。

        Returns:
            {"rows": int, "stocks": int, "data_hashes": int}
        """
        # 1) 找所有 bars 覆盖到的 stock_code
        codes = list(session.execute(
            select(StockDailyBar.stock_code)
            .where(StockDailyBar.trading_date <= trading_date)
            .group_by(StockDailyBar.stock_code)
        ).scalars())
        codes = sorted({str(c).zfill(6) for c in codes})
        if not codes:
            return {"rows": 0, "stocks": 0, "data_hashes": 0}

        # 2) 拉 120 日 bars
        bars_df = self._load_bars(session, codes, trading_date)
        if bars_df.empty:
            return {"rows": 0, "stocks": 0, "data_hashes": 0}

        # 3) 拉 30 日 fund_flow
        flow_df = self._load_fund_flow(session, codes, trading_date)

        # 4) 算指标（复用 screener.compute_features）
        latest_date_obj = trading_date
        feature_df = compute_features(bars_df, flow_df, latest_date_obj)
        if feature_df.empty:
            return {"rows": 0, "stocks": 0, "data_hashes": 0}

        # 5) 计算 data_hash（每个 stock_code 一个 hash）
        hashes = self._compute_hashes(session, codes, trading_date)

        # 6) 拼装写入行
        write_rows = []
        now = self.now_provider()
        for _, row in feature_df.iterrows():
            code = str(row.get("stock_code", "")).zfill(6)
            if not code:
                continue
            payload = {
                "stock_code": code,
                "trading_date": trading_date,
                "compute_version": COMPUTE_VERSION,
                "data_hash": hashes.get(code, ""),
                "bar_count": int(bars_df[bars_df["stock_code"] == code].shape[0]) if "stock_code" in bars_df.columns else None,
                "updated_at": now,
            }
            for col in _PERSIST_COLUMNS:
                if col in feature_df.columns:
                    val = row[col]
                    if pd.isna(val) if hasattr(pd, "isna") else val is None or (isinstance(val, float) and val != val):
                        payload[col] = None
                    else:
                        # numpy int → python int
                        payload[col] = val.item() if hasattr(val, "item") else val
                else:
                    payload[col] = None
            write_rows.append(payload)

        # 7) 分块 upsert
        written = self._upsert_chunks(session, write_rows)
        return {"rows": written, "stocks": len(write_rows), "data_hashes": len(hashes)}

    def backfill_range(
        self, session: Session, start_date: date, end_date: date
    ) -> dict[str, int]:
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        total_rows = 0
        total_stocks = 0
        dates = 0
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                try:
                    r = self.compute_for_date(session, cur)
                    total_rows += r["rows"]
                    total_stocks = max(total_stocks, r["stocks"])
                    if r["rows"] > 0:
                        dates += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("IndicatorsDailyService: %s 计算失败: %s", cur, exc)
            cur += timedelta(days=1)
        return {"dates": dates, "rows": total_rows, "stocks": total_stocks}

    def prune_old(self, session: Session, keep_trading_days: int = 250) -> int:
        """删除早于 ``MAX(trading_date) - keep_trading_days`` 的指标行。"""
        from sqlalchemy import delete, func
        latest = session.scalar(select(func.max(StockIndicatorDaily.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockIndicatorDaily).where(StockIndicatorDaily.trading_date < cutoff)
        )
        session.commit()
        return result.rowcount or 0

    # ---------------- internals ----------------

    def _load_bars(
        self, session: Session, codes: list[str], trading_date: date
    ) -> pd.DataFrame:
        cutoff = trading_date - timedelta(days=180)  # 留 buffer
        rows = list(
            session.execute(
                select(
                    StockDailyBar.stock_code,
                    StockDailyBar.trading_date,
                    StockDailyBar.open,
                    StockDailyBar.close,
                    StockDailyBar.high,
                    StockDailyBar.low,
                    StockDailyBar.volume,
                    StockDailyBar.amount,
                    StockDailyBar.change_pct,
                    StockDailyBar.turnover_rate,
                )
                .where(StockDailyBar.stock_code.in_(codes))
                .where(StockDailyBar.trading_date <= trading_date)
                .where(StockDailyBar.trading_date >= cutoff)
                .order_by(StockDailyBar.stock_code, StockDailyBar.trading_date)
            )
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=[
            "stock_code", "trading_date", "open", "close", "high", "low",
            "volume", "amount", "change_pct", "turnover_rate",
        ])
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        df["trading_date"] = pd.to_datetime(df["trading_date"])
        return df

    def _load_fund_flow(
        self, session: Session, codes: list[str], trading_date: date
    ) -> pd.DataFrame:
        cutoff = trading_date - timedelta(days=40)
        rows = list(
            session.execute(
                select(
                    StockFundFlowDaily.stock_code,
                    StockFundFlowDaily.trading_date,
                    StockFundFlowDaily.main_net_amount,
                    StockFundFlowDaily.main_net_ratio,
                    StockFundFlowDaily.super_large_net,
                    StockFundFlowDaily.large_net,
                )
                .where(StockFundFlowDaily.stock_code.in_(codes))
                .where(StockFundFlowDaily.trading_date <= trading_date)
                .where(StockFundFlowDaily.trading_date >= cutoff)
                .order_by(StockFundFlowDaily.stock_code, StockFundFlowDaily.trading_date)
            )
        )
        if not rows:
            return pd.DataFrame(columns=[
                "stock_code", "trading_date", "main_net_amount",
                "main_net_ratio", "super_large_net", "large_net",
            ])
        df = pd.DataFrame(rows, columns=[
            "stock_code", "trading_date", "main_net_amount",
            "main_net_ratio", "super_large_net", "large_net",
        ])
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        df["trading_date"] = pd.to_datetime(df["trading_date"])
        return df

    def _compute_hashes(
        self, session: Session, codes: list[str], trading_date: date
    ) -> dict[str, str]:
        """每个 stock_code 的 data_hash = sha1(code + max_bar_trading_date + max_flow_trading_date)。"""
        bar_max = dict(session.execute(
            select(StockDailyBar.stock_code, StockDailyBar.trading_date)
            .where(StockDailyBar.stock_code.in_(codes))
            .where(StockDailyBar.trading_date <= trading_date)
            .order_by(StockDailyBar.stock_code, StockDailyBar.trading_date.desc())
        ).all())
        flow_max = dict(session.execute(
            select(StockFundFlowDaily.stock_code, StockFundFlowDaily.trading_date)
            .where(StockFundFlowDaily.stock_code.in_(codes))
            .where(StockFundFlowDaily.trading_date <= trading_date)
            .order_by(StockFundFlowDaily.stock_code, StockFundFlowDaily.trading_date.desc())
        ).all())
        # 用 set default 把相同 trading_date 给所有 code
        # （前面 order_by 实际只能保证单只的最大日期，但 .all() 会拿所有行 → 用 group_by max 更准）
        # 简化：重新跑一个 MAX 聚合
        from sqlalchemy import func
        bar_max_agg = dict(session.execute(
            select(StockDailyBar.stock_code, func.max(StockDailyBar.trading_date))
            .where(StockDailyBar.stock_code.in_(codes))
            .where(StockDailyBar.trading_date <= trading_date)
            .group_by(StockDailyBar.stock_code)
        ).all())
        flow_max_agg = dict(session.execute(
            select(StockFundFlowDaily.stock_code, func.max(StockFundFlowDaily.trading_date))
            .where(StockFundFlowDaily.stock_code.in_(codes))
            .where(StockFundFlowDaily.trading_date <= trading_date)
            .group_by(StockFundFlowDaily.stock_code)
        ).all())
        hashes: dict[str, str] = {}
        for code in codes:
            content = f"{code}|{bar_max_agg.get(code, '')}|{flow_max_agg.get(code, '')}"
            hashes[code] = hashlib.sha1(content.encode("utf-8")).hexdigest()
        return hashes

    def _upsert_chunks(self, session: Session, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        write_cols = ["stock_code", "trading_date", "compute_version", "data_hash", "bar_count"] + _PERSIST_COLUMNS + ["updated_at"]
        # 保证所有列存在
        for r in rows:
            for c in write_cols:
                r.setdefault(c, None)
        written = 0
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i : i + CHUNK_SIZE]
            for r in chunk:
                r.setdefault("updated_at", self.now_provider())
            stmt = sqlite_insert(StockIndicatorDaily).values(chunk)
            update_dict = {c: stmt.excluded[c] for c in write_cols if c not in ("stock_code", "trading_date")}
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_code", "trading_date"],
                set_=update_dict,
            )
            session.execute(stmt)
            session.commit()
            written += len(chunk)
        return written
