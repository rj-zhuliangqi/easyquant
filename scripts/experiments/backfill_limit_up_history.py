"""一次性回填 stock_limit_up_history (2026-07-21)。

拉近 N 个交易日的东财涨停/炸板/强势/昨涨停 4 池，写入 stock_limit_up_history。
首次跑可能耗时（4 池 × 30 日 × 网络），建议先 --dry-run 看日期列表。

用法:
    uv run python scripts/experiments/backfill_limit_up_history.py --start 2026-06-15 --end 2026-07-21
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.akshare_client import AkshareGateway  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import create_session_factory  # noqa: E402
from app.services.limit_up_history import LimitUpHistoryService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_limit_up_history")


def _enumerate_trading_days(start: date, end: date) -> list[date]:
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


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

    dates = _enumerate_trading_days(start, end)
    logger.info("将处理 %d 个 trading_date", len(dates))
    if args.dry_run:
        for d in dates:
            print(d.isoformat())
        return 0

    session_factory = create_session_factory()
    Base.metadata.create_all(session_factory().get_bind())
    gateway = AkshareGateway()
    svc = LimitUpHistoryService(gateway=gateway)

    total = {"limit_up": 0, "broken": 0, "strong": 0, "previous": 0}
    failed: list[tuple[date, str]] = []
    for d in dates:
        session = session_factory()
        try:
            r = svc.refresh_for_date(session, d, force=True)
            for k, v in r.items():
                total[k] += v
            logger.info("%s: %s", d, r)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s 失败: %s", d, exc)
            failed.append((d, str(exc)))
        finally:
            session.close()

    logger.info("总计 %s；失败 %d 个日期", total, len(failed))
    if failed:
        for d, msg in failed:
            logger.error("  %s: %s", d, msg)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
