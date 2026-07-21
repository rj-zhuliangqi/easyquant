"""归档 individual_stock_snapshots 老数据到 CSV (2026-07-21)。

为什么需要：分钟级 snapshots ~160K 行/日，1 年 ~58M 行 ~12GB。主库膨胀会拖慢
所有在线查询。但用户要保留做分钟级 NN 训练，所以不能直接删。

策略：导出老 tick 到按月分 CSV 文件 -> 可选删除主库已归档行（主库保留近 N 日）。
NN 训练时从 ``data/archive/snapshots/snapshots_YYYYMM.csv`` 批量读取。

用法:
    # 1. 先 dry-run 看会归档多少
    uv run python scripts/experiments/archive_snapshots.py --keep-days 90 --dry-run

    # 2. 只导出 CSV，不删主库（安全，先验证 CSV 完整）
    uv run python scripts/experiments/archive_snapshots.py --keep-days 90

    # 3. 导出 + 删主库（确认 CSV OK 后）
    uv run python scripts/experiments/archive_snapshots.py --keep-days 90 --delete
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("archive_snapshots")

DB_PATH = "data/sector_fund_monitor.db"
ARCHIVE_DIR = "data/archive/snapshots"


def _find_cutoff(db_path: str, keep_days: int) -> date | None:
    """cutoff = MAX(trading_date) - keep_days。早于 cutoff 的行将被归档。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT MAX(trading_date) FROM individual_stock_snapshots"
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    latest = date.fromisoformat(row[0])
    return latest - timedelta(days=keep_days)


def _list_archive_months(db_path: str, cutoff: date) -> list[tuple[str, int]]:
    """返回 [(YYYY-MM, 行数), ...] 早于 cutoff 的行按月分组。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT strftime('%Y-%m', trading_date) AS ym, COUNT(*) "
            "FROM individual_stock_snapshots "
            "WHERE trading_date < ? "
            "GROUP BY ym ORDER BY ym",
            (cutoff.isoformat(),),
        ).fetchall()
    finally:
        conn.close()
    return [(r[0], r[1]) for r in rows]


def _export_month(db_path: str, year_month: str, out_path: Path) -> int:
    """导出某月数据到 CSV。返回行数。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql(
            "SELECT trading_date, captured_at, stock_code, stock_name, "
            "latest_price, change_percent, net_amount "
            "FROM individual_stock_snapshots "
            f"WHERE strftime('%Y-%m', trading_date) = '{year_month}'",
            conn,
        )
    finally:
        conn.close()
    if df.empty:
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return len(df)


def _delete_archived(db_path: str, cutoff: date) -> int:
    """删除主库中早于 cutoff 的行（走 app 服务层）。"""
    from app.main import create_session_factory
    from app.services.realtime_cache import RealtimeCacheService
    from app.akshare_client import AkshareGateway

    session_factory = create_session_factory()
    session = session_factory()
    try:
        svc = RealtimeCacheService(gateway=AkshareGateway())
        # 直接按 cutoff 删（prune_old_snapshots 是按 MAX-keep_days，这里要精确 cutoff）
        from app.models import IndividualStockSnapshot
        from sqlalchemy import delete
        result = session.execute(
            delete(IndividualStockSnapshot).where(
                IndividualStockSnapshot.trading_date < cutoff
            )
        )
        session.commit()
        return result.rowcount or 0
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-days", type=int, default=90, help="主库保留天数（默认 90）")
    parser.add_argument("--archive-dir", default=ARCHIVE_DIR, help="归档目录")
    parser.add_argument("--delete", action="store_true", help="归档后删除主库老数据")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不导出不删")
    args = parser.parse_args()

    cutoff = _find_cutoff(DB_PATH, args.keep_days)
    if cutoff is None:
        logger.warning("individual_stock_snapshots 为空，无需归档")
        return 0
    logger.info("keep_days=%d -> cutoff=%s (早于此日的行将被归档)", args.keep_days, cutoff)

    months = _list_archive_months(DB_PATH, cutoff)
    if not months:
        logger.info("无早于 %s 的数据需要归档", cutoff)
        return 0

    total = sum(n for _, n in months)
    logger.info("待归档 %d 个月份，共 %d 行:", len(months), total)
    for ym, n in months:
        logger.info("  %s: %d 行", ym, n)

    if args.dry_run:
        logger.info("dry-run 模式，不导出不删")
        return 0

    archive_dir = Path(args.archive_dir)
    exported = 0
    for ym, _ in months:
        out_path = archive_dir / f"snapshots_{ym}.csv"
        n = _export_month(DB_PATH, ym, out_path)
        exported += n
        logger.info("导出 %s -> %s (%d 行)", ym, out_path, n)

    logger.info("导出完成，共 %d 行", exported)

    if args.delete:
        deleted = _delete_archived(DB_PATH, cutoff)
        logger.info("已从主库删除 %d 行（< %s）", deleted, cutoff)
        logger.info("归档文件在 %s，NN 训练时从那里读", archive_dir)
    else:
        logger.info("未加 --delete，主库未删。确认 CSV 完整后可重跑加 --delete 清理主库")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
