from datetime import datetime, timedelta

from app.models import FundFlowDailyHistory, FundFlowSnapshot
from app.services.dashboard import DashboardService
from app.services.market_time import is_trading_time


def seed_snapshots(db_session) -> None:
    day1 = datetime(2026, 5, 6, 10, 0, 0)
    day2 = datetime(2026, 5, 7, 10, 0, 0)
    db_session.add_all(
        [
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Alpha",
                captured_at=day1,
                inflow=100.0,
                outflow=100.0,
                net_amount=20.0,
                sector_index=1000.0,
                change_percent=1.0,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=2.0,
                leading_stock_price=10.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Beta",
                captured_at=day1,
                inflow=400.0,
                outflow=350.0,
                net_amount=50.0,
                sector_index=1100.0,
                change_percent=0.8,
                company_count=12,
                leading_stock="B1",
                leading_stock_change=1.0,
                leading_stock_price=20.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Alpha",
                captured_at=day2,
                inflow=140.0,
                outflow=60.0,
                net_amount=80.0,
                sector_index=1020.0,
                change_percent=2.0,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=5.0,
                leading_stock_price=11.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Beta",
                captured_at=day2,
                inflow=900.0,
                outflow=780.0,
                net_amount=120.0,
                sector_index=1110.0,
                change_percent=1.5,
                company_count=12,
                leading_stock="B1",
                leading_stock_change=2.2,
                leading_stock_price=22.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Alpha",
                captured_at=day2 - timedelta(minutes=1),
                inflow=120.0,
                outflow=100.0,
                net_amount=20.0,
                sector_index=1015.0,
                change_percent=1.5,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=3.0,
                leading_stock_price=10.8,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Beta",
                captured_at=day2 - timedelta(minutes=1),
                inflow=700.0,
                outflow=600.0,
                net_amount=100.0,
                sector_index=1105.0,
                change_percent=1.3,
                company_count=12,
                leading_stock="B1",
                leading_stock_change=1.8,
                leading_stock_price=21.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Gamma",
                captured_at=day2 - timedelta(minutes=1),
                inflow=100.0,
                outflow=100.0,
                net_amount=0.0,
                sector_index=900.0,
                change_percent=0.1,
                company_count=8,
                leading_stock="G1",
                leading_stock_change=0.5,
                leading_stock_price=9.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Gamma",
                captured_at=day2,
                inflow=160.0,
                outflow=40.0,
                net_amount=120.0,
                sector_index=920.0,
                change_percent=3.0,
                company_count=8,
                leading_stock="G1",
                leading_stock_change=4.0,
                leading_stock_price=10.0,
            ),
            FundFlowSnapshot(
                sector_type="concept",
                sector_name="Concept-X",
                captured_at=day2,
                inflow=50.0,
                outflow=20.0,
                net_amount=30.0,
                sector_index=300.0,
                change_percent=1.1,
                company_count=5,
                leading_stock="C1",
                leading_stock_change=2.1,
                leading_stock_price=8.0,
            ),
        ]
    )
    db_session.add_all(
        [
            FundFlowDailyHistory(sector_type="industry", sector_name="Alpha", trading_date=day1.date(), main_net_amount=20.0, main_net_ratio=0.11),
            FundFlowDailyHistory(sector_type="industry", sector_name="Alpha", trading_date=day2.date(), main_net_amount=80.0, main_net_ratio=0.40),
            FundFlowDailyHistory(sector_type="industry", sector_name="Beta", trading_date=day1.date(), main_net_amount=50.0, main_net_ratio=0.066),
            FundFlowDailyHistory(sector_type="industry", sector_name="Beta", trading_date=day2.date(), main_net_amount=120.0, main_net_ratio=0.0714),
            FundFlowDailyHistory(sector_type="industry", sector_name="Gamma", trading_date=day2.date(), main_net_amount=120.0, main_net_ratio=0.60),
            FundFlowDailyHistory(sector_type="concept", sector_name="Concept-X", trading_date=day2.date(), main_net_amount=30.0, main_net_ratio=0.4286),
        ]
    )
    db_session.commit()


def test_latest_rankings_defaults_to_net_strength(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_latest_rankings(db_session, sector_type="industry", limit=3)

    assert result["updated_at"] == "2026-05-07T10:00:00"
    assert [item["sector_name"] for item in result["leaders"]] == ["Gamma", "Alpha", "Beta"]
    assert round(result["leaders"][0]["net_strength"], 4) == 0.6


def test_comparison_series_returns_multiple_sectors_for_minute_view(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_comparison_series(
        db_session,
        sector_type="industry",
        metric="net_strength",
        granularity="minute",
        lookback_days=2,
        limit=2,
    )

    assert result["metric"] == "net_strength"
    assert result["granularity"] == "minute"
    assert [series["sector_name"] for series in result["series"]] == ["Gamma", "Alpha"]
    assert result["series"][0]["points"][-1]["value"] == 0.6


def test_comparison_series_returns_daily_points(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_comparison_series(
        db_session,
        sector_type="industry",
        metric="net_strength",
        granularity="day",
        lookback_days=2,
        limit=1,
    )

    assert result["series"][0]["sector_name"] == "Gamma"
    assert [point["label"] for point in result["series"][0]["points"]] == ["2026-05-07"]


def test_alerts_detect_strength_jump_and_rank_change(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    alerts = service.get_alerts(db_session, sector_type="industry", metric="net_strength", limit=5)

    assert alerts["updated_at"] == "2026-05-07T10:00:00"
    assert alerts["items"][0]["sector_name"] == "Gamma"
    assert alerts["items"][0]["delta_value"] == 0.6
    assert alerts["items"][0]["rank_change"] == 2


def test_sector_history_supports_multi_day_and_day_granularity(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    minute_history = service.get_sector_history(
        db_session,
        sector_type="industry",
        sector_name="Alpha",
        metric="net_strength",
        granularity="minute",
        lookback_days=2,
    )
    day_history = service.get_sector_history(
        db_session,
        sector_type="industry",
        sector_name="Alpha",
        metric="net_strength",
        granularity="day",
        lookback_days=2,
    )

    assert len(minute_history["points"]) == 3
    assert minute_history["points"][-1]["value"] == 0.4
    assert [point["label"] for point in day_history["points"]] == ["2026-05-06", "2026-05-07"]


def test_is_trading_time_handles_market_sessions() -> None:
    assert is_trading_time(datetime(2026, 5, 7, 10, 15, 0)) is True
    assert is_trading_time(datetime(2026, 5, 7, 11, 45, 0)) is False
    assert is_trading_time(datetime(2026, 5, 7, 14, 30, 0)) is True
    assert is_trading_time(datetime(2026, 5, 7, 15, 5, 0)) is False
