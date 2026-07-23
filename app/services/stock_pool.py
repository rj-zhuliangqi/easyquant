"""选股流水线（P2-3）：选股结果存板块，板块作下游筛选/预警输入。

对标通达信"策略股票池"（tpool）：选股结果 -> 存板块 -> 板块作下次筛选/预警的 universe。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StockPool

logger = logging.getLogger(__name__)


class StockPoolService:
    """板块 CRUD。"""

    def list_pools(self, session: Session) -> list[dict[str, Any]]:
        rows = list(session.execute(select(StockPool).order_by(StockPool.updated_at.desc())).scalars())
        return [
            {
                "id": r.id,
                "name": r.name,
                "codes": json.loads(r.codes_json or "[]"),
                "count": len(json.loads(r.codes_json or "[]")),
                "source_preset_id": r.source_preset_id,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    def get_pool(self, session: Session, pool_id: int) -> dict[str, Any] | None:
        r = session.get(StockPool, pool_id)
        if r is None:
            return None
        return {
            "id": r.id,
            "name": r.name,
            "codes": json.loads(r.codes_json or "[]"),
            "source_preset_id": r.source_preset_id,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    def save_pool(
        self,
        session: Session,
        name: str,
        codes: list[str],
        source_preset_id: int | None = None,
    ) -> dict[str, Any]:
        """新建或按 name 覆盖板块。"""
        codes = [str(c).zfill(6) for c in codes if c]
        existing = session.scalar(select(StockPool).where(StockPool.name == name))
        if existing:
            existing.codes_json = json.dumps(codes, ensure_ascii=False)
            existing.source_preset_id = source_preset_id
            row = existing
        else:
            row = StockPool(
                name=name,
                codes_json=json.dumps(codes, ensure_ascii=False),
                source_preset_id=source_preset_id,
            )
            session.add(row)
        session.commit()
        logger.info("stock_pool saved: %s, %d codes", name, len(codes))
        return {"id": row.id, "name": row.name, "count": len(codes)}

    def delete_pool(self, session: Session, pool_id: int) -> bool:
        r = session.get(StockPool, pool_id)
        if r is None:
            return False
        session.delete(r)
        session.commit()
        return True
