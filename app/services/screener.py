"""选股器核心：指标注册表 / 特征计算 / DSL 过滤 / 内置策略。

只依赖 DB（pandas 计算），与 akshare 在调用层彻底解耦——所有计算基于
``stock_daily_bars`` + ``stock_fund_flow_daily`` + 实时快照（基础组指标）。

性能：2000 只 × 120 日 pandas 计算 < 3s。特征帧以 ``(latest_date, universe_hash)``
为 key 缓存 10 分钟，回补完成时主动失效。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import ScreenerPreset, StockDailyBar, StockFundFlowDaily
from app.services.daily_bars import BoardPrefixes


logger = logging.getLogger(__name__)


# ---------------- 内置预设 ----------------


BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "name": "放量突破",
        "description": "量价资金三重确认的平台突破，不追涨停",
        "conditions": [
            {"indicator": "platform_breakout", "op": "==", "value": 1},
            {"indicator": "volume_ratio", "op": "between", "value": [2.0, 5.0]},
            {"indicator": "change_pct", "op": ">=", "value": 3.0},
            {"indicator": "limit_up_today", "op": "==", "value": 0},
            {"indicator": "close_vs_ma20", "op": ">=", "value": 0},
            {"indicator": "main_net_inflow", "op": ">", "value": 0},
        ],
        "order_by": "main_net_inflow_5d",
        "order": "desc",
    },
    {
        "name": "趋势多头",
        "description": "顺势低吸，震荡向上市",
        "conditions": [
            {"indicator": "ma_bullish", "op": "==", "value": 1},
            {"indicator": "close_vs_ma20", "op": ">=", "value": 0},
            {"indicator": "change_20d", "op": "between", "value": [5.0, 35.0]},
            {"indicator": "turnover_rate", "op": "between", "value": [3.0, 15.0]},
            {"indicator": "main_net_inflow_5d", "op": ">", "value": 0},
        ],
        "order_by": "change_20d",
        "order": "desc",
    },
    {
        "name": "连续小阳",
        "description": "温和吸筹，回避急涨",
        "conditions": [
            {"indicator": "consecutive_up_days", "op": ">=", "value": 4},
            {"indicator": "change_pct", "op": "<", "value": 5.0},
            {"indicator": "change_10d", "op": "<", "value": 18.0},
            {"indicator": "volume_ratio", "op": "between", "value": [1.0, 2.5]},
            {"indicator": "close_vs_ma10", "op": ">=", "value": 0},
        ],
        "order_by": "consecutive_up_days",
        "order": "desc",
    },
    {
        "name": "缩量回踩",
        "description": "上升趋势中的缩量回调买点",
        "conditions": [
            {"indicator": "close_vs_ma20", "op": "between", "value": [-3.0, 3.0]},
            {"indicator": "change_3d", "op": "<", "value": 0},
            {"indicator": "volume_ratio", "op": "<=", "value": 0.7},
            {"indicator": "change_20d", "op": ">", "value": 10.0},
            {"indicator": "macd_dif", "op": ">", "value": 0},
        ],
        "order_by": "change_3d",
        "order": "asc",
    },
    {
        "name": "主力抢筹",
        "description": "资金先行、价格未充分拉升；市值归一化避免偏大盘",
        "conditions": [
            {"indicator": "main_net_inflow_days", "op": ">=", "value": 3},
            {"indicator": "main_net_inflow_5d_pct_mv", "op": ">", "value": 0.5},
            {"indicator": "change_5d", "op": "<", "value": 20.0},
            {"indicator": "rsi14", "op": "<", "value": 75.0},
        ],
        "order_by": "main_net_inflow_5d_pct_mv",
        "order": "desc",
    },
    {
        "name": "超跌反弹",
        "description": "左侧反弹，需配合仓位控制",
        "conditions": [
            {"indicator": "change_20d", "op": "<", "value": -15.0},
            {"indicator": "rsi14", "op": "<", "value": 30.0},
            {"indicator": "volume_ratio", "op": ">=", "value": 1.5},
            {"indicator": "change_pct", "op": ">", "value": 0},
        ],
        "order_by": "rsi14",
        "order": "asc",
    },
]


# ---------------- 指标注册表 ----------------

INDICATOR_REGISTRY: dict[str, dict[str, Any]] = {
    # basic (from realtime)
    "latest_price": {"label": "最新价", "group": "基础", "unit": "yuan", "default_op": "between", "default_value": [0, 10000], "source": "realtime"},
    "change_pct": {"label": "今日涨跌幅", "group": "基础", "unit": "%", "default_op": "between", "default_value": [-10, 10]},
    "total_mv": {"label": "总市值", "group": "基础", "unit": "yuan", "default_op": ">=", "default_value": 1e10},
    "float_mv": {"label": "流通市值", "group": "基础", "unit": "yuan", "default_op": ">=", "default_value": 5e9},
    "pe_dynamic": {"label": "市盈率(动)", "group": "基础", "unit": "x", "default_op": "between", "default_value": [0, 200], "nullable": True},
    "pb": {"label": "市净率", "group": "基础", "unit": "x", "default_op": "between", "default_value": [0, 30], "nullable": True},
    "turnover_rate": {"label": "换手率", "group": "基础", "unit": "%", "default_op": "between", "default_value": [0.5, 30]},
    # trend
    "ma5": {"label": "MA5", "group": "趋势", "unit": "yuan"},
    "ma10": {"label": "MA10", "group": "趋势", "unit": "yuan"},
    "ma20": {"label": "MA20", "group": "趋势", "unit": "yuan"},
    "ma60": {"label": "MA60", "group": "趋势", "unit": "yuan"},
    "close_vs_ma5": {"label": "收盘价/MA5（%）", "group": "趋势", "unit": "%", "default_op": ">=", "default_value": -2},
    "close_vs_ma10": {"label": "收盘价/MA10（%）", "group": "趋势", "unit": "%", "default_op": ">=", "default_value": -3},
    "close_vs_ma20": {"label": "收盘价/MA20（%）", "group": "趋势", "unit": "%", "default_op": ">=", "default_value": -5},
    "close_vs_ma60": {"label": "收盘价/MA60（%）", "group": "趋势", "unit": "%"},
    "ma_bullish": {"label": "均线多头排列", "group": "趋势", "unit": "0/1", "default_op": "==", "default_value": 1},
    "golden_cross_recent": {"label": "近5日MA5上穿MA10", "group": "趋势", "unit": "0/1", "default_op": "==", "default_value": 1},
    "death_cross_recent": {"label": "近5日MA5下穿MA10", "group": "趋势", "unit": "0/1"},
    "high_20d_break": {"label": "突破20日新高", "group": "趋势", "unit": "0/1"},
    "high_60d_break": {"label": "突破60日新高", "group": "趋势", "unit": "0/1"},
    "low_20d_break": {"label": "跌破20日新低", "group": "趋势", "unit": "0/1"},
    # momentum
    "change_3d": {"label": "3日涨幅", "group": "动量", "unit": "%"},
    "change_5d": {"label": "5日涨幅", "group": "动量", "unit": "%"},
    "change_10d": {"label": "10日涨幅", "group": "动量", "unit": "%"},
    "change_20d": {"label": "20日涨幅", "group": "动量", "unit": "%"},
    "consecutive_up_days": {"label": "连涨天数", "group": "动量", "unit": "天", "default_op": ">=", "default_value": 3},
    "consecutive_down_days": {"label": "连跌天数", "group": "动量", "unit": "天"},
    "rsi6": {"label": "RSI6", "group": "动量", "unit": "x"},
    "rsi14": {"label": "RSI14", "group": "动量", "unit": "x"},
    "macd_dif": {"label": "MACD DIF", "group": "动量", "unit": "x"},
    "macd_dea": {"label": "MACD DEA", "group": "动量", "unit": "x"},
    "macd_hist": {"label": "MACD 柱", "group": "动量", "unit": "x"},
    "macd_golden_recent": {"label": "近3日MACD金叉", "group": "动量", "unit": "0/1"},
    "bias20": {"label": "乖离率20", "group": "动量", "unit": "%"},
    # volume
    "volume_ratio": {"label": "量比（当日/前5日均量）", "group": "量能", "unit": "x", "default_op": "between", "default_value": [0.8, 5]},
    "amount": {"label": "今日成交额", "group": "量能", "unit": "yuan"},
    "amount_ma5": {"label": "5日均成交额", "group": "量能", "unit": "yuan"},
    "turnover_ma5": {"label": "5日均换手率", "group": "量能", "unit": "%"},
    "volume_up_days": {"label": "连续放量天数", "group": "量能", "unit": "天"},
    # pattern
    "limit_up_today": {"label": "当日涨停(代码自适应)", "group": "形态", "unit": "0/1", "default_op": "==", "default_value": 0},
    "limit_up_count_5d": {"label": "近5日涨停次数", "group": "形态", "unit": "次"},
    "platform_breakout": {"label": "平台突破(收盘>前20日最高)", "group": "形态", "unit": "0/1", "default_op": "==", "default_value": 1},
    "gap_up_pct": {"label": "跳空缺口(%)", "group": "形态", "unit": "%"},
    "lower_shadow_ratio": {"label": "下影线占比", "group": "形态", "unit": "%"},
    # fundflow
    "main_net_inflow": {"label": "主力净流入(今日)", "group": "资金流", "unit": "yuan", "default_op": ">", "default_value": 0},
    "main_net_inflow_5d": {"label": "5日主力净流入", "group": "资金流", "unit": "yuan", "default_op": ">", "default_value": 0},
    "main_net_inflow_10d": {"label": "10日主力净流入", "group": "资金流", "unit": "yuan"},
    "main_net_inflow_days": {"label": "连续净流入天数", "group": "资金流", "unit": "天", "default_op": ">=", "default_value": 3},
    "main_net_ratio": {"label": "主力净占比(今日)", "group": "资金流", "unit": "%"},
    "super_large_net": {"label": "超大单净额", "group": "资金流", "unit": "yuan"},
    "main_net_inflow_5d_pct_mv": {"label": "5日主力净流入/流通市值(%)", "group": "资金流", "unit": "%", "default_op": ">", "default_value": 0.5, "nullable": True},
}


SUPPORTED_OPS = ("==", "!=", ">", ">=", "<", "<=", "between")

# ----------------- ScreenerService -----------------


class ScreenerService:
    """选股器服务：特征计算、DSL 过滤、预设管理。"""

    CACHE_TTL_SECONDS = 600
    WARN_NO_FUND_FLOW = "资金流数据尚未回填；资金类条件被跳过"
    WARN_RSI_LIMITED = "RSI 在历史不足时返回近似值"
    WARN_LIMITED_BARS = "部分股票日线不足 60 日，相关指标返回 NaN"

    def __init__(self, daily_bars_service: Any | None = None) -> None:
        self.daily_bars = daily_bars_service
        self._cache: dict[tuple, tuple[float, dict[str, Any]]] = {}

    # ---------------- public API -----------------

    def indicators_payload(self) -> dict[str, Any]:
        """指标注册表，前端直接使用。"""
        groups: dict[str, list[dict[str, Any]]] = {}
        for name, meta in INDICATOR_REGISTRY.items():
            groups.setdefault(meta["group"], []).append({"name": name, **meta})
        return {
            "groups": [
                {"name": g, "indicators": items} for g, items in groups.items()
            ],
            "ops": list(SUPPORTED_OPS),
        }

    def get_preset(self, session: Session, preset_id: int) -> dict[str, Any] | None:
        """单条 GET: 按 id 读预设, 用于前端"打开即看 + 克隆"。"""
        row = session.get(ScreenerPreset, preset_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "conditions": json.loads(row.conditions_json or "[]"),
            "universe": json.loads(row.universe_json or "{}"),
            "order_by": row.order_by,
            "order": row.order,
            "is_builtin": bool(row.is_builtin),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def list_presets(self, session: Session) -> list[dict[str, Any]]:
        rows = list(session.scalars(select(ScreenerPreset).order_by(ScreenerPreset.id)))
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "conditions": json.loads(row.conditions_json or "[]"),
                "universe": json.loads(row.universe_json or "{}"),
                "order_by": row.order_by,
                "order": row.order,
                "is_builtin": bool(row.is_builtin),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

    def save_preset(
        self,
        session: Session,
        *,
        name: str,
        description: str | None,
        conditions: list[dict[str, Any]],
        universe: dict[str, Any] | None = None,
        order_by: str | None = None,
        order: str = "desc",
    ) -> dict[str, Any]:
        existing = session.scalar(select(ScreenerPreset).where(ScreenerPreset.name == name))
        if existing is not None and existing.is_builtin:
            raise PermissionError(f"内置预设 [{name}] 不可覆盖")
        if existing is None:
            row = ScreenerPreset(
                name=name,
                description=description,
                conditions_json=json.dumps(conditions, ensure_ascii=False),
                universe_json=json.dumps(universe or {}, ensure_ascii=False),
                order_by=order_by,
                order=order,
                is_builtin=False,
            )
            session.add(row)
        else:
            existing.description = description
            existing.conditions_json = json.dumps(conditions, ensure_ascii=False)
            existing.universe_json = json.dumps(universe or {}, ensure_ascii=False)
            existing.order_by = order_by
            existing.order = order
            row = existing
        session.commit()
        return {"id": row.id, "name": row.name, "is_builtin": False}

    def delete_preset(self, session: Session, preset_id: int) -> bool:
        row = session.get(ScreenerPreset, preset_id)
        if row is None:
            return False
        if row.is_builtin:
            raise PermissionError(f"内置预设 [{row.name}] 不可删除")
        session.delete(row)
        session.commit()
        return True

    def seed_builtin_presets(self, session: Session) -> int:
        """启动时按 name 幂等写入内置预设。返回实际新增数量。"""
        added = 0
        for preset in BUILTIN_PRESETS:
            existing = session.scalar(
                select(ScreenerPreset).where(ScreenerPreset.name == preset["name"])
            )
            if existing is None:
                row = ScreenerPreset(
                    name=preset["name"],
                    description=preset.get("description"),
                    conditions_json=json.dumps(preset["conditions"], ensure_ascii=False),
                    universe_json=json.dumps({}, ensure_ascii=False),
                    order_by=preset.get("order_by"),
                    order=preset.get("order", "desc"),
                    is_builtin=True,
                )
                session.add(row)
                added += 1
        if added:
            session.commit()
        return added

    def run(
        self,
        session: Session,
        request: dict[str, Any],
        *,
        realtime_lookup: Callable[[list[str]], dict[str, dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """执行一次筛选。

        ``request``::

            {
              "conditions": [{"indicator": str, "op": str, "value": number|list}],
              "universe": {"min_amount": 50_000_000, "exclude_st": True, "boards": [...]},
              "order_by": str,
              "order": "asc"|"desc",
              "limit": int,
              "preset_id": int  (可选，等价于预设)
            }
        """
        conditions = list(request.get("conditions") or [])
        # 关键修复: 当 request 同时带 conditions(非空)且带 preset_id 时,
        # 用户条件优先, preset 只提供 universe 兜底和 order_by 默认。
        # 旧逻辑无条件用 preset conditions -> 用户在 builder 里改条件会被静默覆盖(2026-07-20 reported)
        user_conditions_present = bool(conditions)
        if request.get("preset_id"):
            row = session.get(ScreenerPreset, int(request["preset_id"]))
            if row is None:
                raise KeyError(f"preset_id {request['preset_id']} 不存在")
            preset_conditions = json.loads(row.conditions_json or "[]")
            if not user_conditions_present:
                conditions = preset_conditions
            order_by_default = row.order_by or "change_pct"
            order_default = row.order or "desc"
        else:
            order_by_default = "change_pct"
            order_default = "desc"
        order_by = request.get("order_by") or order_by_default
        order = request.get("order") or order_default
        # 优先使用请求里的 universe；preset 只在请求未传时提供默认（避免覆盖用户显式选择）
        preset_universe = self._safe_universe_from_preset(session, request)
        request_universe = request.get("universe") or {}
        universe_cfg = {**preset_universe, **request_universe}

        codes_filter = self._resolve_codes(session, universe_cfg)
        feature_payload = self._compute_features(session, codes_filter, request=request, universe_hash=_hash_universe(codes_filter))
        df: pd.DataFrame = feature_payload["frame"]
        warnings: list[str] = list(feature_payload["warnings"])

        # 资金流降级
        referenced = {c["indicator"] for c in conditions}
        if referenced & _FUNDFLOW_INDICATORS and feature_payload["flow_universe_size"] == 0:
            warnings.append(self.WARN_NO_FUND_FLOW)

        filtered = apply_dsl(df, conditions)
        limit = int(request.get("limit") or 100)
        if limit > 0:
            ascending = (order or "desc") == "asc"
            sort_col = order_by if order_by in filtered.columns else "change_pct"
            if sort_col not in filtered.columns:
                sort_col = "change_pct"
            filtered = filtered.sort_values(sort_col, ascending=ascending, na_position="last").head(limit)

        results = [_row_to_result(row) for _, row in filtered.iterrows()]
        return {
            "data_date": feature_payload["data_date"],
            "total": int(len(filtered)),
            "results": results,
            "warnings": warnings,
        }

    def invalidate_cache(self) -> None:
        self._cache.clear()

    # ---------------- internals -----------------

    def _safe_universe_from_preset(self, session: Session, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("preset_id"):
            row = session.get(ScreenerPreset, int(request["preset_id"]))
            if row is None:
                return {}
            try:
                return json.loads(row.universe_json or "{}")
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _resolve_codes(self, session: Session, universe_cfg: dict[str, Any]) -> list[str]:
        if self.daily_bars is None:
            return []
        # 客户端 boards 过滤
        boards = universe_cfg.get("boards") or ["main", "cyb", "kcb"]
        exclude_st = bool(universe_cfg.get("exclude_st", True))
        min_amount = float(universe_cfg.get("min_amount", 50_000_000.0))
        universe = self.daily_bars.get_universe(session, min_amount=min_amount)
        if universe.empty:
            return []
        df = universe
        if exclude_st:
            mask = df["name"].astype(str).str.contains("ST|\\*ST|PT|退", regex=True, na=False)
            df = df[~mask]
        allowed_prefixes: set[str] = set()
        for board in boards:
            for prefix in BoardPrefixes.get(board, ()):
                allowed_prefixes.add(prefix)
        if allowed_prefixes:
            prefix_mask = df["code"].astype(str).str.startswith(tuple(allowed_prefixes))
            df = df[prefix_mask]
        return df["code"].astype(str).str.zfill(6).tolist()

    def _compute_features(
        self,
        session: Session,
        codes: list[str],
        *,
        request: dict[str, Any],
        universe_hash: str,
    ) -> dict[str, Any]:
        cache_key = ("features", universe_hash)
        now_ts = time.time()
        cached = self._cache.get(cache_key)
        if cached and now_ts - cached[0] < self.CACHE_TTL_SECONDS:
            return cached[1]

        latest_date = session.scalar(
            select(func.max(StockDailyBar.trading_date))
            .where(StockDailyBar.stock_code.in_(codes))
        )
        if latest_date is None:
            empty = _empty_frame()
            empty["data_date"] = None
            payload = {"frame": empty, "warnings": [self.WARN_LIMITED_BARS], "flow_universe_size": 0, "data_date": None}
            self._cache[cache_key] = (now_ts, payload)
            return payload

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
                .where(StockDailyBar.trading_date >= (latest_date - timedelta(days=120)))
                .order_by(StockDailyBar.stock_code, StockDailyBar.trading_date)
            )
        )
        if not rows:
            empty = _empty_frame()
            payload = {"frame": empty, "warnings": [self.WARN_LIMITED_BARS], "flow_universe_size": 0, "data_date": latest_date.isoformat()}
            self._cache[cache_key] = (now_ts, payload)
            return payload

        bars = pd.DataFrame(rows, columns=[
            "stock_code", "trading_date", "open", "close", "high", "low", "volume", "amount",
            "change_pct", "turnover_rate",
        ])
        bars["trading_date"] = pd.to_datetime(bars["trading_date"])

        latest_date_obj = latest_date.date() if hasattr(latest_date, "date") else latest_date
        flows = _load_fund_flow(session, codes, latest_date)
        frame = compute_features(bars, flows, latest_date_obj)

        # realtime 字段（pe/pb/turnover_rate/total_mv/float_mv/latest_price）
        # 注意：传 callable 时才能合入实时字段（避免 isinstance(callable, Callable) 的 TypeError）
        realtime_value = request.get("_realtime_lookup")
        realtime_lookup = realtime_value if callable(realtime_value) else None
        if realtime_lookup:
            realtime_df = realtime_lookup(codes)
            if realtime_df is not None and not realtime_df.empty:
                frame = frame.merge(realtime_df, on="stock_code", how="left", suffixes=("", "_rt"))

        # 限定返回列
        keep_cols = [c for c in frame.columns if c in INDICATOR_REGISTRY or c in ("stock_code", "stock_name")]
        frame = frame.reindex(columns=keep_cols)
        warnings: list[str] = []
        if (bars["close"].isna().sum() if "close" in bars.columns else 0) > 0:
            warnings.append(self.WARN_LIMITED_BARS)
        flow_universe_size = flows["stock_code"].nunique() if "stock_code" in flows.columns else 0
        payload = {
            "frame": frame,
            "warnings": warnings,
            "flow_universe_size": int(flow_universe_size),
            "data_date": latest_date.isoformat(),
        }
        self._cache[cache_key] = (now_ts, payload)
        return payload


# ---------------- feature computation ----------------


def _load_fund_flow(session: Session, codes: list[str], latest_date: Any) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=["stock_code", "trading_date", "main_net_amount", "main_net_ratio", "super_large_net", "large_net"])
    # latest_date 可能是 date 或 datetime；统一转 date
    if hasattr(latest_date, "date"):
        cutoff = latest_date.date() - timedelta(days=30)
    else:
        cutoff = latest_date - timedelta(days=30)
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
            .where(StockFundFlowDaily.trading_date >= cutoff)
        )
    )
    if not rows:
        return pd.DataFrame(columns=["stock_code", "trading_date", "main_net_amount", "main_net_ratio", "super_large_net", "large_net"])
    df = pd.DataFrame(rows, columns=["stock_code", "trading_date", "main_net_amount", "main_net_ratio", "super_large_net", "large_net"])
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df


def compute_features(bars: pd.DataFrame, fund_flow: pd.DataFrame, latest_trading_date: date) -> pd.DataFrame:
    """根据 ``bars``（120 日） + ``fund_flow``（30 日）算特征帧。

    所有指标尽量向量化（groupby.transform），2000 只 × 120 日 < 3s。
    """
    if bars.empty:
        return _empty_frame()

    bars = bars.copy()
    bars.sort_values(["stock_code", "trading_date"], inplace=True)
    bars.reset_index(drop=True, inplace=True)
    grouped = bars.groupby("stock_code", sort=False)

    latest = grouped.tail(1).copy().reset_index(drop=True)
    latest_idx = latest.set_index("stock_code")

    # --- MA ---
    for n in (5, 10, 20, 60):
        ma_full = grouped["close"].transform(lambda s, n=n: s.rolling(n, min_periods=n).mean())
        latest[f"ma{n}"] = ma_full.groupby(bars["stock_code"]).tail(1).values
    for ma in ("ma5", "ma10", "ma20", "ma60"):
        latest[f"close_vs_{ma}"] = (latest["close"] - latest[ma]) / latest[ma] * 100.0
    latest["ma_bullish"] = (
        (latest["ma5"] > latest["ma10"])
        & (latest["ma10"] > latest["ma20"])
        & (latest["ma20"] > latest["ma60"])
    ).astype(int)

    # --- 金叉/死叉近 5 日 ---
    ma5_full = grouped["close"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    ma10_full = grouped["close"].transform(lambda s: s.rolling(10, min_periods=10).mean())
    bars["_cross_up"] = ((ma5_full > ma10_full) & (ma5_full.shift(1) <= ma10_full.shift(1))).fillna(False).astype(int)
    bars["_cross_down"] = ((ma5_full < ma10_full) & (ma5_full.shift(1) >= ma10_full.shift(1))).fillna(False).astype(int)
    recent5 = bars.groupby("stock_code").tail(5)
    latest["golden_cross_recent"] = latest["stock_code"].map(recent5.groupby("stock_code")["_cross_up"].max().fillna(0).astype(int)).fillna(0).astype(int)
    latest["death_cross_recent"] = latest["stock_code"].map(recent5.groupby("stock_code")["_cross_down"].max().fillna(0).astype(int)).fillna(0).astype(int)

    # --- 高低突破 ---
    bars["_high_20"] = grouped["high"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).max())
    bars["_high_60"] = grouped["high"].transform(lambda s: s.shift(1).rolling(60, min_periods=60).max())
    bars["_low_20"] = grouped["low"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).min())
    tail1 = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["high_20d_break"] = ((latest_idx["close"] > tail1["_high_20"]).fillna(False).astype(int)).reindex(latest["stock_code"]).fillna(0).astype(int).values
    latest["high_60d_break"] = ((latest_idx["close"] > tail1["_high_60"]).fillna(False).astype(int)).reindex(latest["stock_code"]).fillna(0).astype(int).values
    latest["low_20d_break"] = ((latest_idx["close"] < tail1["_low_20"]).fillna(False).astype(int)).reindex(latest["stock_code"]).fillna(0).astype(int).values

    # --- 涨跌幅 N 日 ---
    for n, label in [(3, "change_3d"), (5, "change_5d"), (10, "change_10d"), (20, "change_20d")]:
        then_vals = grouped["close"].transform(lambda s, n=n: s.shift(n)).groupby(bars["stock_code"]).tail(1).values
        with np.errstate(divide="ignore", invalid="ignore"):
            latest[label] = np.where(
                (then_vals != 0) & ~np.isnan(then_vals),
                (latest["close"].values - then_vals) / then_vals * 100.0,
                np.nan,
            )

    # --- 连涨/连跌 ---
    bars["_dir"] = np.sign(bars.groupby("stock_code")["close"].diff())
    latest["consecutive_up_days"] = latest["stock_code"].map(_tail_streak_sign(bars, 1)).fillna(0).astype(int)
    latest["consecutive_down_days"] = latest["stock_code"].map(_tail_streak_sign(bars, -1)).fillna(0).astype(int)

    # --- 量比 / 均量 / 均换手 ---
    bars["_vol_ma5"] = grouped["volume"].transform(lambda s: s.shift(1).rolling(5, min_periods=5).mean())
    tail1_vol = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["volume_ratio"] = (latest_idx["volume"] / tail1_vol["_vol_ma5"]).reindex(latest["stock_code"]).values
    latest["amount_ma5"] = grouped["amount"].transform(lambda s: s.rolling(5, min_periods=5).mean()).groupby(bars["stock_code"]).tail(1).values
    latest["turnover_ma5"] = grouped["turnover_rate"].transform(lambda s: s.rolling(5, min_periods=5).mean()).groupby(bars["stock_code"]).tail(1).values

    # --- 连续放量天数 ---
    bars["_vol_up"] = (bars.groupby("stock_code")["volume"].diff() > 0).astype(int)
    latest["volume_up_days"] = latest["stock_code"].map(_tail_streak_flag(bars, "_vol_up")).fillna(0).astype(int)

    # --- RSI6 / RSI14 ---
    delta = bars.groupby("stock_code")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    for n, label in [(6, "rsi6"), (14, "rsi14")]:
        avg_gain = gain.groupby(bars["stock_code"]).transform(lambda s, n=n: s.rolling(n, min_periods=n).mean())
        avg_loss = loss.groupby(bars["stock_code"]).transform(lambda s, n=n: s.rolling(n, min_periods=n).mean())
        # avg_loss==0（持续上涨）时 RSI=100；avg_gain==0（持续下跌）时 RSI=0
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        rsi = rsi.where(~np.isnan(rs), np.where(avg_loss == 0, 100.0, 0.0))
        bars[label] = rsi
    tail1c = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["rsi6"] = latest["stock_code"].map(tail1c["rsi6"]).values
    latest["rsi14"] = latest["stock_code"].map(tail1c["rsi14"]).values

    # --- MACD(12,26,9) ---
    ema12 = bars.groupby("stock_code")["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema26 = bars.groupby("stock_code")["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
    dif = ema12 - ema26
    dea = dif.groupby(bars["stock_code"]).transform(lambda s: s.ewm(span=9, adjust=False).mean())
    bars["_dif"], bars["_dea"], bars["_hist"] = dif, dea, (dif - dea) * 2
    tail1d = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["macd_dif"] = latest["stock_code"].map(tail1d["_dif"]).values
    latest["macd_dea"] = latest["stock_code"].map(tail1d["_dea"]).values
    latest["macd_hist"] = latest["stock_code"].map(tail1d["_hist"]).values
    bars["_macd_cross_up"] = ((dif > dea) & (dif.shift(1) <= dea.shift(1))).fillna(False).astype(int)
    recent3 = bars.groupby("stock_code").tail(3)
    latest["macd_golden_recent"] = latest["stock_code"].map(recent3.groupby("stock_code")["_macd_cross_up"].max().fillna(0).astype(int)).fillna(0).astype(int)

    latest["bias20"] = (latest["close"] - latest["ma20"]) / latest["ma20"] * 100.0

    # --- 形态（涨停判定向量化） ---
    codes = bars["stock_code"].astype(str)
    is_cyb_kcb = codes.str.startswith(("300", "301", "688", "689"))
    threshold = np.where(is_cyb_kcb, 19.8, 9.8)
    change_vals = pd.to_numeric(bars["change_pct"], errors="coerce").values
    bars["is_limit_up"] = np.where(
        ~np.isnan(change_vals) & (change_vals >= threshold),
        1,
        0,
    )
    # latest 的 limit_up_today：按 stock_code 取最后一日
    tail1g = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["limit_up_today"] = latest["stock_code"].map(tail1g["is_limit_up"]).fillna(0).astype(int).values

    last5 = bars.groupby("stock_code").tail(5)
    latest["limit_up_count_5d"] = latest["stock_code"].map(last5.groupby("stock_code")["is_limit_up"].sum()).fillna(0).astype(int)
    latest["platform_breakout"] = latest["high_20d_break"]

    bars["gap_up_pct"] = (bars["open"] / bars.groupby("stock_code")["close"].shift(1) - 1) * 100
    tail1e = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["gap_up_pct"] = latest["stock_code"].map(tail1e["gap_up_pct"]).values

    hl_range = bars["high"] - bars["low"]
    bars["lower_shadow_ratio"] = np.where(
        hl_range > 0,
        (bars[["open", "close"]].min(axis=1) - bars["low"]) / hl_range * 100,
        0,
    )
    tail1f = bars.groupby("stock_code").tail(1).set_index("stock_code")
    latest["lower_shadow_ratio"] = latest["stock_code"].map(tail1f["lower_shadow_ratio"]).values

    # --- 资金流 ---
    if not fund_flow.empty:
        fund_flow = fund_flow.copy()
        fund_flow.sort_values(["stock_code", "trading_date"], inplace=True)
        fund_grouped = fund_flow.groupby("stock_code", sort=False)
        for n, col in [(1, "main_net_inflow"), (5, "main_net_inflow_5d"), (10, "main_net_inflow_10d")]:
            tail = fund_grouped.tail(n).groupby("stock_code")["main_net_amount"].sum(min_count=1)
            latest[col] = latest["stock_code"].map(tail)
        latest["main_net_inflow_days"] = latest["stock_code"].map(_consecutive_inflow_days(fund_flow))
        flow_tail = fund_grouped.tail(1).set_index("stock_code")
        latest["main_net_ratio"] = latest["stock_code"].map(flow_tail["main_net_ratio"]).values
        latest["super_large_net"] = latest["stock_code"].map(flow_tail["super_large_net"]).values
        if "float_mv" in latest.columns:
            mv = latest.set_index("stock_code")["float_mv"]
            net5 = latest.set_index("stock_code")["main_net_inflow_5d"]
            with np.errstate(divide="ignore", invalid="ignore"):
                latest["main_net_inflow_5d_pct_mv"] = np.where(
                    (mv != 0) & ~np.isnan(mv) & ~np.isnan(net5),
                    net5 / mv * 100.0,
                    np.nan,
                )
        else:
            latest["main_net_inflow_5d_pct_mv"] = np.nan
    else:
        for col in [
            "main_net_inflow", "main_net_inflow_5d", "main_net_inflow_10d",
            "main_net_inflow_days", "main_net_ratio", "super_large_net",
            "main_net_inflow_5d_pct_mv",
        ]:
            latest[col] = np.nan

    if "stock_name" not in latest.columns:
        latest["stock_name"] = latest["stock_code"]

    return latest


def _tail_streak_sign(bars: pd.DataFrame, sign: int) -> pd.Series:
    """从末尾向前数连续 sign 方向的天数。"""
    def _streak(series: pd.Series) -> int:
        count = 0
        for value in reversed(series.tolist()):
            if value == sign:
                count += 1
            else:
                break
        return count
    return bars.groupby("stock_code")["_dir"].apply(_streak)


def _tail_streak_flag(bars: pd.DataFrame, col: str) -> pd.Series:
    """从末尾向前数连续 flag==1 的天数。"""
    def _streak(series: pd.Series) -> int:
        count = 0
        for value in reversed(series.tolist()):
            if value == 1:
                count += 1
            else:
                break
        return count
    return bars.groupby("stock_code")[col].apply(_streak)


def _empty_frame() -> pd.DataFrame:
    cols = list(INDICATOR_REGISTRY.keys()) + ["stock_code", "stock_name"]
    return pd.DataFrame(columns=cols)


def _consecutive_inflow_days(fund_flow: pd.DataFrame) -> pd.Series:
    out: dict[str, int] = {}
    for code, group in fund_flow.groupby("stock_code", sort=False):
        series = group.sort_values("trading_date")["main_net_amount"].tolist()
        count = 0
        for value in reversed(series):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                break
            if value > 0:
                count += 1
            else:
                break
        out[code] = count
    return pd.Series(out)


def _is_limit_up(code: object, change_pct: object | None) -> bool:
    if change_pct is None or (isinstance(change_pct, float) and pd.isna(change_pct)):
        return False
    threshold = 9.8
    code_str = str(code or "")
    if code_str.startswith(("300", "301", "688", "689")):
        threshold = 19.8
    return float(change_pct) >= threshold


def _hash_universe(codes: list[str]) -> str:
    text = ",".join(sorted(codes))
    return hashlib.md5(text.encode("utf-8")).hexdigest()  # noqa: S324 (内部摘要)


# ---------------- DSL ----------------


_FUNDFLOW_INDICATORS = {
    "main_net_inflow",
    "main_net_inflow_5d",
    "main_net_inflow_10d",
    "main_net_inflow_days",
    "main_net_ratio",
    "super_large_net",
    "main_net_inflow_5d_pct_mv",
}


def apply_dsl(frame: pd.DataFrame, conditions: list[dict[str, Any]]) -> pd.DataFrame:
    """DSL 过滤。

    条件形如 ``{"indicator": str, "op": str, "value": number | [lo, hi]}``。
    仅对 frame 中存在的指标生效；缺失列（资金流未回填）整列视为 NaN，逻辑上
    不满足（除非 ``== NaN`` 类型——目前不支持）。
    """
    if frame.empty or not conditions:
        return frame
    masks: list[pd.Series] = []
    for condition in conditions:
        indicator = condition.get("indicator")
        op = condition.get("op")
        value = condition.get("value")
        if indicator not in INDICATOR_REGISTRY:
            continue
        if indicator not in frame.columns:
            # 缺失列视为不满足：给一张全 False 的 mask
            masks.append(pd.Series([False] * len(frame), index=frame.index))
            continue
        col = pd.to_numeric(frame[indicator], errors="coerce")
        mask = _op_mask(col, op, value)
        masks.append(mask)
    if not masks:
        return frame
    combined = masks[0]
    for mask in masks[1:]:
        combined = combined & mask
    return frame[combined]


def _op_mask(series: pd.Series, op: str | None, value: Any) -> pd.Series:
    if op == "between":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return pd.Series([True] * len(series), index=series.index)
        lo, hi = sorted(float(v) for v in value)
        return series.between(lo, hi)
    if value is None:
        return pd.Series([True] * len(series), index=series.index)
    try:
        target = float(value)
    except (TypeError, ValueError):
        return pd.Series([True] * len(series), index=series.index)
    if op == "==":
        return series == target
    if op == "!=":
        return series != target
    if op == ">":
        return series > target
    if op == ">=":
        return series >= target
    if op == "<":
        return series < target
    if op == "<=":
        return series <= target
    return pd.Series([True] * len(series), index=series.index)


def _row_to_result(row: pd.Series) -> dict[str, Any]:
    payload = {
        "code": str(row.get("stock_code") or ""),
        "name": str(row.get("stock_name") or ""),
        "close": _maybe_float(row.get("close")),
        "change_pct": _maybe_float(row.get("change_pct")),
        "turnover_rate": _maybe_float(row.get("turnover_rate")),
        "volume_ratio": _maybe_float(row.get("volume_ratio")),
        "amount": _maybe_float(row.get("amount")),
        "main_net_inflow": _maybe_float(row.get("main_net_inflow")),
        "main_net_inflow_5d": _maybe_float(row.get("main_net_inflow_5d")),
    }
    # 条件引用到的指标值
    for name in INDICATOR_REGISTRY:
        if name not in payload and name in row.index:
            payload[name] = _maybe_float(row.get(name))
    return {k: v for k, v in payload.items() if v is not None or k in ("code", "name")}


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        if pd.isna(result):
            return None
        return result
    except (TypeError, ValueError):
        return None
