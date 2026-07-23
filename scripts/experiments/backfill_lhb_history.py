"""一次性回填 stock_lhb_detail。

拉近 N 个交易日的东财龙虎榜明细，写入 stock_lhb_detail。龙虎榜走 datacenter-web
（非 push2），Clash 封 push2 不影响。每日 ~100 行，单日 1 次调用，速度较快。

安全：自建 engine（不 import app.main，避免触发模块级 `app = create_app()` 跑 prod
schema/recovery —— 见 [[incident-2026-07-19-prod-db-truncated]]）；schema 已由服务启动
迁移好，此处不重复 create_all。写库走 LhbHistoryService（200 行 chunk commit）。

用法:
    uv run python scripts/experiments/backfill_lhb_history.py --start 2026-06-15 --end 2026-07-22
    uv run python scripts/experiments/backfill_lhb_history.py --start 2026-07-22 --end 2026-07-22 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.akshare_client import AkshareGateway  # noqa: E402
from app.services.lhb_history import LhbHistoryService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_lhb_history")

DEFAULT_DB = "sqlite:///data/sector_fund_monitor.db"


def _make_session_factory() -> sessionmaker[Session]:
    """自建写 engine：WAL + busy_timeout=30s，不跑 schema 迁移/recovery。"""
    engine = create_engine(
        DEFAULT_DB,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


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

    session_factory = _make_session_factory()
    gateway = AkshareGateway()
    svc = LhbHistoryService(gateway=gateway)

    total_rows = 0
    dates_with_data = 0
    failed: list[tuple[date, str]] = []
    for d in dates:
        session = session_factory()
        try:
            n = svc.refresh_for_date(session, d, force=True)
            total_rows += n
            if n > 0:
                dates_with_data += 1
            logger.info("%s: +%d 行", d, n)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s 失败: %s", d, exc)
            failed.append((d, str(exc)))
        finally:
            session.close()

    logger.info("总计 +%d 行，%d 个日期有数据；失败 %d 个日期", total_rows, dates_with_data, len(failed))
    if failed:
        for d, msg in failed:
            logger.error("  %s: %s", d, msg)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
