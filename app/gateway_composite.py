"""双源互备网关：TuShare 主 + AKShare 备。

TuShare 2000 档做 EOD 全量主源（按日期批量，稳定不受 Clash 影响）；AKShare 保留为
盘中实时 + 涨停池细分 + 逐只 fallback。主源失败/NotImplementedError 自动降级备源，
记录 source_snapshot（前端"数据来源"标签 + 降级告警）。

2025-08 TuShare 曾整体宕机一周 -> 每个数据域必须双源互备。本类把原散落在
``AkshareGateway`` 各方法里的 fallback 链上提一层，统一编排。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class CompositeGateway:
    """TuShare 主 + AKShare 备。``primary`` 通常为 TushareGateway，``fallback`` 为 AkshareGateway。"""

    def __init__(self, primary: Any, fallback: Any) -> None:
        self._primary = primary
        self._fallback = fallback
        self._source_snapshots: dict[str, dict[str, object]] = {}

    def _snapshot(self, key: str, *, source: str, fallback_used: bool, degraded_fields: list[str] | None = None, **meta: Any) -> None:
        snap: dict[str, object] = {
            "source_label": source,
            "updated_at": datetime.now().isoformat(),
            "fallback_used": fallback_used,
            "degraded_fields": degraded_fields or [],
        }
        if meta:
            snap["meta"] = {k: v for k, v in meta.items() if v is not None}
        self._source_snapshots[key] = snap

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        if key in self._source_snapshots:
            return self._source_snapshots[key]
        snap = self._primary.get_source_snapshot(key)
        if snap:
            return snap
        return self._fallback.get_source_snapshot(key)

    # ---- TuShare 批量方法（主源失败返回空，调用方 backfill_by_date 据此降级逐只）----
    def fetch_daily_by_date(self, trade_date: Any, *, qfq_baseline_adj: dict[str, float] | None = None) -> pd.DataFrame:
        try:
            df = self._primary.fetch_daily_by_date(trade_date, qfq_baseline_adj=qfq_baseline_adj)
            self._snapshot("daily_by_date", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_daily_by_date tushare 失败，返回空（调用方应降级逐只）", exc_info=True)
            self._snapshot("daily_by_date", source="tushare", fallback_used=True, degraded_fields=["daily"])
            return pd.DataFrame()

    def fetch_daily_basic_by_date(self, trade_date: Any) -> pd.DataFrame:
        try:
            df = self._primary.fetch_daily_basic_by_date(trade_date)
            self._snapshot("daily_basic_by_date", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_daily_basic_by_date tushare 失败", exc_info=True)
            self._snapshot("daily_basic_by_date", source="tushare", fallback_used=True, degraded_fields=["daily_basic"])
            return pd.DataFrame()

    def fetch_fund_flow_by_date(self, trade_date: Any) -> pd.DataFrame:
        try:
            df = self._primary.fetch_fund_flow_by_date(trade_date)
            self._snapshot("fund_flow_by_date", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_fund_flow_by_date tushare 失败", exc_info=True)
            self._snapshot("fund_flow_by_date", source="tushare", fallback_used=True, degraded_fields=["moneyflow"])
            return pd.DataFrame()

    def fetch_lhb_by_date(self, trade_date: Any) -> pd.DataFrame:
        try:
            df = self._primary.fetch_lhb_by_date(trade_date)
            self._snapshot("lhb_by_date", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_lhb_by_date tushare 失败", exc_info=True)
            self._snapshot("lhb_by_date", source="tushare", fallback_used=True, degraded_fields=["lhb"])
            return pd.DataFrame()

    def fetch_stk_limit_by_date(self, trade_date: Any) -> pd.DataFrame:
        try:
            df = self._primary.fetch_stk_limit_by_date(trade_date)
            self._snapshot("stk_limit_by_date", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_stk_limit_by_date tushare 失败", exc_info=True)
            self._snapshot("stk_limit_by_date", source="tushare", fallback_used=True, degraded_fields=["stk_limit"])
            return pd.DataFrame()

    def fetch_stock_basic(self) -> pd.DataFrame:
        try:
            df = self._primary.fetch_stock_basic()
            self._snapshot("stock_basic", source="tushare", fallback_used=df.empty, count=len(df))
            return df
        except Exception:  # noqa: BLE001
            logger.warning("fetch_stock_basic tushare 失败", exc_info=True)
            self._snapshot("stock_basic", source="tushare", fallback_used=True, degraded_fields=["stock_basic"])
            return pd.DataFrame()

    # ---- 逐只/通用方法：primary 优先，失败/NotImplementedError -> fallback ----
    def fetch_stock_daily_history(self, symbol: str, start: str, end: str, adjust: str = "") -> pd.DataFrame:
        try:
            return self._primary.fetch_stock_daily_history(symbol, start, end, adjust)
        except NotImplementedError:
            return self._fallback.fetch_stock_daily_history(symbol, start, end, adjust)
        except Exception:  # noqa: BLE001
            logger.warning("fetch_stock_daily_history tushare 失败，降级 AKShare: %s", symbol, exc_info=True)
            return self._fallback.fetch_stock_daily_history(symbol, start, end, adjust)

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        try:
            return self._primary.fetch_market_index_history(symbol, days)
        except NotImplementedError:
            return self._fallback.fetch_market_index_history(symbol, days)
        except Exception:  # noqa: BLE001
            logger.warning("fetch_market_index_history tushare 失败，降级 AKShare: %s", symbol, exc_info=True)
            return self._fallback.fetch_market_index_history(symbol, days)

    # ---- AKShare 独有方法（TuShare 2000 档无）：直接转发 fallback ----
    def fetch_individual_realtime(self) -> pd.DataFrame:
        return self._fallback.fetch_individual_realtime()

    def fetch_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        return self._fallback.fetch_limit_up_pool(date_str)

    def fetch_previous_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        return self._fallback.fetch_previous_limit_up_pool(date_str)

    def fetch_broken_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        return self._fallback.fetch_broken_limit_up_pool(date_str)

    def fetch_strong_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        return self._fallback.fetch_strong_limit_up_pool(date_str)

    # ---- 其余方法（板块/概念/资金流批量/龙虎榜明细等）：__getattr__ 透明转发 ----
    # primary 优先；NotImplementedError/AttributeError/Exception -> fallback
    def __getattr__(self, name: str) -> Any:
        # __getattr__ 仅在常规查找失败时调用；self._primary/_fallback 由 __init__ 设置，不递归。
        def wrapper(*args: Any, **kw: Any) -> Any:
            try:
                return getattr(self._primary, name)(*args, **kw)
            except (NotImplementedError, AttributeError):
                return getattr(self._fallback, name)(*args, **kw)
            except Exception:  # noqa: BLE001
                logger.warning("CompositeGateway.%s tushare 失败，降级 AKShare", name, exc_info=True)
                return getattr(self._fallback, name)(*args, **kw)
        return wrapper
