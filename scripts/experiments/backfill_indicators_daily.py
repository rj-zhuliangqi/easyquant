"""一次性回填 stock_indicators_daily (2026-07-21)。

用法:
    uv run python scripts/experiments/backfill_indicators_daily.py --start 2026-06-15 --end 2026-07-21
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
from app.services.indicators_daily import IndicatorsDailyService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_indicators_daily")


def _list_dates_with_bars(db_path: str, start: date, end: date) -> list[date]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT DISTINCT trading_date FROM stock_daily_bars "
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
    dates = [d for d in _list_dates_with_bars(db_path, start, end) if d.weekday() < 5]
    logger.info("发现 %d 个 trading_date", len(dates))

    if args.dry_run:
        for d in dates:
            print(d.isoformat())
        return 0
    if not dates:
        logger.warning("区间 [%s, %s] 内无 bars", start, end)
        return 0

    session_factory = create_session_factory()
    Base.metadata.create_all(session_factory().get_bind())
    svc = IndicatorsDailyService()

    total_rows = 0
    failed: list[tuple[date, str]] = []
    for d in dates:
        session = session_factory()
        try:
            r = svc.compute_for_date(session, d)
            total_rows += r["rows"]
            logger.info("%s: +%d 行（%d 只）", d, r["rows"], r["stocks"])
        except Exception as exc:  # noqa: BLE001
            logger.error("%s 失败: %s", d, exc)
            failed.append((d, str(exc)))
        finally:
            session.close()

    logger.info("总写入 %d 行；失败 %d 个日期", total_rows, len(failed))
    if failed:
        for d, msg in failed:
            logger.error("  %s: %s", d, msg)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
