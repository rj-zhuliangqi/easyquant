"""选股器本地日线库与资金流回补服务。

设计要点（v2 选股方案）：

- 逐只拉取日线做同步筛选不可行（0.5–1.5s/只）。本服务负责后台回补 + 维护
  本地数据库，前端筛选时纯离线计算。
- 价格统一前复权（``adjust="qfq"``）以保证除权日附近指标不断裂；
  ``volume/amount/turnover_rate`` 为原始值。
- 串行 + 0.2-0.3s 抖动避免触发限流；单只失败仅记录不中断。
- 资金流缺失时记入 ``warnings``，筛选引擎降级（跳过该条件）。
- ``self.progress["running"]`` 互斥锁防止并发回补。
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import IndividualStockSnapshot, StockDailyBar, StockFundFlowDaily


logger = logging.getLogger(__name__)


@dataclass
class DailyBarsProgress:
    running: bool = False
    stage: str = "idle"  # idle | bars | fund_flow | done
    done: int = 0
    total: int = 0
    failed: list[dict[str, str]] = field(default_factory=list)
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class UniverseFilters:
    min_amount: float = 50_000_000.0
    exclude_st: bool = True
    boards: tuple[str, ...] = ("main", "cyb", "kcb")  # 4/8/920 北交所恒排除


BoardPrefixes = {
    "main": ("000", "001", "002", "003", "600", "601", "603", "605"),  # 沪深主板
    "cyb": ("300", "301"),  # 创业板
    "kcb": ("688", "689"),  # 科创板
    "bj": ("4", "8", "920"),  # 北交所
}


class DailyBarsService:
    """个股日线 + 资金流回补与查询。"""

    def __init__(self, gateway: Any, now_provider: Callable[[], datetime] | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now
        self._lock = threading.Lock()
        self.progress = DailyBarsProgress()

    # ---------------- public: query -----------------

    def coverage(self, session: Session) -> dict[str, Any]:
        """当前 stock_daily_bars / stock_fund_flow_daily 覆盖统计。"""
        bar_rows = session.scalar(select(func.count()).select_from(StockDailyBar)) or 0
        flow_rows = session.scalar(select(func.count()).select_from(StockFundFlowDaily)) or 0
        stock_count = session.scalar(
            select(func.count(func.distinct(StockDailyBar.stock_code)))
        ) or 0
        latest_date = session.scalar(select(func.max(StockDailyBar.trading_date)))
        flow_stock_count = session.scalar(
            select(func.count(func.distinct(StockFundFlowDaily.stock_code)))
        ) or 0
        return {
            "bar_rows": int(bar_rows),
            "flow_rows": int(flow_rows),
            "stock_count": int(stock_count),
            "flow_stock_count": int(flow_stock_count),
            "latest_date": latest_date.isoformat() if latest_date else None,
        }

    def latest_trading_date(self, session: Session) -> date | None:
        return session.scalar(select(func.max(StockDailyBar.trading_date)))

    # ---------------- universe -----------------

    def get_universe(
        self,
        session: Session,
        min_amount: float = 50_000_000.0,
    ) -> pd.DataFrame:
        """从 ``individual_stock_snapshots`` 取最新一日的全市场快照，按规则过滤。

        过滤：
        - ST / *ST / 退市 (名称包含 ST、PT、*、退)
        - 北交所 (4/8/920 开头)
        - 停牌 (amount 为 None 或 0)
        - amount < min_amount
        """
        latest_date = session.scalar(select(func.max(IndividualStockSnapshot.trading_date)))
        if latest_date is None:
            return pd.DataFrame(columns=["code", "name", "latest_price", "change_pct", "amount"])

        rows = list(
            session.execute(
                select(
                    IndividualStockSnapshot.stock_code,
                    IndividualStockSnapshot.stock_name,
                    IndividualStockSnapshot.latest_price,
                    IndividualStockSnapshot.change_percent,
                    IndividualStockSnapshot.net_amount,
                )
                .where(IndividualStockSnapshot.trading_date == latest_date)
                .where(IndividualStockSnapshot.captured_at == session.scalar(
                    select(func.max(IndividualStockSnapshot.captured_at)).where(
                        IndividualStockSnapshot.trading_date == latest_date
                    )
                ))
            )
        )
        if not rows:
            return pd.DataFrame(columns=["code", "name", "latest_price", "change_pct", "amount"])

        df = pd.DataFrame(
            rows,
            columns=["code", "name", "latest_price", "change_pct", "net_amount"],
        )
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["name"] = df["name"].astype(str)

        # ST / *ST / 退市
        st_mask = df["name"].str.contains("ST|\\*ST|PT|退", case=False, regex=True, na=False)
        # 北交所
        bj_mask = df["code"].str.startswith(("4", "8", "920"))
        # 停牌（amount=0 或 None；IndividualStockSnapshot 没有 amount 字段，fallback 用 net_amount）
        suspended = df["net_amount"].isna() | (df["net_amount"].fillna(0) <= 0)
        # 流通市值近似：用 net_amount 代替（仅用于过滤，没有 amount 字段时 fallback）
        # 因未引入市值字段，这里如果 net_amount < min_amount 直接剔除
        amount_mask = df["net_amount"].fillna(0) >= min_amount

        kept = df[~st_mask & ~bj_mask & ~suspended & amount_mask].reset_index(drop=True)
        kept["latest_price"] = pd.to_numeric(kept["latest_price"], errors="coerce")
        kept["change_pct"] = pd.to_numeric(kept["change_pct"], errors="coerce")
        kept["amount"] = pd.to_numeric(kept["net_amount"], errors="coerce")
        return kept[["code", "name", "latest_price", "change_pct", "amount"]]

    # ---------------- backfill -----------------

    def _ensure_lock(self) -> bool:
        """若已有回补在跑，返回 False（拒绝）；否则 True。"""
        with self._lock:
            if self.progress.running:
                return False
            self.progress = DailyBarsProgress(
                running=True,
                stage="bars",
                started_at=self.now_provider(),
            )
            return True

    def _release_lock(self) -> None:
        with self._lock:
            self.progress.running = False
            self.progress.finished_at = self.now_provider()

    def backfill_all(
        self,
        session: Session,
        min_amount: float = 50_000_000.0,
        days: int = 150,
        code_limit: int | None = None,
        progress_cb: Callable[[DailyBarsProgress], None] | None = None,
    ) -> dict[str, Any]:
        """二阶段回补：日线 → 资金流。

        ``code_limit`` 用于测试 / 冒烟（仅前 N 只）。
        """
        if not self._ensure_lock():
            return {"started": False, "already_running": True, "progress": self._snapshot()}

        try:
            universe = self.get_universe(session, min_amount=min_amount)
            if universe.empty:
                self.progress.message = "universe 为空，跳过回补"
                self.progress.stage = "done"
                return {"started": True, "already_running": False, "progress": self._snapshot()}

            codes = universe["code"].astype(str).str.zfill(6).tolist()
            if code_limit is not None:
                codes = codes[: max(0, int(code_limit))]
            self.progress.total = len(codes)
            self.progress.message = f"universe={len(codes)}，开始回补日线"

            # 阶段 1：日线
            self._backfill_bars(session, codes, days=days, progress_cb=progress_cb)
            # 阶段 2：资金流
            self.progress.stage = "fund_flow"
            self.progress.message = "开始回补资金流"
            if progress_cb:
                progress_cb(self._snapshot())
            self._backfill_fund_flow(session, codes, progress_cb=progress_cb)

            self.progress.stage = "done"
            self.progress.message = (
                f"回补完成：universe={len(codes)}, "
                f"failed={len(self.progress.failed)}"
            )
            # 收尾 prune
            try:
                self.prune_old_bars(session)
                self.prune_old_fund_flow(session)
            except Exception:
                logger.exception("prune_old_bars failed")
            return {"started": True, "already_running": False, "progress": self._snapshot()}
        except Exception as exc:  # noqa: BLE001
            logger.exception("backfill_all crashed")
            self.progress.stage = "error"
            self.progress.message = f"回补异常：{exc}"
            return {"started": True, "already_running": False, "progress": self._snapshot()}
        finally:
            self._release_lock()

    def _backfill_bars(
        self,
        session: Session,
        codes: Iterable[str],
        *,
        days: int = 150,
        progress_cb: Callable[[DailyBarsProgress], None] | None = None,
    ) -> None:
        codes = list(codes)
        self.progress.stage = "bars"
        for index, code in enumerate(codes):
            existing_dates = set(
                session.scalars(
                    select(StockDailyBar.trading_date).where(StockDailyBar.stock_code == code)
                ).all()
            )
            try:
                start = (self.now_provider().date() - timedelta(days=days)).strftime("%Y%m%d")
                end = self.now_provider().date().strftime("%Y%m%d")
                frame = self.gateway.fetch_stock_daily_history(
                    code, start, end, adjust="qfq"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch_stock_daily_history failed: %s exc=%s", code, exc)
                self.progress.failed.append({"code": code, "stage": "bars", "error": str(exc)})
                continue

            if frame is None or frame.empty:
                self.progress.failed.append({"code": code, "stage": "bars", "error": "empty"})
            else:
                rows = _daily_history_to_rows(code, frame)
                if rows:
                    insert_rows(session, StockDailyBar, rows, key_cols=("stock_code", "trading_date"))
                    session.commit()
                if progress_cb is not None:
                    pass

            self.progress.done = index + 1
            if progress_cb is not None and (index % 5 == 0 or index == len(codes) - 1):
                progress_cb(self._snapshot())
            _sleep_jitter()

    def _backfill_fund_flow(
        self,
        session: Session,
        codes: Iterable[str],
        *,
        progress_cb: Callable[[DailyBarsProgress], None] | None = None,
    ) -> None:
        codes = list(codes)
        for index, code in enumerate(codes):
            market = _infer_market(code)
            try:
                frame = self.gateway.fetch_stock_fund_flow_history(code, market)
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch_stock_fund_flow_history failed: %s exc=%s", code, exc)
                self.progress.failed.append({"code": code, "stage": "fund_flow", "error": str(exc)})
                continue

            if frame is None or frame.empty:
                self.progress.failed.append({"code": code, "stage": "fund_flow", "error": "empty"})
            else:
                rows = _fund_flow_history_to_rows(code, frame)
                if rows:
                    insert_rows(
                        session, StockFundFlowDaily, rows, key_cols=("stock_code", "trading_date")
                    )
                    session.commit()

            if progress_cb is not None and (index % 5 == 0 or index == len(codes) - 1):
                progress_cb(self._snapshot())
            _sleep_jitter()

    def ensure_recent_bars(
        self,
        session: Session,
        codes: Iterable[str],
        *,
        days: int = 10,
        progress_cb: Callable[[DailyBarsProgress], None] | None = None,
    ) -> None:
        """增量回补：仅补最近 ``days`` 自然日的日线（断点续跑）。"""
        for code in codes:
            try:
                start = (self.now_provider().date() - timedelta(days=days)).strftime("%Y%m%d")
                end = self.now_provider().date().strftime("%Y%m%d")
                frame = self.gateway.fetch_stock_daily_history(code, start, end, adjust="qfq")
            except Exception as exc:  # noqa: BLE001
                logger.warning("ensure_recent_bars failed %s: %s", code, exc)
                continue
            if frame is None or frame.empty:
                continue
            rows = _daily_history_to_rows(code, frame)
            if rows:
                insert_rows(session, StockDailyBar, rows, key_cols=("stock_code", "trading_date"))
                session.commit()
            _sleep_jitter()
        if progress_cb:
            progress_cb(self._snapshot())

    # ---------------- prune -----------------

    def prune_old_bars(self, session: Session, keep_trading_days: int = 120) -> int:
        """删除超过保留窗口的旧日线，按 ``trading_date < cutoff``。"""
        cutoff_date = self.latest_trading_date(session)
        if cutoff_date is None:
            return 0
        cutoff = cutoff_date - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockDailyBar).where(StockDailyBar.trading_date < cutoff)
        )
        session.commit()
        return int(result.rowcount or 0)

    def prune_old_fund_flow(self, session: Session, keep_trading_days: int = 120) -> int:
        latest = session.scalar(select(func.max(StockFundFlowDaily.trading_date)))
        if latest is None:
            return 0
        cutoff = latest - timedelta(days=keep_trading_days)
        result = session.execute(
            delete(StockFundFlowDaily).where(StockFundFlowDaily.trading_date < cutoff)
        )
        session.commit()
        return int(result.rowcount or 0)

    # ---------------- helpers -----------------

    def _snapshot(self) -> dict[str, Any]:
        return {
            "running": self.progress.running,
            "stage": self.progress.stage,
            "done": self.progress.done,
            "total": self.progress.total,
            "failed": list(self.progress.failed),
            "message": self.progress.message,
            "started_at": self.progress.started_at.isoformat() if self.progress.started_at else None,
            "finished_at": self.progress.finished_at.isoformat() if self.progress.finished_at else None,
        }


# ---------------- module-level helpers -----------------


def _sleep_jitter() -> None:
    time.sleep(random.uniform(0.2, 0.3))


def _infer_market(code: str) -> str:
    """akshare stock_individual_fund_flow 的 market 实参。

    sh=6 开头（沪），sz=0/3 开头（深），bj=4/8/920 开头（北交所）。
    """
    code = str(code).strip().zfill(6) if code else ""
    if not code:
        return "sh"
    if code.startswith(("4", "8", "920")):
        return "bj"
    if code.startswith("6"):
        return "sh"
    return "sz"


def _daily_history_to_rows(code: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """akshare stock_zh_a_hist 返回列（去除全角符号后）：

    ["日期", "股票代码", "开盘", "收盘", "最高", "最低", "成交量", "成交额",
     "振幅", "涨跌幅", "涨跌额", "换手率"]
    """
    if frame is None or frame.empty:
        return []
    col_open = _pick_col(frame, ["开盘"])
    col_close = _pick_col(frame, ["收盘"])
    col_high = _pick_col(frame, ["最高"])
    col_low = _pick_col(frame, ["最低"])
    col_volume = _pick_col(frame, ["成交量"])
    col_amount = _pick_col(frame, ["成交额"])
    col_change_pct = _pick_col(frame, ["涨跌幅"])
    col_turnover_rate = _pick_col(frame, ["换手率"])
    col_date = _pick_col(frame, ["日期"])

    if col_date is None:
        return []

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        try:
            trading_date = pd.to_datetime(row[col_date]).date()
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            {
                "stock_code": code,
                "trading_date": trading_date,
                "open": _safe_float(row.get(col_open)) if col_open else None,
                "close": _safe_float(row.get(col_close)) if col_close else None,
                "high": _safe_float(row.get(col_high)) if col_high else None,
                "low": _safe_float(row.get(col_low)) if col_low else None,
                "volume": _safe_float(row.get(col_volume)) if col_volume else None,
                "amount": _safe_float(row.get(col_amount)) if col_amount else None,
                "change_pct": _safe_float(row.get(col_change_pct)) if col_change_pct else None,
                "turnover_rate": _safe_float(row.get(col_turnover_rate)) if col_turnover_rate else None,
            }
        )
    return rows


def _fund_flow_history_to_rows(code: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """akshare stock_individual_fund_flow 返回列：

    ["日期", "收盘价", "涨跌幅", "主力净额", "主力净占比", "超大单净额",
     "大单净额", "中单净额", "小单净额"]
    """
    if frame is None or frame.empty:
        return []
    col_date = _pick_col(frame, ["日期"])
    col_main_net = _pick_col(frame, ["主力净额"])
    col_main_ratio = _pick_col(frame, ["主力净占比", "主力净占比%"])
    col_super = _pick_col(frame, ["超大单净额"])
    col_large = _pick_col(frame, ["大单净额"])
    if col_date is None:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        try:
            trading_date = pd.to_datetime(row[col_date]).date()
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            {
                "stock_code": code,
                "trading_date": trading_date,
                "main_net_amount": _safe_float(row.get(col_main_net)) if col_main_net else None,
                "main_net_ratio": _safe_float(row.get(col_main_ratio)) if col_main_ratio else None,
                "super_large_net": _safe_float(row.get(col_super)) if col_super else None,
                "large_net": _safe_float(row.get(col_large)) if col_large else None,
            }
        )
    return rows


def _pick_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        result = float(value)
        if pd.isna(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def insert_rows(
    session: Session,
    model: type,
    rows: list[dict[str, Any]],
    *,
    key_cols: tuple[str, str],
) -> int:
    """SQLite ON CONFLICT upsert。``key_cols`` 用于唯一键。"""
    if not rows:
        return 0
    stmt = sqlite_insert(model.__table__).values(rows)
    update_dict = {
        col: stmt.excluded[col]
        for col in rows[0].keys()
        if col not in key_cols
    }
    stmt = stmt.on_conflict_do_update(index_elements=key_cols, set_=update_dict)
    session.execute(stmt)
    return len(rows)
