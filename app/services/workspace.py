from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import WatchedStock, WorkspaceNote
from app.services._common import merge_upsert_by_key


class WorkspaceService:
    def __init__(self, *, realtime_cache: Any, now_provider: Any | None = None) -> None:
        self.realtime_cache = realtime_cache
        self.now_provider = now_provider or datetime.now

    def get_workspace(self, session: Session, limit_notes: int = 20) -> dict[str, Any]:
        notes = list(
            session.scalars(
                select(WorkspaceNote)
                .where(WorkspaceNote.status == "active")
                .order_by(desc(WorkspaceNote.created_at))
                .limit(max(limit_notes, 1))
            )
        )
        return {
            "updated_at": self.now_provider().isoformat(),
            "watched_sectors": self.realtime_cache.list_watched_sectors(session),
            "watched_stocks": self.list_watched_stocks(session),
            "notes": [self._note_to_dict(item) for item in notes],
        }

    def save_workspace(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        watched_sectors = payload.get("watched_sectors") or []
        watched_stocks = payload.get("watched_stocks") or []
        self.realtime_cache.sync_watched_sectors(session, watched_sectors)
        self.sync_watched_stocks(session, watched_stocks)
        return self.get_workspace(session)

    def list_watched_stocks(self, session: Session) -> list[dict[str, Any]]:
        rows = list(
            session.scalars(
                select(WatchedStock)
                .where(WatchedStock.enabled.is_(True))
                .order_by(WatchedStock.stock_code.asc())
            )
        )
        return [self._stock_to_dict(row) for row in rows]

    def sync_watched_stocks(self, session: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            stock_code = str(item.get("stock_code") or "").strip()
            stock_name = str(item.get("stock_name") or "").strip()
            if not stock_code or stock_code in seen:
                continue
            seen.add(stock_code)
            normalized.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name or stock_code,
                    "sector_name": str(item.get("sector_name") or "").strip() or None,
                    "watch_reason": str(item.get("watch_reason") or "").strip() or None,
                    "enabled": True,
                }
            )

        # P5-1f/C2: merge upsert 抽到 _common.merge_upsert_by_key（按 stock_code
        # 更新/新增/删除），保留行 id、减少并发丢数据窗口
        merge_upsert_by_key(
            session,
            WatchedStock,
            normalized,
            key_fields=("stock_code",),
            update_fields=("stock_name", "sector_name", "watch_reason", "enabled"),
        )
        session.commit()
        return normalized

    def add_watch_item(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        watched_stocks = self.list_watched_stocks(session)
        watched_stocks.append(payload)
        self.sync_watched_stocks(session, watched_stocks)
        return self.get_workspace(session)

    def add_note(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        trading_date_value = payload.get("trading_date")
        note = WorkspaceNote(
            trading_date=date.fromisoformat(trading_date_value) if trading_date_value else None,
            subject_type=str(payload.get("subject_type") or "market"),
            subject_key=str(payload.get("subject_key") or "market"),
            content=str(payload.get("content") or "").strip(),
            status=str(payload.get("status") or "active"),
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return self._note_to_dict(note)

    def delete_note(
        self,
        session: Session,
        subject_type: str,
        subject_key: str,
        note_id: int | None = None,
    ) -> int:
        """删除 WorkspaceNote。

        - 默认按 (subject_type, subject_key) 软删（status='archived'），避免历史回放丢数据
        - 若传 note_id 则精删该 id
        - 返回被影响的行数
        """
        from sqlalchemy import update

        stmt = select(WorkspaceNote).where(
            WorkspaceNote.subject_type == subject_type,
            WorkspaceNote.subject_key == subject_key,
        )
        rows = list(session.scalars(stmt))
        if note_id is not None:
            rows = [r for r in rows if r.id == note_id]
        if not rows:
            return 0
        for row in rows:
            if note_id is not None:
                session.delete(row)
            else:
                row.status = "archived"
        session.commit()
        return len(rows)

    @staticmethod
    def _stock_to_dict(row: WatchedStock) -> dict[str, Any]:
        return {
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "sector_name": row.sector_name,
            "watch_reason": row.watch_reason,
            "enabled": row.enabled,
        }

    @staticmethod
    def _note_to_dict(row: WorkspaceNote) -> dict[str, Any]:
        return {
            "id": row.id,
            "trading_date": row.trading_date.isoformat() if row.trading_date else None,
            "subject_type": row.subject_type,
            "subject_key": row.subject_key,
            "content": row.content,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
