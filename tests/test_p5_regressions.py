"""P5 schema 助手与 merge upsert 的回归测试。

覆盖：
- P5-3 _add_missing_columns：缺则 ADD COLUMN，存在则幂等
- P5-3 ensure_ai_center_schema：在只有 users 表的库上不报错
- P5-1f merge upsert：sync_watched_stocks/sync_watched_sectors 保留行 id、按 key 更新/新增/删除
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import _add_missing_columns, ensure_ai_center_schema
from app.models import WatchedSector, WatchedStock
from app.services.realtime_cache import RealtimeCacheService
from app.services.workspace import WorkspaceService


def test_add_missing_columns_creates_only_when_absent(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    Base.metadata.create_all(engine)
    # 新列缺失 -> 添加
    _add_missing_columns(engine, "ai_jobs", {
        "job_type": "ALTER TABLE ai_jobs ADD COLUMN job_type VARCHAR(40) DEFAULT 'stock_pick'",
    })
    cols = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(ai_jobs)")).fetchall()}
    assert "job_type" in cols
    # 再次运行 -> 幂等不抛错
    _add_missing_columns(engine, "ai_jobs", {
        "job_type": "ALTER TABLE ai_jobs ADD COLUMN job_type VARCHAR(40) DEFAULT 'stock_pick'",
    })


def test_add_missing_columns_noop_when_table_missing(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    Base.metadata.create_all(engine)
    # 表不存在 -> 直接跳过（交给 create_all 处理）
    _add_missing_columns(engine, "no_such_table", {
        "x": "ALTER TABLE no_such_table ADD COLUMN x INTEGER",
    })


def test_ensure_ai_center_schema_idempotent_on_minimal_db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    Base.metadata.create_all(engine)
    ensure_ai_center_schema(engine)
    ensure_ai_center_schema(engine)
    cols = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(users)")).fetchall()}
    assert "is_admin" in cols


def test_sync_watched_stocks_merge_preserves_ids_and_removes_extras(db_session):
    class StubCache:
        def sync_watched_sectors(self, *a, **kw):
            pass
    service = WorkspaceService(realtime_cache=StubCache())
    SessionLocal = sessionmaker(bind=db_session.get_bind())
    session = SessionLocal()

    # 初始：插入 2 个
    service.sync_watched_stocks(session, [
        {"stock_code": "000001", "stock_name": "A", "sector_name": None, "watch_reason": None},
        {"stock_code": "000002", "stock_name": "B", "sector_name": None, "watch_reason": None},
    ])
    initial_ids = {row.stock_code: row.id for row in session.query(WatchedStock).all()}
    assert set(initial_ids) == {"000001", "000002"}

    # 合并：000001 更新名称 + 保留 id；000003 新增；000002 删除
    service.sync_watched_stocks(session, [
        {"stock_code": "000001", "stock_name": "A-renamed", "sector_name": "银行", "watch_reason": "测试"},
        {"stock_code": "000003", "stock_name": "C", "sector_name": None, "watch_reason": None},
    ])

    rows = {row.stock_code: row for row in session.query(WatchedStock).all()}
    assert set(rows) == {"000001", "000003"}
    assert rows["000001"].id == initial_ids["000001"], "000001 行 id 应保留"
    assert rows["000001"].stock_name == "A-renamed"
    assert rows["000001"].sector_name == "银行"
    assert rows["000001"].watch_reason == "测试"
    assert rows["000003"].stock_name == "C"


def test_sync_watched_sectors_merge_updates_and_deletes(db_session):
    class StubGateway:
        def resolve_sector_name(self, sector_type, name):
            return name  # 直通，不走实际解析
    cache = RealtimeCacheService(gateway=StubGateway())
    SessionLocal = sessionmaker(bind=db_session.get_bind())
    session = SessionLocal()

    cache.sync_watched_sectors(session, [
        {"sector_type": "industry", "sector_name": "Alpha"},
        {"sector_type": "concept", "sector_name": "Beta"},
    ])
    initial = {(r.sector_type, r.sector_name): r.id for r in session.query(WatchedSector).all()}
    assert len(initial) == 2

    cache.sync_watched_sectors(session, [
        {"sector_type": "industry", "sector_name": "Alpha"},  # 保留
        {"sector_type": "industry", "sector_name": "Gamma"},  # 新增
        # Beta 删除
    ])

    rows = {(r.sector_type, r.sector_name) for r in session.query(WatchedSector).all()}
    assert rows == {("industry", "Alpha"), ("industry", "Gamma")}
    alpha = session.query(WatchedSector).filter_by(sector_type="industry", sector_name="Alpha").one()
    assert alpha.id == initial[("industry", "Alpha")], "Alpha 行 id 应保留"

# ── C1: _migrate_all 通用 schema 迁移 ───────────────────────────────────────
def test_migrate_all_adds_missing_column_for_any_table(tmp_path):
    """C1: 临时 Base 含一张新表 + 一列，DB 里只有空表壳，_migrate_all 应补列。"""
    from datetime import datetime
    from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c1.db'}")
    # 建一个只有 id 列的空表壳（模拟老库缺新列）
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE _test_migrate (id INTEGER PRIMARY KEY)"))

    md = MetaData()
    Table(
        "_test_migrate", md,
        Column("id", Integer, primary_key=True),
        Column("note", String(100), nullable=True),  # 可空新列
        Column("created_at", DateTime, nullable=True),
    )
    from app.main import _migrate_all
    added = _migrate_all(engine, md)
    assert added == 2, f"应补 2 列，实际 {added}"
    cols = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(_test_migrate)")).fetchall()}
    assert "note" in cols and "created_at" in cols


def test_migrate_all_skips_not_null_no_default(tmp_path):
    """C1: NOT NULL 且无 server_default 的列应被跳过（ADD 会失败）。"""
    from sqlalchemy import Column, Integer, MetaData, String, Table

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c1b.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE _test_nn (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO _test_nn (id) VALUES (1)"))  # 非空表

    md = MetaData()
    Table(
        "_test_nn", md,
        Column("id", Integer, primary_key=True),
        Column("required", String(50), nullable=False),  # NOT NULL 无 default
    )
    from app.main import _migrate_all
    added = _migrate_all(engine, md)
    assert added == 0, f"NOT NULL 无 default 应跳过，实际加了 {added}"
    cols = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(_test_nn)")).fetchall()}
    assert "required" not in cols


def test_migrate_all_idempotent(tmp_path):
    """C1: 列已存在时不应重复 ADD。"""
    from sqlalchemy import Column, Integer, MetaData, String, Table

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c1c.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE _test_idem (id INTEGER PRIMARY KEY, note VARCHAR(50))"))

    md = MetaData()
    Table("_test_idem", md, Column("id", Integer, primary_key=True), Column("note", String(50), nullable=True))
    from app.main import _migrate_all
    assert _migrate_all(engine, md) == 0  # note 已存在
    assert _migrate_all(engine, md) == 0  # 再跑仍 0


def test_migrate_all_covers_all_production_tables(tmp_path):
    """C1 验收：对生产 Base.metadata 跑 _migrate_all 不应抛异常（覆盖 14+ 表）。"""
    from app.main import _migrate_all
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'c1d.db'}")
    Base.metadata.create_all(engine)  # 全表建成最新 schema
    # 再跑 _migrate_all：列都存在，应返回 0 且不报错
    added = _migrate_all(engine, Base.metadata)
    assert added == 0
