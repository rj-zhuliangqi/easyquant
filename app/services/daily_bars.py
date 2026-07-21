"""选股器本地日线库与资金流回补服务。

设计要点（v2 选股方案）：

- 逐只拉取日线做同步筛选不可行（0.5–1.5s/只）。本服务负责后台回补 + 维护
  本地数据库，前端筛选时纯离线计算。
- 价格统一前复权（``adjust="qfq"``）以保证除权日附近指标不断裂；
  ``volume/amount/turnover_rate`` 为原始值。
- 串行 + 0.2-0.3s 抖动避免触发限流；单只失败仅记录不中断。
- 资金流缺失时记入 ``warnings``，筛选引擎降级（跳过该条件）。
- ``self.progress["running"]`` 互斥锁防止并发回补。
- ``backfill_all(run_async=True)`` 入队即返回 ``{started, job_id}``，避免 Cloudflare
  tunnel 100s 读超时切断仍在跑的同步请求（参见 plan：选股器 524 根因）。
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
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
    stage: str = "idle"  # idle | bars | fund_flow | done | error
    done: int = 0
    total: int = 0
    failed: list[dict[str, str]] = field(default_factory=list)
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_breakdown: dict[str, int] = field(default_factory=dict)


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
        # fire-and-forget worker 状态（524 修复）
        self._bg_thread: threading.Thread | None = None
        self._job_id: str | None = None
        # _safe_fetch_* 捕获的最近一次真异常（key="bars"|"flow"，value="ExceptionType: msg"）
        self._last_fetch_error: dict[str, str] = {}

    # ---------------- public: query -----------------

    def coverage(self, session: Session) -> dict[str, Any]:
        """当前 stock_daily_bars / stock_fund_flow_daily 覆盖统计。"""
        bar_rows = session.scalar(select(func.count()).select_from(StockDailyBar)) or 0
        flow_rows = session.scalar(select(func.count()).select_from(StockFundFlowDaily)) or 0
        stock_count = session.scalar(
            select(func.count(func.distinct(StockDailyBar.stock_code)))
        ) or 0
        latest_date = session.scalar(select(func.max(StockDailyBar.trading_date)))
        flow_latest_date = session.scalar(select(func.max(StockFundFlowDaily.trading_date)))
        flow_stock_count = session.scalar(
            select(func.count(func.distinct(StockFundFlowDaily.stock_code)))
        ) or 0
        return {
            "bar_rows": int(bar_rows),
            "flow_rows": int(flow_rows),
            "stock_count": int(stock_count),
            "flow_stock_count": int(flow_stock_count),
            "latest_date": latest_date.isoformat() if latest_date else None,
            "flow_latest_date": flow_latest_date.isoformat() if flow_latest_date else None,
        }

    def latest_trading_date(self, session: Session) -> date | None:
        return session.scalar(select(func.max(StockDailyBar.trading_date)))

    # ---------------- universe -----------------

    def get_universe(
        self,
        session: Session,
        min_amount: float = 50_000_000.0,
        realtime_amounts: dict[str, float] | None = None,
        universe_as_of: date | None = None,
    ) -> pd.DataFrame:
        """从 ``individual_stock_snapshots`` 取最新一日的全市场快照，按规则过滤。

        过滤：
        - ST / *ST / 退市 (名称包含 ST、PT、*、退)
        - 北交所 (4/8/920 开头)
        - 停牌（net_amount 为 None 或 ≤0）
        - 成交额 < min_amount

        成交额优先使用 ``realtime_amounts``（由 ``fetch_individual_realtime()`` 提供，
        含 ``成交额`` 列），否则 fallback 到 ``net_amount``（保持向后兼容）。

        ``universe_as_of`` (2026-07-21)：指定历史日期时，优先从
        ``stock_realtime_eod`` 读 amount；用于历史回放。
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

        # 成交额：realtime_amounts 注入 > stock_realtime_eod (as_of) > snapshot.net_amount 兜底
        if realtime_amounts:
            df["amount"] = df["code"].map(realtime_amounts)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        elif universe_as_of is not None:
            # 2026-07-21: 历史回放 → stock_realtime_eod.amount
            from app.models import StockRealtimeEod  # 局部 import 避免循环
            eod_amounts = dict(session.execute(
                select(StockRealtimeEod.stock_code, StockRealtimeEod.amount).where(
                    StockRealtimeEod.trading_date == universe_as_of,
                )
            ).all())
            if eod_amounts:
                df["amount"] = df["code"].map(
                    {str(k).zfill(6): v for k, v in eod_amounts.items()}
                )
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            else:
                df["amount"] = pd.to_numeric(df["net_amount"], errors="coerce")
        else:
            df["amount"] = pd.to_numeric(df["net_amount"], errors="coerce")

        # ST / *ST / 退市
        st_mask = df["name"].str.contains("ST|\\*ST|PT|退", case=False, regex=True, na=False)
        # 北交所
        bj_mask = df["code"].str.startswith(("4", "8", "920"))
        # 停牌（net_amount 缺失或 ≤0）
        suspended = df["net_amount"].isna() | (df["net_amount"].fillna(0) <= 0)
        # 成交额门槛
        amount_mask = df["amount"].fillna(0) >= min_amount

        kept = df[~st_mask & ~bj_mask & ~suspended & amount_mask].reset_index(drop=True)
        kept["latest_price"] = pd.to_numeric(kept["latest_price"], errors="coerce")
        kept["change_pct"] = pd.to_numeric(kept["change_pct"], errors="coerce")
        kept["amount"] = pd.to_numeric(kept["amount"], errors="coerce")
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
        session_or_factory: Session | Callable[[], Session],
        min_amount: float = 50_000_000.0,
        days: int = 150,
        code_limit: int | None = None,
        progress_cb: Callable[[DailyBarsProgress], None] | None = None,
        run_async: bool = False,
    ) -> dict[str, Any]:
        """二阶段回补：日线 → 资金流。

        ``session_or_factory``：
        - 同步模式（run_async=False，传 Session）：直接使用
        - 异步模式（run_async=True，传 callable）：worker 自建 Session（避免依赖 request 的 Depends session）

        ``code_limit`` 用于测试 / 冒烟（仅前 N 只）。

        ``run_async=True`` → 入队即返回 ``{started, job_id, already_running}``，实际工作在 daemon 线程跑。
        必须配合 callable factory（传 Session 会双线程争用同一对象 → sqlalchemy "concurrent operations"）。
        ``run_async=False``（默认）→ 阻塞执行（用于测试和单次脚本；main.py 显式传 True）。
        """
        with self._lock:
            if self.progress.running:
                return {"started": False, "already_running": True, "job_id": self._job_id, "progress": self._snapshot()}
            self.progress = DailyBarsProgress(
                running=True,
                stage="bars",
                started_at=self.now_provider(),
            )
            self._last_fetch_error = {}
            self._job_id = f"bf-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            job_id = self._job_id

        def _worker(session: Session) -> None:
            try:
                result = self._do_backfill(session, min_amount=min_amount, days=days, code_limit=code_limit, progress_cb=progress_cb)
                logger.info("backfill job %s done: %s", job_id, result.get("progress", {}).get("message"))
            except Exception as exc:  # noqa: BLE001
                logger.exception("backfill job %s crashed", job_id)
                self.progress.stage = "error"
                self.progress.message = f"回补异常：{exc}"
                self.progress.failed.append({"code": "-", "stage": "internal", "error": str(exc), "category": "internal"})
                self.progress.failure_breakdown["internal"] = self.progress.failure_breakdown.get("internal", 0) + 1
            finally:
                self.progress.running = False
                self.progress.finished_at = self.now_provider()

        def _run_async() -> None:
            session = session_or_factory() if callable(session_or_factory) else session_or_factory
            try:
                _worker(session)
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        if run_async:
            t = threading.Thread(target=_run_async, name=f"screener-backfill-{job_id}", daemon=True)
            t.start()
            self._bg_thread = t
            return {"started": True, "already_running": False, "job_id": job_id, "progress": self._snapshot()}
        else:
            session = session_or_factory if not callable(session_or_factory) else session_or_factory()
            try:
                _worker(session)
            finally:
                try:
                    session.close()
                except Exception:
                    pass
            return {"started": True, "already_running": False, "job_id": job_id, "progress": self._snapshot()}

    def _do_backfill(
        self,
        session: Session,
        *,
        min_amount: float,
        days: int,
        code_limit: int | None,
        progress_cb: Callable[[DailyBarsProgress], None] | None,
    ) -> dict[str, Any]:
        """backfill_all 的实际工作（原 backfill_all body）。"""
        # 拉一次实时快照（含成交额），用作 universe 过滤的真实依据
        realtime_amounts = self._safe_fetch_realtime_amounts()
        universe = self.get_universe(session, min_amount=min_amount, realtime_amounts=realtime_amounts)
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

    def wait_for_background_job(self, timeout: float | None = None) -> None:
        """测试用：等待后台线程结束（pytest fixture teardown）。"""
        thread = self._bg_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

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
            start = (self.now_provider().date() - timedelta(days=days)).strftime("%Y%m%d")
            end = self.now_provider().date().strftime("%Y%m%d")
            frame = self._safe_fetch_daily(code, start, end)
            if frame is None or frame.empty:
                _sleep_jitter()
                frame = self._safe_fetch_daily(code, start, end)
            if frame is None or frame.empty:
                category = self._categorize_failure("bars")
                self._last_fetch_error.pop("bars", None)
                self.progress.failed.append(
                    {"code": code, "stage": "bars", "error": "empty", "category": category}
                )
                self.progress.failure_breakdown[category] = self.progress.failure_breakdown.get(category, 0) + 1
            else:
                rows = _daily_history_to_rows(code, frame)
                if rows:
                    insert_rows(session, StockDailyBar, rows, key_cols=("stock_code", "trading_date"))
                    session.commit()

            self.progress.done = index + 1
            if progress_cb is not None and (index % 5 == 0 or index == len(codes) - 1):
                progress_cb(self._snapshot())
            _sleep_jitter()

    def _safe_fetch_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        try:
            return self.gateway.fetch_stock_daily_history(code, start, end, adjust="qfq")
        except Exception as exc:  # noqa: BLE001
            self._last_fetch_error["bars"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("fetch_stock_daily_history failed: %s exc=%s", code, exc)
            return pd.DataFrame()

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
            # 第一次拉取（gateway 内部已含 akshare→eastmoney fallback）
            frame = self._safe_fetch_fund_flow(code, market)
            # 第二次：瞬时限流重试 1 次（screener 文档约定）
            if frame is None or frame.empty:
                _sleep_jitter()
                frame = self._safe_fetch_fund_flow(code, market)
            if frame is None or frame.empty:
                category = self._categorize_failure("flow")
                self._last_fetch_error.pop("flow", None)
                self.progress.failed.append(
                    {"code": code, "stage": "fund_flow", "error": "empty", "category": category}
                )
                self.progress.failure_breakdown[category] = self.progress.failure_breakdown.get(category, 0) + 1
            else:
                rows = _fund_flow_history_to_rows(code, frame)
                if rows:
                    insert_rows(
                        session, StockFundFlowDaily, rows, key_cols=("stock_code", "trading_date")
                    )
                    session.commit()

            self.progress.done = index + 1
            if progress_cb is not None and (index % 5 == 0 or index == len(codes) - 1):
                progress_cb(self._snapshot())
            _sleep_jitter()

    def _safe_fetch_fund_flow(self, code: str, market: str) -> pd.DataFrame:
        """拉单只资金流，吞掉异常返回空 DataFrame。"""
        try:
            return self.gateway.fetch_stock_fund_flow_history(code, market)
        except Exception as exc:  # noqa: BLE001
            self._last_fetch_error["flow"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("fetch_stock_fund_flow_history failed: %s exc=%s", code, exc)
            return pd.DataFrame()

    def _categorize_failure(self, stage: str) -> str:
        """根据 ``_last_fetch_error`` 把失败归类到 network/proxy/parse/empty/other。

        - 真实异常（网络/解析/代理）: 来自 ``_safe_fetch_*`` 写入 ``_last_fetch_error``
        - 异常类别不存在: 返回 "empty"（数据源返回空但连接成功 — 通常是限流/无数据）
        """
        err = self._last_fetch_error.get(stage, "")
        if not err:
            return "empty"
        el = err.lower()
        if "timeout" in el or "aborted" in el or "timedout" in el:
            return "network"
        if "proxy" in el or "remote end closed" in el or "maxretry" in el:
            return "proxy"
        if "connection" in el or "remote disconnected" in el or "connectionerror" in el:
            return "network"
        if "json" in el or "parse" in el or "decode" in el or "valueerror" in el:
            return "parse"
        return "other"

    def _safe_fetch_realtime_amounts(self) -> dict[str, float]:
        """从 ``fetch_individual_realtime()`` 提取 ``code -> 成交额`` 映射。

        失败时返回空 dict，``get_universe`` 会 fallback 到 snapshot.net_amount。
        结果缓存 60s，避免 /api/screener/status 高频轮询拖慢响应。
        """
        now = self.now_provider()
        cached_at = getattr(self, "_realtime_amounts_cache_at", None)
        cached = getattr(self, "_realtime_amounts_cache", None)
        if cached is not None and cached_at and (now - cached_at).total_seconds() < 60:
            return cached
        try:
            frame = self.gateway.fetch_individual_realtime()
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_individual_realtime failed: %s", exc)
            return cached if cached is not None else {}
        if frame is None or frame.empty or "成交额" not in frame.columns:
            return cached if cached is not None else {}
        # 列名兼容: 新浪 path 返回 "代码"/"股票代码" 都能命中; 数据来自 INDIVIDUAL_EXTENDED_COLUMNS[0]="股票代码"。
        code_col = "股票代码" if "股票代码" in frame.columns else ("代码" if "代码" in frame.columns else None)
        if code_col is None:
            return cached if cached is not None else {}
        codes = frame[code_col].astype(str).str.zfill(6)
        amounts = pd.to_numeric(frame["成交额"], errors="coerce")
        result = dict(zip(codes, amounts))
        self._realtime_amounts_cache = result
        self._realtime_amounts_cache_at = now
        return result

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
            "failure_breakdown": dict(self.progress.failure_breakdown),
            "job_id": self._job_id,
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
