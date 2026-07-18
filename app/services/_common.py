"""服务层共享 helper。

C2: ``merge_upsert_by_key`` 抽自 ``realtime_cache.sync_watched_sectors`` 与
``workspace.sync_watched_stocks`` 的重复 merge upsert 逻辑。
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session


def merge_upsert_by_key(
    session: Session,
    model: type,
    items: list[dict[str, Any]],
    key_fields: Sequence[str],
    update_fields: Sequence[str] | None = None,
) -> list:
    """按 ``key_fields`` 做 merge upsert（保留行 id，避免全表 delete+insert）。

    - incoming 有、DB 无 -> ``session.add(model(**item))``
    - incoming 有、DB 有 -> 更新 ``update_fields``（默认 item 中所有非 key 字段）
    - DB 有、incoming 无 -> ``session.delete(row)``

    调用方负责 ``session.commit()`` 与 items 的归一化/去重。
    返回 incoming items 对应的行列表（已存在行复用原对象，新增行为刚 add 的对象）。
    """
    incoming_keys = {tuple(item[k] for k in key_fields) for item in items}
    existing = {
        tuple(getattr(row, k) for k in key_fields): row
        for row in session.scalars(select(model))
    }

    if update_fields is None:
        seen_fields: list[str] = []
        field_set: set[str] = set()
        for it in items:
            for f in it.keys():
                if f not in field_set:
                    field_set.add(f)
                    seen_fields.append(f)
        update_fields = [f for f in seen_fields if f not in key_fields]

    result: list = []
    for item in items:
        key = tuple(item[k] for k in key_fields)
        row = existing.get(key)
        if row is not None:
            for f in update_fields:
                if f in item:
                    setattr(row, f, item[f])
            result.append(row)
        else:
            row = model(**item)
            session.add(row)
            result.append(row)
    for key, row in existing.items():
        if key not in incoming_keys:
            session.delete(row)
    return result
