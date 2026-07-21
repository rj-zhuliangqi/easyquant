"""一次性回填 stock_limit_up_indicators (2026-07-21)。

依赖 stock_limit_up_history 已经先回填好（聚合源）。
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import Base  # noqa: E402
from app.main import create_session_factory  # noqa: E402
from app.services.limit_up_indicators import LimitUpIndicatorsService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_limit_up_indicators")


def _list_dates_with_history(db_path: str, start: date, end: date) -> list[date]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT DISTINCT trading_date FROM stock_limit_up_history "
            "WHERE trading_date BETWEEN ? AND ? ORDER BY trading_date",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    finally:
        conn.close()
    return [date.fromisoformat(r[0]) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError as exc:
        logger.error("日期格式错误: %s", exc)
        return 2
    if start > end:
        start, end = end, start

    db_path = "data/sector_fund_monitor.db"
    dates = _list_dates_with_history(db_path, start, end)
    logger.info("发现 %d 个 trading_date 有 limit_up_history", len(dates))
    if args.dry_run:
        for d in dates:
            print(d.isoformat())
        return 0
    if not dates:
        logger.warning("区间 [%s, %s] 内无 stock_limit_up_history；先跑 backfill_limit_up_history", start, end)
        return 0

    session_factory = create_session_factory()
    Base.metadata.create_all(session_factory().get_bind())
    svc = LimitUpIndicatorsService()

    total = 0
    failed: list[tuple[date, str]] = []
    for d in dates:
        session = session_factory()
        try:
            n = svc.rebuild_for_date(session, d)
            total += n
            logger.info("%s: +%d 行", d, n)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s 失败: %s", d, exc)
            failed.append((d, str(exc)))
        finally:
            session.close()

    logger.info("总写入 %d 行；失败 %d 个日期", total, len(failed))
    if failed:
        for d, msg in failed:
            logger.error("  %s: %s", d, msg)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
