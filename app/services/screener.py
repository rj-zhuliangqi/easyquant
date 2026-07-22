"""选股器核心：指标注册表 / 特征计算 / DSL 过滤 / 内置策略。

只依赖 DB（pandas 计算），与 akshare 在调用层彻底解耦——所有计算基于
``stock_daily_bars`` + ``stock_fund_flow_daily`` + 实时快照（基础组指标）。

性能：2000 只 × 120 日 pandas 计算 < 3s。特征帧以 ``(universe_hash, as_of_date)``
为 key 缓存 10 分钟，回补完成时主动失效。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import (
    ScreenerPreset,
    ScreenerPresetHit,
    StockDailyBar,
    StockFundFlowDaily,
    StockIndicatorDaily,
    StockLhbDetail,
    StockLimitUpIndicator,
    StockRealtimeEod,
)
from app.services.daily_bars import BoardPrefixes


logger = logging.getLogger(__name__)


# ---------------- 内置预设 ----------------


BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "name": "放量突破",
        "description": "量价资金三重确认的平台突破，不追涨停",
        "category": "量价突破",
        # 评分模式 min_score=5：6 条满足 5 条即命中，容忍资金流缺失（push2 不通时仍可筛）
        "match_mode": "score",
        "min_score": 5,
        "conditions": [
            {"indicator": "platform_breakout", "op": "==", "value": 1, "weight": 2},
            {"indicator": "volume_ratio", "op": "between", "value": [2.0, 5.0], "weight": 2},
            {"indicator": "change_pct", "op": ">=", "value": 3.0, "weight": 1},
            {"indicator": "limit_up_today", "op": "==", "value": 0, "weight": 1},
            {"indicator": "close_vs_ma20", "op": ">=", "value": 0, "weight": 1},
            {"indicator": "main_net_inflow", "op": ">", "value": 0, "weight": 1},
        ],
        "order_by": "score",
        "order": "desc",
    },
    {
        "name": "趋势多头",
        "description": "顺势低吸，震荡向上市",
        "category": "趋势跟踪",
        # 5 条满足 4 条，容忍资金流缺失
        "match_mode": "score",
        "min_score": 4,
        "conditions": [
            {"indicator": "ma_bullish", "op": "==", "value": 1, "weight": 2},
            {"indicator": "close_vs_ma20", "op": ">=", "value": 0, "weight": 1},
            {"indicator": "change_20d", "op": "between", "value": [5.0, 35.0], "weight": 1},
            {"indicator": "turnover_rate", "op": "between", "value": [3.0, 15.0], "weight": 1},
            {"indicator": "main_net_inflow_5d", "op": ">", "value": 0, "weight": 1},
        ],
        "order_by": "score",
        "order": "desc",
    },
    {
        "name": "连续小阳",
        "description": "温和吸筹，回避急涨",
        "category": "量价突破",
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
        "category": "趋势跟踪",
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
        "description": "资金先行、价格未充分拉升；市值归一化避免偏大盘（依赖资金流，需 push2 通）",
        "category": "资金动向",
        # 全 AND：本策略核心就是资金流，缺数据时宁可不选不选错
        "match_mode": "all",
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
        "category": "趋势跟踪",
        "conditions": [
            {"indicator": "change_20d", "op": "<", "value": -15.0},
            {"indicator": "rsi14", "op": "<", "value": 30.0},
            {"indicator": "volume_ratio", "op": ">=", "value": 1.5},
            {"indicator": "change_pct", "op": ">", "value": 0},
        ],
        "order_by": "rsi14",
        "order": "asc",
    },
    {
        "name": "龙虎榜接力",
        "description": "机构净买入上榜股，顺势跟进（依赖龙虎榜，17:00 后出齐）",
        "category": "事件驱动",
        # 评分模式 min_score=4：lhb_today(2)+inst(2)=4 即命中，
        # 趋势/避涨停为加分项；lhb 缺数据时整体不出票（事件策略本就该等数据）
        "match_mode": "score",
        "min_score": 4,
        "conditions": [
            {"indicator": "lhb_today", "op": "==", "value": 1, "weight": 2},
            {"indicator": "lhb_inst_net_buy", "op": ">", "value": 0, "weight": 2},
            {"indicator": "close_vs_ma20", "op": ">=", "value": 0, "weight": 1},
            {"indicator": "limit_up_today", "op": "==", "value": 0, "weight": 1},
        ],
        "order_by": "score",
        "order": "desc",
    },
    {
        "name": "涨停接力",
        "description": "连板股次日跟踪，2 板起算（依赖涨停指标，16:10 后出齐）",
        "category": "事件驱动",
        # 全 AND：事件信号需精确，缺数据宁可不选
        "match_mode": "all",
        "conditions": [
            {"indicator": "consecutive_limit_up_days", "op": ">=", "value": 2},
            {"indicator": "limit_up_today", "op": "==", "value": 1},
            {"indicator": "volume_ratio", "op": "<=", "value": 5.0},
        ],
        "order_by": "consecutive_limit_up_days",
        "order": "desc",
    },
]


# ---------------- 指标注册表 ----------------

INDICATOR_REGISTRY: dict[str, dict[str, Any]] = {
    # basic (from realtime_eod; was previously "realtime" but unused in HTTP path)
    "latest_price": {"label": "最新价", "group": "基础", "unit": "yuan", "default_op": "between", "default_value": [0, 10000], "source": "realtime_eod"},
    "change_pct": {"label": "今日涨跌幅", "group": "基础", "unit": "%", "default_op": "between", "default_value": [-10, 10], "source": "realtime_eod"},
    "total_mv": {"label": "总市值", "group": "基础", "unit": "yuan", "default_op": ">=", "default_value": 1e10, "source": "realtime_eod"},
    "float_mv": {"label": "流通市值", "group": "基础", "unit": "yuan", "default_op": ">=", "default_value": 5e9, "source": "realtime_eod"},
    "pe_dynamic": {"label": "市盈率(动)", "group": "基础", "unit": "x", "default_op": "between", "default_value": [0, 200], "nullable": True, "source": "realtime_eod"},
    "pb": {"label": "市净率", "group": "基础", "unit": "x", "default_op": "between", "default_value": [0, 30], "nullable": True, "source": "realtime_eod"},
    "turnover_rate": {"label": "换手率", "group": "基础", "unit": "%", "default_op": "between", "default_value": [0.5, 30], "source": "realtime_eod"},
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
    "volume_ratio_strict": {"label": "严格量比（同分钟）", "group": "量能", "unit": "x", "nullable": True, "source": "limit_up_history", "default_op": "between", "default_value": [0.8, 5]},
    "amount": {"label": "今日成交额", "group": "量能", "unit": "yuan", "source": "realtime_eod"},
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
    # 涨停类指标（持久化于 stock_limit_up_indicators / stock_limit_up_history）
    "consecutive_limit_up_days": {"label": "连板数", "group": "形态", "unit": "板", "default_op": ">=", "default_value": 1, "source": "limit_up_indicators"},
    "sealed_amount": {"label": "封单金额", "group": "资金流", "unit": "yuan", "default_op": ">", "default_value": 0, "nullable": True, "source": "limit_up_indicators"},
    # 龙虎榜（实时从 stock_lhb_detail 聚合，表小不预计算；2026-07-22）
    "lhb_today": {"label": "当日龙虎榜上榜", "group": "事件", "unit": "0/1", "default_op": "==", "default_value": 1, "source": "lhb_detail"},
    "lhb_net_buy": {"label": "龙虎榜净买额", "group": "事件", "unit": "yuan", "default_op": ">", "default_value": 0, "nullable": True, "source": "lhb_detail"},
    "lhb_inst_net_buy": {"label": "龙虎榜机构净席位(买-卖)", "group": "事件", "unit": "席", "default_op": ">", "default_value": 0, "nullable": True, "source": "lhb_detail"},
}


SUPPORTED_OPS = ("==", "!=", ">", ">=", "<", "<=", "between")

# ----------------- ScreenerService -----------------


class ScreenerService:
    """选股器服务：特征计算、DSL 过滤、预设管理。"""

    CACHE_TTL_SECONDS = 600
    WARN_NO_FUND_FLOW = "资金流数据尚未回填；资金类条件被跳过"
    WARN_NO_LHB = "龙虎榜数据尚未入库（17:00 后出齐）；龙虎榜类条件被跳过"
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
            "category": row.category,
            "match_mode": row.match_mode,
            "min_score": row.min_score,
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
                "category": row.category,
                "match_mode": row.match_mode,
                "min_score": row.min_score,
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
        category: str = "量价突破",
        match_mode: str = "all",
        min_score: int = 0,
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
                category=category,
                match_mode=match_mode,
                min_score=min_score,
                is_builtin=False,
            )
            session.add(row)
        else:
            existing.description = description
            existing.conditions_json = json.dumps(conditions, ensure_ascii=False)
            existing.universe_json = json.dumps(universe or {}, ensure_ascii=False)
            existing.order_by = order_by
            existing.order = order
            existing.category = category
            existing.match_mode = match_mode
            existing.min_score = min_score
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
        """启动时按 name 幂等写入内置预设。返回实际新增数量。

        对已存在的内置预设，刷新 category/match_mode/min_score/description/conditions，
        保证代码侧迭代能同步到库（内置预设不可被用户改，全量覆盖安全）。
        """
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
                    category=preset.get("category", "量价突破"),
                    match_mode=preset.get("match_mode", "all"),
                    min_score=preset.get("min_score", 0),
                    is_builtin=True,
                )
                session.add(row)
                added += 1
            elif existing.is_builtin:
                # 内置预设：以代码为准刷新（用户改不了内置，覆盖安全）
                existing.description = preset.get("description")
                existing.conditions_json = json.dumps(preset["conditions"], ensure_ascii=False)
                existing.order_by = preset.get("order_by")
                existing.order = preset.get("order", "desc")
                existing.category = preset.get("category", "量价突破")
                existing.match_mode = preset.get("match_mode", "all")
                existing.min_score = preset.get("min_score", 0)
        if added:
            session.commit()
        return added

    # ---------------- 命中历史 (2026-07-22) ----------------

    def snapshot_preset_hits(self, session: Session, trading_date: date) -> dict[str, int]:
        """跑所有预设记录当日命中数 + 代码到 ``screener_preset_hits``。

        17:10 cron 调（此时 lhb 17:00 / indicators 16:30 均已就绪）。单预设失败不阻塞。
        缓存命中：8 个预设共享同一帧，第一个算完后续走缓存。

        Returns:
            {"snapshots": int, "total_hits": int}
        """
        presets = list(session.execute(select(ScreenerPreset)).scalars())
        snapshots = 0
        total_hits = 0
        now = self._now()
        for preset in presets:
            try:
                result = self.run(session, {"preset_id": preset.id, "limit": 100})
                hits = result.get("results") or []
                codes = [str(r.get("code")) for r in hits if r.get("code")]
                hit_count = int(result.get("total") or len(hits))
                self._upsert_hit(session, preset.id, trading_date, hit_count, codes, now)
                snapshots += 1
                total_hits += hit_count
            except Exception:  # noqa: BLE001
                logger.exception("snapshot_preset_hits: preset=%s 失败", preset.name)
                continue
        return {"snapshots": snapshots, "total_hits": total_hits}

    def get_hit_history(
        self, session: Session, preset_id: int, *, days: int = 5
    ) -> list[dict[str, Any]]:
        """返回某预设近 ``days`` 个交易日的命中快照（供前端"近 5 日命中数"）。"""
        rows = list(
            session.execute(
                select(ScreenerPresetHit)
                .where(ScreenerPresetHit.preset_id == preset_id)
                .order_by(ScreenerPresetHit.trading_date.desc())
                .limit(days)
            ).scalars()
        )
        return [
            {
                "trading_date": r.trading_date.isoformat() if r.trading_date else None,
                "hit_count": int(r.hit_count or 0),
                "hit_codes": json.loads(r.hit_codes or "[]"),
            }
            for r in reversed(rows)  # 时间升序
        ]

    @staticmethod
    def _upsert_hit(
        session: Session,
        preset_id: int,
        trading_date: date,
        hit_count: int,
        codes: list[str],
        now: datetime,
    ) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        capped = codes[:100]
        stmt = sqlite_insert(ScreenerPresetHit).values(
            preset_id=preset_id,
            trading_date=trading_date,
            hit_count=hit_count,
            hit_codes=json.dumps(capped, ensure_ascii=False),
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["preset_id", "trading_date"],
            set_={
                "hit_count": stmt.excluded.hit_count,
                "hit_codes": stmt.excluded.hit_codes,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        session.execute(stmt)
        session.commit()

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    # ---------------- 策略目录 / 个股详情 (2026-07-22 Phase 3) ----------------

    def strategies_catalog(self, session: Session) -> list[dict[str, Any]]:
        """策略商城目录：合并预设 + 近 5 日命中历史。

        每条：id/name/description/category/match_mode/min_score/conditions/
              is_builtin/order_by/order/hit_5d(近5日命中数列表)/avg_5d/total_5d。
        """
        presets = list(session.execute(select(ScreenerPreset).order_by(ScreenerPreset.id)).scalars())
        catalog: list[dict[str, Any]] = []
        for row in presets:
            hist = self.get_hit_history(session, row.id, days=5)
            counts = [h["hit_count"] for h in hist]
            total_5d = sum(counts)
            avg_5d = round(total_5d / len(counts), 1) if counts else 0.0
            try:
                conditions = json.loads(row.conditions_json or "[]")
            except Exception:  # noqa: BLE001
                conditions = []
            catalog.append({
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "category": row.category,
                "match_mode": row.match_mode,
                "min_score": row.min_score,
                "conditions": conditions,
                "is_builtin": row.is_builtin,
                "order_by": row.order_by,
                "order": row.order,
                "hit_5d": counts,
                "avg_5d": avg_5d,
                "total_5d": total_5d,
                "last_hit_date": hist[-1]["trading_date"] if hist else None,
            })
        return catalog

    def stock_detail(self, session: Session, code: str) -> dict[str, Any] | None:
        """个股抽屉详情：近 60 日 K 线 + 近期龙虎榜 + 最新指标 + 近期资金流。

        供前端 StockDrawer 渲染。code 缺失返回 None。
        """
        code = str(code).strip().zfill(6)
        if not code:
            return None

        # 近 60 日 K 线
        bar_rows = list(
            session.execute(
                select(
                    StockDailyBar.trading_date, StockDailyBar.open, StockDailyBar.close,
                    StockDailyBar.high, StockDailyBar.low, StockDailyBar.volume,
                    StockDailyBar.amount, StockDailyBar.change_pct, StockDailyBar.turnover_rate,
                )
                .where(StockDailyBar.stock_code == code)
                .order_by(StockDailyBar.trading_date.desc())
                .limit(60)
            )
        )
        if not bar_rows:
            return None
        kline = [
            {
                "date": r[0].isoformat() if r[0] else None,
                "open": _maybe_float(r[1]), "close": _maybe_float(r[2]),
                "high": _maybe_float(r[3]), "low": _maybe_float(r[4]),
                "volume": _maybe_float(r[5]), "amount": _maybe_float(r[6]),
                "change_pct": _maybe_float(r[7]), "turnover_rate": _maybe_float(r[8]),
            }
            for r in reversed(bar_rows)  # 升序
        ]
        name_row = session.execute(
            select(StockRealtimeEod.stock_name)
            .where(StockRealtimeEod.stock_code == code)
            .order_by(StockRealtimeEod.trading_date.desc())
            .limit(1)
        ).first()
        stock_name = name_row[0] if name_row else ""

        # 最新预计算指标
        ind = session.execute(
            select(StockIndicatorDaily)
            .where(StockIndicatorDaily.stock_code == code)
            .order_by(StockIndicatorDaily.trading_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        indicators = self._indicator_row_to_dict(ind) if ind else {}

        # 最新 EOD 基础组
        eod = session.execute(
            select(
                StockRealtimeEod.close, StockRealtimeEod.change_pct,
                StockRealtimeEod.turnover_rate, StockRealtimeEod.pe_dynamic,
                StockRealtimeEod.pb, StockRealtimeEod.total_mv, StockRealtimeEod.float_mv,
                StockRealtimeEod.trading_date,
            )
            .where(StockRealtimeEod.stock_code == code)
            .order_by(StockRealtimeEod.trading_date.desc())
            .limit(1)
        ).first()
        basics = {
            "latest_price": _maybe_float(eod[0]) if eod else None,
            "change_pct": _maybe_float(eod[1]) if eod else None,
            "turnover_rate": _maybe_float(eod[2]) if eod else None,
            "pe_dynamic": _maybe_float(eod[3]) if eod else None,
            "pb": _maybe_float(eod[4]) if eod else None,
            "total_mv": _maybe_float(eod[5]) if eod else None,
            "float_mv": _maybe_float(eod[6]) if eod else None,
            "data_date": eod[7].isoformat() if eod and eod[7] else None,
        } if eod else {}

        # 近 10 日资金流
        flow_rows = list(
            session.execute(
                select(
                    StockFundFlowDaily.trading_date, StockFundFlowDaily.main_net_amount,
                    StockFundFlowDaily.main_net_ratio, StockFundFlowDaily.super_large_net,
                )
                .where(StockFundFlowDaily.stock_code == code)
                .order_by(StockFundFlowDaily.trading_date.desc())
                .limit(10)
            )
        )
        fund_flow = [
            {
                "date": r[0].isoformat() if r[0] else None,
                "main_net": _maybe_float(r[1]),
                "main_net_ratio": _maybe_float(r[2]),
                "super_large_net": _maybe_float(r[3]),
            }
            for r in reversed(flow_rows)
        ]

        # 近 30 日龙虎榜
        lhb_rows = list(
            session.execute(
                select(
                    StockLhbDetail.trading_date, StockLhbDetail.reason,
                    StockLhbDetail.interpretation, StockLhbDetail.net_buy,
                    StockLhbDetail.inst_net_count,
                )
                .where(StockLhbDetail.stock_code == code)
                .order_by(StockLhbDetail.trading_date.desc())
                .limit(30)
            )
        )
        lhb = [
            {
                "date": r[0].isoformat() if r[0] else None,
                "reason": r[1], "interpretation": r[2],
                "net_buy": _maybe_float(r[3]), "inst_net_count": int(r[4] or 0),
            }
            for r in lhb_rows
        ]

        return {
            "code": code,
            "name": stock_name,
            "kline": kline,
            "indicators": indicators,
            "basics": basics,
            "fund_flow": fund_flow,
            "lhb": lhb,
        }

    @staticmethod
    def _indicator_row_to_dict(ind: Any) -> dict[str, Any]:
        """从 StockIndicatorDaily ORM 行抽取前端关心的关键指标。"""
        out: dict[str, Any] = {}
        for key in (
            "ma5", "ma10", "ma20", "ma60",
            "close_vs_ma20", "ma_bullish",
            "change_5d", "change_20d", "consecutive_up_days",
            "rsi14", "macd_dif", "macd_hist",
            "volume_ratio", "limit_up_today", "platform_breakout",
            "main_net_inflow", "main_net_inflow_5d", "main_net_inflow_days",
        ):
            val = getattr(ind, key, None)
            out[key] = _maybe_float(val)
        td = getattr(ind, "trading_date", None)
        out["data_date"] = td.isoformat() if td else None
        return out


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
        match_mode = str(request.get("match_mode") or "all")
        min_score = float(request.get("min_score") or 0)
        if request.get("preset_id"):
            row = session.get(ScreenerPreset, int(request["preset_id"]))
            if row is None:
                raise KeyError(f"preset_id {request['preset_id']} 不存在")
            preset_conditions = json.loads(row.conditions_json or "[]")
            if not user_conditions_present:
                conditions = preset_conditions
            order_by_default = row.order_by or "change_pct"
            order_default = row.order or "desc"
            # preset 的 match_mode/min_score 作为默认，request 显式传值则覆盖
            if not request.get("match_mode"):
                match_mode = str(row.match_mode or "all")
            if not request.get("min_score"):
                min_score = float(row.min_score or 0)
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

        # 龙虎榜降级：引用了 lhb 指标但当日无 lhb 数据（17:00 前或当日无人上榜）
        if referenced & _LHB_INDICATORS and (
            "lhb_today" not in df.columns or df["lhb_today"].isna().all()
        ):
            warnings.append(self.WARN_NO_LHB)

        filtered = apply_dsl(df, conditions, match_mode=match_mode, min_score=min_score)
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
        # 支持 as_of_date 历史回放（2026-07-21 持久化层新增）
        as_of_str = universe_cfg.get("as_of_date")
        as_of = None
        if as_of_str:
            try:
                from datetime import date as _date
                as_of = _date.fromisoformat(as_of_str)
            except (TypeError, ValueError):
                as_of = None
        universe = self.daily_bars.get_universe(
            session, min_amount=min_amount, universe_as_of=as_of
        )
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
        # 缓存 key 纳入 as_of_date：历史回放与当日 universe 可能同 hash，
        # 不区分会命中当日缓存返回错日期指标。
        as_of = (request.get("universe") or {}).get("as_of_date")
        cache_key = ("features", universe_hash, as_of)
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
        bars["stock_code"] = bars["stock_code"].astype(str).str.zfill(6)
        bars["trading_date"] = pd.to_datetime(bars["trading_date"])

        latest_date_obj = latest_date.date() if hasattr(latest_date, "date") else latest_date
        flows = _load_fund_flow(session, codes, latest_date)
        frame = compute_features(bars, flows, latest_date_obj)

        # === 持久化层覆盖 (2026-07-21) ===
        # 1) 基础组字段 (pe/pb/total_mv/float_mv/turnover_rate/latest_price/change_pct)
        #    从 stock_realtime_eod 读，缺则保留 live compute 值
        rt_eod_df = _load_realtime_eod(session, codes, latest_date_obj)
        if not rt_eod_df.empty:
            frame = frame.merge(rt_eod_df, on="stock_code", how="left", suffixes=("", "_eod"))

        # 2) bars/fundflow 派生 43 指标：优先 stock_indicators_daily 预计算，缺则保留 live
        precomp_df = _load_precomputed_indicators(session, codes, latest_date_obj)
        if not precomp_df.empty:
            # 先把预计算表按 stock_code 建索引，再 map 到 frame 的整数 index，
            # 最后 where：mapped 非空取预计算值，否则保留 live compute 值。
            # （旧实现 .where(cond, other) 的 cond 用 stock_code 字符串 index，
            # 与调用方 frame 整数 index 对齐后全 NaN -> 永远取 other，预计算覆盖形同虚设。）
            precomp_idx = precomp_df.set_index("stock_code")
            for col in precomp_df.columns:
                if col == "stock_code":
                    continue
                if col not in frame.columns:
                    continue
                mapped = frame["stock_code"].map(precomp_idx[col])
                frame[col] = mapped.where(mapped.notna(), frame[col])

        # 3) 涨停指标 (consecutive_limit_up_days / sealed_amount 等) 从 stock_limit_up_indicators
        lu_df = _load_limit_up_indicators(session, codes, latest_date_obj)
        if not lu_df.empty:
            frame = frame.merge(lu_df, on="stock_code", how="left", suffixes=("", "_lu"))

        # 4) 龙虎榜指标 (lhb_today/lhb_net_buy/lhb_inst_net_buy) 从 stock_lhb_detail 实时聚合
        lhb_df = _load_lhb_indicators(session, codes, latest_date_obj)
        if not lhb_df.empty:
            frame = frame.merge(lhb_df, on="stock_code", how="left", suffixes=("", "_lhb"))

        # 向后兼容：旧版 _realtime_lookup callable 仍生效（测试用）
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
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df


# ---------------- 持久化层加载助手 (2026-07-21) ----------------


def _load_realtime_eod(
    session: Session, codes: list[str], trading_date: Any
) -> pd.DataFrame:
    """从 ``stock_realtime_eod`` 拉取基础组字段（pe/pb/total_mv/float_mv/turnover_rate/latest_price）。"""
    if not codes:
        return pd.DataFrame()
    td = trading_date.date() if hasattr(trading_date, "date") else trading_date
    rows = list(
        session.execute(
            select(
                StockRealtimeEod.stock_code,
                StockRealtimeEod.close,  # close → latest_price（指标用 latest_price 命名）
                StockRealtimeEod.change_pct,
                StockRealtimeEod.turnover_rate,
                StockRealtimeEod.pe_dynamic,
                StockRealtimeEod.pb,
                StockRealtimeEod.total_mv,
                StockRealtimeEod.float_mv,
            )
            .where(StockRealtimeEod.trading_date == td)
            .where(StockRealtimeEod.stock_code.in_(codes))
        )
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "stock_code", "latest_price", "change_pct", "turnover_rate",
        "pe_dynamic", "pb", "total_mv", "float_mv",
    ])
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    return df


def _load_precomputed_indicators(
    session: Session, codes: list[str], trading_date: Any
) -> pd.DataFrame:
    """从 ``stock_indicators_daily`` 拉取预计算的 43 列 bars/fundflow 派生指标。"""
    if not codes:
        return pd.DataFrame()
    td = trading_date.date() if hasattr(trading_date, "date") else trading_date
    rows = list(
        session.execute(
            select(StockIndicatorDaily).where(
                StockIndicatorDaily.trading_date == td,
                StockIndicatorDaily.stock_code.in_(codes),
            )
        )
    )
    if not rows:
        return pd.DataFrame()
    # 转 DataFrame，丢 ORM 元数据列
    records = []
    for r in rows:
        records.append({
            "stock_code": str(r.stock_code).zfill(6),
            "compute_version": r.compute_version,
            "data_hash": r.data_hash,
            # 以下 43 列为预计算指标
            "ma5": r.ma5, "ma10": r.ma10, "ma20": r.ma20, "ma60": r.ma60,
            "close_vs_ma5": r.close_vs_ma5, "close_vs_ma10": r.close_vs_ma10,
            "close_vs_ma20": r.close_vs_ma20, "close_vs_ma60": r.close_vs_ma60,
            "ma_bullish": r.ma_bullish,
            "golden_cross_recent": r.golden_cross_recent,
            "death_cross_recent": r.death_cross_recent,
            "high_20d_break": r.high_20d_break, "high_60d_break": r.high_60d_break,
            "low_20d_break": r.low_20d_break,
            "change_3d": r.change_3d, "change_5d": r.change_5d,
            "change_10d": r.change_10d, "change_20d": r.change_20d,
            "consecutive_up_days": r.consecutive_up_days,
            "consecutive_down_days": r.consecutive_down_days,
            "rsi6": r.rsi6, "rsi14": r.rsi14,
            "macd_dif": r.macd_dif, "macd_dea": r.macd_dea, "macd_hist": r.macd_hist,
            "macd_golden_recent": r.macd_golden_recent,
            "bias20": r.bias20,
            "volume_ratio": r.volume_ratio,
            "amount_ma5": r.amount_ma5, "turnover_ma5": r.turnover_ma5,
            "volume_up_days": r.volume_up_days,
            "limit_up_today": r.limit_up_today,
            "limit_up_count_5d": r.limit_up_count_5d,
            "platform_breakout": r.platform_breakout,
            "gap_up_pct": r.gap_up_pct, "lower_shadow_ratio": r.lower_shadow_ratio,
            "main_net_inflow": r.main_net_inflow,
            "main_net_inflow_5d": r.main_net_inflow_5d,
            "main_net_inflow_10d": r.main_net_inflow_10d,
            "main_net_inflow_days": r.main_net_inflow_days,
            "main_net_ratio": r.main_net_ratio,
            "super_large_net": r.super_large_net,
            "main_net_inflow_5d_pct_mv": r.main_net_inflow_5d_pct_mv,
        })
    return pd.DataFrame(records)


def _load_limit_up_indicators(
    session: Session, codes: list[str], trading_date: Any
) -> pd.DataFrame:
    """从 ``stock_limit_up_indicators`` 拉取涨停指标。"""
    if not codes:
        return pd.DataFrame()
    td = trading_date.date() if hasattr(trading_date, "date") else trading_date
    rows = list(
        session.execute(
            select(
                StockLimitUpIndicator.stock_code,
                StockLimitUpIndicator.limit_up_today,
                StockLimitUpIndicator.consecutive_limit_up_days,
                StockLimitUpIndicator.sealed_amount,
                StockLimitUpIndicator.broken_today,
                StockLimitUpIndicator.strong_pool,
            )
            .where(StockLimitUpIndicator.trading_date == td)
            .where(StockLimitUpIndicator.stock_code.in_(codes))
        )
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "stock_code", "limit_up_today", "consecutive_limit_up_days",
        "sealed_amount", "broken_today", "strong_pool",
    ])
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    return df


def _load_lhb_indicators(
    session: Session, codes: list[str], trading_date: Any
) -> pd.DataFrame:
    """从 ``stock_lhb_detail`` 聚合龙虎榜指标（当日，按 stock_code）。

    一只票一日可能多行（多个上榜原因），net_buy/inst_net_count 取净额求和，
    lhb_today 置 1。表小（~100 行/日），实时查不预计算。
    """
    if not codes:
        return pd.DataFrame()
    td = trading_date.date() if hasattr(trading_date, "date") else trading_date
    rows = list(
        session.execute(
            select(
                StockLhbDetail.stock_code,
                func.sum(StockLhbDetail.net_buy).label("lhb_net_buy"),
                func.sum(StockLhbDetail.inst_net_count).label("lhb_inst_net_buy"),
            )
            .where(StockLhbDetail.trading_date == td)
            .where(StockLhbDetail.stock_code.in_(codes))
            .group_by(StockLhbDetail.stock_code)
        )
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["stock_code", "lhb_net_buy", "lhb_inst_net_buy"])
    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    df["lhb_today"] = 1
    return df[["stock_code", "lhb_today", "lhb_net_buy", "lhb_inst_net_buy"]]


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

# 龙虎榜类指标（实时从 stock_lhb_detail 聚合）
_LHB_INDICATORS = {
    "lhb_today",
    "lhb_net_buy",
    "lhb_inst_net_buy",
}


def apply_dsl(
    frame: pd.DataFrame,
    conditions: list[dict[str, Any]],
    *,
    match_mode: str = "all",
    min_score: float = 0,
) -> pd.DataFrame:
    """DSL 过滤，支持 all/any/score 三种匹配模式（2026-07-22 选股器重构）。

    score 模式：每条满足加 weight（默认 1）计入 score 列，过滤 score>=min_score。
    资金流缺数据时该条件不计分但其它条件仍可凑分，容忍数据缺失。
    """

    if frame.empty or not conditions:
        return frame
    mode = (match_mode or "all").lower()
    weighted_masks: list[tuple[pd.Series, float]] = []
    for condition in conditions:
        indicator = condition.get("indicator")
        op = condition.get("op")
        value = condition.get("value")
        weight = float(condition.get("weight") or 1)
        if indicator not in INDICATOR_REGISTRY:
            continue
        if indicator not in frame.columns:
            weighted_masks.append((pd.Series([False] * len(frame), index=frame.index), weight))
            continue
        col = pd.to_numeric(frame[indicator], errors="coerce")
        weighted_masks.append((_op_mask(col, op, value), weight))
    if not weighted_masks:
        return frame

    if mode == "score":
        score = pd.Series([0.0] * len(frame), index=frame.index)
        for mask, weight in weighted_masks:
            score = score + mask.astype(float) * weight
        frame = frame.assign(score=score)
        return frame[score >= float(min_score)]

    if mode == "any":
        combined = weighted_masks[0][0]
        for mask, _ in weighted_masks[1:]:
            combined = combined | mask
        return frame[combined]

    # 默认 all：AND
    combined = weighted_masks[0][0]
    for mask, _ in weighted_masks[1:]:
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
        "score": _maybe_float(row.get("score")),
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
