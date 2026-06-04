from __future__ import annotations

import argparse
from datetime import date
import json

from app.akshare_client import AkshareGateway
from app.main import create_session_factory
from app.services.stock_research import StockResearchService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run stock research and import the result into AI Center.")
    parser.add_argument("--trading-date", default=None, help="Trading date in YYYY-MM-DD format. Defaults to today.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of candidates to keep.")
    parser.add_argument("--mode", default="flow-momentum", help="Research mode label.")
    parser.add_argument("--skill-name", default="AI选股研究", help="AI skill name to use in AI Center.")
    parser.add_argument("--revision-title", default="AI选股研究 v1", help="AI skill revision title.")
    parser.add_argument("--job-name", default="15:00 AI选股研究", help="AI job name.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    trading_date = date.fromisoformat(args.trading_date) if args.trading_date else date.today()

    session_factory = create_session_factory()
    service = StockResearchService(gateway=AkshareGateway())
    with session_factory() as session:
        result = service.run(
            session,
            trading_date=trading_date,
            limit=args.limit,
            mode=args.mode,
            skill_name=args.skill_name,
            revision_title=args.revision_title,
            job_name=args.job_name,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
