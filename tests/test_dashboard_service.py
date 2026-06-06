from datetime import date, datetime

from app.models import FundFlowDailyHistory, FundFlowSnapshot
from app.services.dashboard import DashboardService
from app.services.market_time import is_trading_time


class StubGateway:
    def resolve_sector_name(self, sector_type: str, sector_name: str) -> str | None:
        mapping = {
            ("industry", "公路铁路运输"): "铁路公路",
            ("concept", "电网"): "智能电网",
        }
        return mapping.get((sector_type, sector_name), sector_name)


def seed_snapshots(db_session) -> None:
    day1 = datetime(2026, 5, 6, 10, 0, 0)
    minute_1 = datetime(2026, 5, 7, 9, 58, 0)
    minute_2 = datetime(2026, 5, 7, 9, 59, 0)
    minute_4 = datetime(2026, 5, 7, 10, 1, 0)

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
                captured_at=minute_1,
                inflow=100.0,
                outflow=100.0,
                net_amount=5.0,
                sector_index=1010.0,
                change_percent=-0.3,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=1.0,
                leading_stock_price=10.2,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Alpha",
                captured_at=minute_2,
                inflow=120.0,
                outflow=100.0,
                net_amount=20.0,
                sector_index=1015.0,
                change_percent=0.2,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=3.0,
                leading_stock_price=10.8,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Alpha",
                captured_at=minute_4,
                inflow=140.0,
                outflow=60.0,
                net_amount=80.0,
                sector_index=1020.0,
                change_percent=-0.1,
                company_count=10,
                leading_stock="A1",
                leading_stock_change=5.0,
                leading_stock_price=11.0,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Beta",
                captured_at=minute_1,
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
                sector_name="Beta",
                captured_at=minute_2,
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
                sector_name="Beta",
                captured_at=minute_4,
                inflow=920.0,
                outflow=800.0,
                net_amount=120.0,
                sector_index=1112.0,
                change_percent=1.7,
                company_count=12,
                leading_stock="B1",
                leading_stock_change=2.5,
                leading_stock_price=22.4,
            ),
            FundFlowSnapshot(
                sector_type="industry",
                sector_name="Gamma",
                captured_at=minute_2,
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
                captured_at=minute_4,
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
                sector_name="智能电网",
                captured_at=minute_4,
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
            FundFlowDailyHistory(sector_type="industry", sector_name="Alpha", trading_date=minute_4.date(), main_net_amount=80.0, main_net_ratio=0.40),
            FundFlowDailyHistory(sector_type="industry", sector_name="Beta", trading_date=day1.date(), main_net_amount=50.0, main_net_ratio=0.066),
            FundFlowDailyHistory(sector_type="industry", sector_name="Beta", trading_date=minute_4.date(), main_net_amount=120.0, main_net_ratio=0.0714),
            FundFlowDailyHistory(sector_type="industry", sector_name="Gamma", trading_date=minute_4.date(), main_net_amount=120.0, main_net_ratio=0.60),
            FundFlowDailyHistory(sector_type="concept", sector_name="智能电网", trading_date=minute_4.date(), main_net_amount=30.0, main_net_ratio=0.4286),
        ]
    )
    db_session.commit()


def test_latest_rankings_defaults_to_net_strength(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_latest_rankings(db_session, sector_type="industry", limit=3)

    assert result["updated_at"] == "2026-05-07T10:01:00"
    assert [item["sector_name"] for item in result["leaders"]] == ["Gamma", "Alpha", "Beta"]
    assert round(result["leaders"][0]["net_strength"], 4) == 0.6


def test_comparison_series_returns_gap_filled_zero_based_points(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService(gateway=StubGateway())

    result = service.get_comparison_series(
        db_session,
        sector_type="industry",
        metric="net_strength",
        granularity="minute",
        lookback_days=2,
        limit=2,
        trading_date=date(2026, 5, 7),
    )

    alpha = next(series for series in result["series"] if series["sector_name"] == "Alpha")
    assert alpha["points"][0]["value"] is None
    assert alpha["points"][28]["value"] == 0.0
    assert alpha["points"][30]["is_filled"] is True
    assert result["missing_labels_count"] > 0


def test_comparison_series_filters_invalid_watchlist_names(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService(gateway=StubGateway())

    result = service.get_comparison_series(
        db_session,
        sector_type="concept",
        metric="net_strength",
        granularity="minute",
        lookback_days=2,
        limit=1,
        include_sector_names=["电网", "不存在概念"],
        trading_date=date(2026, 5, 7),
    )

    assert [series["sector_name"] for series in result["series"]] == ["智能电网"]
    assert result["resolved_watchlist"]["电网"] == "智能电网"
    assert result["invalid_watchlist"] == ["不存在概念"]


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


def test_comparison_series_supports_laggards_rank_view(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService(gateway=StubGateway())

    result = service.get_comparison_series(
        db_session,
        sector_type="industry",
        metric="net_strength",
        granularity="minute",
        lookback_days=2,
        limit=2,
        trading_date=date(2026, 5, 7),
        rank_view="laggards",
    )

    assert [series["sector_name"] for series in result["series"]] == ["Beta", "Alpha"]


def test_alerts_detect_strength_jump_and_rank_change(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    alerts = service.get_alerts(db_session, sector_type="industry", metric="net_strength", limit=5)

    assert alerts["updated_at"] == "2026-05-07T10:01:00"
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
        trading_date=date(2026, 5, 7),
    )
    day_history = service.get_sector_history(
        db_session,
        sector_type="industry",
        sector_name="Alpha",
        metric="net_strength",
        granularity="day",
        lookback_days=2,
    )

    assert minute_history["points"][28]["value"] == 0.0
    assert minute_history["points"][31]["value"] == 0.375
    assert [point["label"] for point in day_history["points"]] == ["2026-05-06", "2026-05-07"]


def test_sector_history_can_resolve_specific_alias(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService(gateway=StubGateway())

    minute_history = service.get_sector_history(
        db_session,
        sector_type="concept",
        sector_name="电网",
        metric="net_strength",
        granularity="minute",
        lookback_days=30,
        trading_date=date(2026, 5, 7),
    )

    assert minute_history["sector_name"] == "智能电网"


def test_rankings_support_all_limit_and_available_dates(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    rankings = service.get_latest_rankings(db_session, sector_type="industry", limit=0)
    dates = service.get_available_trading_dates(db_session, sector_type="industry")

    assert len(rankings["leaders"]) == 3
    assert dates == ["2026-05-07", "2026-05-06"]


def test_monitor_signals_exposes_acceleration_persistence_and_divergence(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_monitor_signals(db_session, sector_type="industry", metric="net_strength", limit=3)

    assert result["updated_at"] == "2026-05-07T10:01:00"
    assert result["items"][0]["sector_name"] == "Alpha"
    assert result["items"][0]["acceleration_1"] > 0
    assert result["items"][0]["acceleration_3"] > 0
    assert result["items"][0]["persistence"] == 3
    assert result["items"][0]["divergence"] == "bullish_flow_vs_price"
    assert result["items"][1]["sector_name"] == "Gamma"


def test_sector_workspace_exposes_cache_metadata_and_structure_shell(db_session) -> None:
    seed_snapshots(db_session)
    service = DashboardService()

    result = service.get_sector_workspace(
        db_session,
        sector_type="industry",
        sector_name="Alpha",
        metric="net_strength",
        granularity="minute",
        lookback_days=30,
        trading_date=date(2026, 5, 7),
    )

    assert result["resolved_trading_date"] == "2026-05-07"
    assert result["source_status"] == "cache_hit"
    assert result["cache_meta"]["requested_trading_date"] == "2026-05-07"
    assert result["analysis_cache"]["detail_updated_at"] == "2026-05-07T10:01:00"
    assert result["structure"]["metrics"] == []
    assert result["structure"]["notes"] == []


def test_is_trading_time_handles_market_sessions() -> None:
    assert is_trading_time(datetime(2026, 5, 7, 10, 15, 0)) is True
    assert is_trading_time(datetime(2026, 5, 7, 11, 45, 0)) is False
    assert is_trading_time(datetime(2026, 5, 7, 14, 30, 0)) is True
    assert is_trading_time(datetime(2026, 5, 7, 15, 5, 0)) is False
