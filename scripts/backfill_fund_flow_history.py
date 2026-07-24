"""一次性回补近 N 日全市场资金流 -> stock_fund_flow_daily（详情页"近10日资金流"填满）。

TuShare moneyflow 按日期全市场拉取，每日期望 ~5400 行，10 日 ~10 秒。
避免 import app.main（顶层 create_app 会触发 prod DB 完整性检查/恢复），直接建 engine。

用法:
    EQ_TUSHARE_TOKEN=xxx uv run python scripts/backfill_fund_flow_history.py --days 10
    # token 已在 launchd plist；手动跑可从 plist 取：
    # export EQ_TUSHARE_TOKEN=$(plutil -extract EnvironmentVariables.EQ_TUSHARE_TOKEN raw ~/Library/LaunchAgents/com.easyquant.server.plist)
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import DEFAULT_DATABASE_URL  # noqa: E402
from app.database import Base  # noqa: E402  # 触发 models 注册
import app.models  # noqa: E402,F401
from app.services.daily_bars import DailyBarsService  # noqa: E402
from app.tushare_client import TushareGateway  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_fund_flow_history")


def _list_recent_dates(db_path: str, days: int) -> list[date]:
    """从 stock_daily_bars 取最近 days 个有日线的交易日（降序）。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT DISTINCT trading_date FROM stock_daily_bars ORDER BY trading_date DESC LIMIT ?",
            (days,),
        ).fetchall()
    finally:
        conn.close()
    return [date.fromisoformat(r[0]) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=10, help="回补最近 N 个交易日（默认 10）")
    args = parser.parse_args()

    db_path = DEFAULT_DATABASE_URL.split("///")[-1]
    dates = _list_recent_dates(db_path, args.days)
    if not dates:
        logger.error("stock_daily_bars 无数据，无可回补日期")
        return 1
    logger.info("将回补 %d 个交易日的资金流: %s", len(dates), dates)

    engine = create_engine(
        DEFAULT_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    gw = TushareGateway()
    daily_bars = DailyBarsService(gateway=None, tushare_gateway=gw)

    total = 0
    for d in dates:
        with SessionLocal() as session:
            try:
                n = daily_bars.backfill_fund_flow_by_date(session, d)
                total += n
            except Exception:  # noqa: BLE001
                logger.exception("回补 %s 失败", d)
    logger.info("完成，共写入 %d 行 -> stock_fund_flow_daily", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
