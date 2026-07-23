"""盘中预警（P2-4）：IR 条件的盘中执行器。

cron 盘中轮询（9:30-15:00 每 5 分钟）对所有启用的 AlertRule 执行 IR，命中记 AlertEvent。
预警中心从"独立功能"变为"选股条件的盘中执行器"。

注意：依赖 stock_daily_bars 最新数据（盘中由实时快照增量更新，或近似用昨日 EOD）。
真正秒级实时需 push2 轮询（Clash 修复后），当前 5 分钟 cron 近似。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertEvent, AlertRule

logger = logging.getLogger(__name__)


class AlertService:
    """预警规则管理 + 盘中触发检查。"""

    def __init__(self, screener: Any, now_provider: Callable[[], datetime] | None = None) -> None:
        self.screener = screener
        self.now_provider = now_provider or datetime.now

    def define_rule(self, session: Session, name: str, ir: dict, enabled: bool = True) -> dict:
        """新建/覆盖预警规则（按 name）。ir 可由 tdx_parser.parse_tdx 生成。"""
        existing = session.scalar(select(AlertRule).where(AlertRule.name == name))
        ir_text = json.dumps(ir, ensure_ascii=False)
        if existing:
            existing.ir_json = ir_text
            existing.enabled = enabled
            row = existing
        else:
            row = AlertRule(name=name, ir_json=ir_text, enabled=enabled)
            session.add(row)
        session.commit()
        return {"id": row.id, "name": row.name, "enabled": row.enabled}

    def list_rules(self, session: Session) -> list[dict]:
        rows = list(session.execute(select(AlertRule).order_by(AlertRule.id.desc())).scalars())
        return [
            {
                "id": r.id,
                "name": r.name,
                "ir": json.loads(r.ir_json) if r.ir_json else None,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def delete_rule(self, session: Session, rule_id: int) -> bool:
        r = session.get(AlertRule, rule_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True

    def check_rules(self, session: Session) -> dict[str, int]:
        """对所有启用规则执行 IR，命中记 AlertEvent（同规则+代码+日去重）。

        返回 ``{"rules_checked", "events_added", "codes_matched"}``。
        """
        rules = list(session.execute(
            select(AlertRule).where(AlertRule.enabled == True)  # noqa: E712
        ).scalars())
        today = self.now_provider().date()
        added = 0
        matched_codes: set[str] = set()
        for rule in rules:
            try:
                ir = json.loads(rule.ir_json)
            except Exception:  # noqa: BLE001
                logger.warning("alert rule %s ir_json 解析失败，跳过", rule.id)
                continue
            try:
                result = self.screener.run(session, {"ir": ir, "limit": 0})
            except Exception:  # noqa: BLE001
                logger.exception("alert rule %s 执行失败", rule.id)
                continue
            for r in result.get("results", []):
                code = str(r.get("code") or "").zfill(6)
                if not code:
                    continue
                # 同 rule+code+today 去重
                exists = session.scalar(
                    select(AlertEvent).where(
                        AlertEvent.rule_id == rule.id,
                        AlertEvent.stock_code == code,
                    ).where(AlertEvent.triggered_at >= datetime.combine(today, datetime.min.time()))
                )
                if exists:
                    continue
                event = AlertEvent(
                    rule_id=rule.id,
                    stock_code=code,
                    triggered_at=self.now_provider(),
                    data_json=json.dumps({k: v for k, v in r.items() if k in ("close", "change_pct", "score")}, ensure_ascii=False),
                )
                session.add(event)
                added += 1
                matched_codes.add(code)
        if added:
            session.commit()
        logger.info("alert check: rules=%d events_added=%d codes=%d", len(rules), added, len(matched_codes))
        return {"rules_checked": len(rules), "events_added": added, "codes_matched": len(matched_codes)}

    def list_events(self, session: Session, rule_id: int | None = None, days: int = 7) -> list[dict]:
        cutoff = self.now_provider() - _timedelta_days(days)
        q = select(AlertEvent).where(AlertEvent.triggered_at >= cutoff)
        if rule_id is not None:
            q = q.where(AlertEvent.rule_id == rule_id)
        q = q.order_by(AlertEvent.triggered_at.desc()).limit(500)
        rows = list(session.execute(q).scalars())
        return [
            {
                "id": e.id,
                "rule_id": e.rule_id,
                "stock_code": e.stock_code,
                "triggered_at": e.triggered_at.isoformat() if e.triggered_at else None,
                "data": json.loads(e.data_json) if e.data_json else None,
            }
            for e in rows
        ]


def _timedelta_days(days: int):
    from datetime import timedelta
    return timedelta(days=days)
