from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
import logging
from pathlib import Path
import time
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, event
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.akshare_client import AkshareGateway
from app.config import AI_CENTER_INBOX_DIR
from app.config import AI_CENTER_PROCESSED_DIR
from app.config import DEFAULT_DATABASE_URL
from app.database import Base
from app.models import FundFlowSnapshot
from app.services.collector import FundFlowCollector
from app.services.ai_center import AiCenterService
from app.services.dashboard import DashboardService
from app.services.history_cache import HistoryCacheService
from app.services.home_dashboard import HomeDashboardService
from app.services.limit_up import LimitUpService
from app.services.market_signal import MarketSignalService
from app.services.market_temperature import MarketTemperatureService
from app.services.market_time import is_trading_time
from app.services.page_payloads import PagePayloadService
from app.services.realtime_cache import RealtimeCacheService
from app.services.workspace import WorkspaceService


logger = logging.getLogger(__name__)
STATIC_ASSET_VERSION = "20260602-navrestore"
SPA_SHELL_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"
SPA_SHELL_FILENAME = "spa/frontend/index.html"
SPA_NAVIGATION_PATHS = (
    "/",
    "/alerts",
    "/opportunity-pool",
    "/sector-monitor",
    "/limit-up-ladder",
    "/ai-center",
    "/workspace",
)


def create_session_factory(database_url: str = DEFAULT_DATABASE_URL) -> sessionmaker[Session]:
    sqlite_connect_args = {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        connect_args=sqlite_connect_args,
        future=True,
    )
    if database_url.startswith("sqlite"):
        _configure_sqlite_engine(engine)
    Base.metadata.create_all(engine)
    ensure_ai_center_schema(engine)
    ensure_indexes(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _configure_sqlite_engine(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def ensure_indexes(engine: Engine) -> None:
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            try:
                index.create(bind=engine, checkfirst=True)
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise


def ensure_ai_center_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "ai_jobs" not in inspector.get_table_names() or "ai_runs" not in inspector.get_table_names():
        return

    required_columns = {
        "ai_jobs": {
            "job_type": "ALTER TABLE ai_jobs ADD COLUMN job_type VARCHAR(40) DEFAULT 'stock_pick'",
            "result_schema_version": "ALTER TABLE ai_jobs ADD COLUMN result_schema_version VARCHAR(20) DEFAULT '1.0'",
            "active_rulepack_id": "ALTER TABLE ai_jobs ADD COLUMN active_rulepack_id INTEGER",
            "display_group": "ALTER TABLE ai_jobs ADD COLUMN display_group VARCHAR(20) DEFAULT '盘中'",
        },
        "ai_runs": {
            "result_type": "ALTER TABLE ai_runs ADD COLUMN result_type VARCHAR(40)",
            "result_payload_json": "ALTER TABLE ai_runs ADD COLUMN result_payload_json TEXT",
            "push_payload_json": "ALTER TABLE ai_runs ADD COLUMN push_payload_json TEXT",
            "error_stage": "ALTER TABLE ai_runs ADD COLUMN error_stage VARCHAR(40)",
            "duration_ms": "ALTER TABLE ai_runs ADD COLUMN duration_ms INTEGER",
        },
    }

    with engine.begin() as conn:
        for table_name, statements in required_columns.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()}
            for column_name, ddl in statements.items():
                if column_name not in existing:
                    conn.execute(text(ddl))


def build_static_page_response(filename: str) -> FileResponse:
    response = FileResponse(Path(__file__).parent / "static" / filename)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def build_spa_shell_response() -> FileResponse:
    response = FileResponse(Path(__file__).parent / "static" / SPA_SHELL_FILENAME)
    response.headers["Cache-Control"] = SPA_SHELL_CACHE_CONTROL
    return response


def _ensure_home_summary_ready(
    session: Session,
    dashboard: DashboardService,
    collector: FundFlowCollector,
    now_provider: Callable[[], datetime],
) -> None:
    now = now_provider()
    if not is_trading_time(now):
        return
    snapshot = dashboard.get_latest_rankings(
        session,
        sector_type="industry",
        limit=1,
        metric="net_amount",
        trading_date=now.date(),
    )
    if snapshot.get("updated_at"):
        return
    collector.collect_snapshot(session, captured_at=now.replace(second=0, microsecond=0))


def _warm_page_payload_cache(
    page_payloads: PagePayloadService,
    session_factory: sessionmaker[Session],
    pages: tuple[str, ...] = ("home", "alerts", "sector-monitor", "limit-up-ladder", "opportunity-pool", "ai-center", "workspace"),
) -> None:
    with session_factory() as session:
        for page_name in pages:
            try:
                page_payloads.get_page_payload(page_name, session)
            except Exception:
                logger.exception("page payload warmup failed for %s", page_name)


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    gateway: AkshareGateway | None = None,
    enable_scheduler: bool = True,
    now_provider: Callable[[], datetime] | None = None,
) -> FastAPI:
    session_factory = session_factory or create_session_factory()
    gateway = gateway or AkshareGateway()
    now_provider = now_provider or datetime.now
    collector = FundFlowCollector(gateway=gateway)
    dashboard = DashboardService(gateway=gateway)
    history_cache = HistoryCacheService(gateway=gateway)
    limit_up = LimitUpService(gateway=gateway, now_provider=now_provider)
    realtime_cache = RealtimeCacheService(gateway=gateway, now_provider=now_provider)
    home_dashboard = HomeDashboardService(
        gateway=gateway,
        dashboard=dashboard,
        limit_up=limit_up,
        realtime_cache=realtime_cache,
        now_provider=now_provider,
    )
    market_temperature = MarketTemperatureService(
        limit_up=limit_up,
        home_dashboard=home_dashboard,
        gateway=gateway,
        now_provider=now_provider,
    )
    workspace = WorkspaceService(
        realtime_cache=realtime_cache,
        now_provider=now_provider,
    )
    market_signal = MarketSignalService(
        dashboard=dashboard,
        limit_up=limit_up,
        market_temperature=market_temperature,
        realtime_cache=realtime_cache,
        workspace=workspace,
        now_provider=now_provider,
    )
    ai_center = AiCenterService(gateway=gateway, now_provider=now_provider)
    with session_factory() as bootstrap_session:
        try:
            ai_center.ensure_builtin_registry(bootstrap_session)
        except OperationalError:
            bootstrap_session.rollback()
            logger.warning("ai center builtin registry bootstrap skipped because local database schema is behind")
    home_dashboard.market_temperature = market_temperature
    home_dashboard.market_signal = market_signal
    page_payloads = PagePayloadService(
        dashboard=dashboard,
        home_dashboard=home_dashboard,
        history_cache=history_cache,
        market_signal=market_signal,
        limit_up=limit_up,
        realtime_cache=realtime_cache,
        workspace=workspace,
        ai_center=ai_center,
        now_provider=now_provider,
        gateway=gateway,
    )
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if enable_scheduler:
            with session_factory() as session:
                try:
                    _ensure_home_summary_ready(session, dashboard, collector, now_provider)
                except Exception:
                    logger.exception("home summary warmup failed during startup")
            scheduler.add_job(
                lambda: _run_scheduled_job("collector-core", session_factory, lambda session: _collect_once(session_factory, dashboard, collector, realtime_cache, now_provider, session=session)),
                "interval",
                minutes=1,
                id="collector-core",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("individual-rankings-cache", session_factory, lambda session: _refresh_individual_rankings_once(session, realtime_cache, now_provider)),
                "interval",
                minutes=2,
                id="individual-rankings-cache",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("watched-sector-stocks-cache", session_factory, lambda session: _refresh_watched_sector_stocks_once(session, realtime_cache, now_provider)),
                "interval",
                minutes=3,
                id="watched-sector-stocks-cache",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=90,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("hot-sector-prefetch", session_factory, lambda session: _prefetch_priority_sector_stocks(session, dashboard, realtime_cache, trading_date=now_provider().date(), cold_batch_size=2)),
                "interval",
                minutes=5,
                id="hot-sector-prefetch",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "ai-run-import-scan",
                    session_factory,
                    lambda session: ai_center.scan_import_directory(session, inbox_dir=AI_CENTER_INBOX_DIR, processed_dir=AI_CENTER_PROCESSED_DIR),
                ),
                "interval",
                minutes=2,
                id="ai-run-import-scan",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("ai-outcome-refresh", session_factory, lambda session: ai_center.compute_pending_outcomes(session)),
                "interval",
                minutes=10,
                id="ai-outcome-refresh",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("collector-core-startup", session_factory, lambda session: _collect_once(session_factory, dashboard, collector, realtime_cache, now_provider, session=session)),
                "date",
                run_date=now_provider(),
                id="collector-core-startup",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
            )
            scheduler.add_job(
                lambda: _run_scheduled_job("individual-rankings-cache-startup", session_factory, lambda session: _refresh_individual_rankings_once(session, realtime_cache, now_provider)),
                "date",
                run_date=now_provider(),
                id="individual-rankings-cache-startup",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            scheduler.add_job(
                lambda: _warm_page_payload_cache(page_payloads, session_factory),
                "date",
                run_date=now_provider(),
                id="page-payload-warmup-startup",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            scheduler.add_job(
                lambda: _warm_page_payload_cache(page_payloads, session_factory),
                "interval",
                minutes=3,
                id="page-payload-warmup",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Sector Fund Monitor", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/sector-monitor")
    def sector_monitor_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/limit-up-ladder")
    def limit_up_ladder_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/alerts")
    def alerts_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/opportunity-pool")
    def opportunity_pool_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/review-center")
    def review_center_page() -> RedirectResponse:
        response = RedirectResponse(url="/ai-center?tab=reviews")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.get("/workspace")
    def workspace_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/ai-center")
    def ai_center_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/legacy/home")
    def legacy_home_page() -> FileResponse:
        return build_static_page_response("home.html")

    @app.get("/legacy/alerts")
    def legacy_alerts_page() -> FileResponse:
        return build_static_page_response("alerts.html")

    @app.get("/legacy/opportunity-pool")
    def legacy_opportunity_pool_page() -> FileResponse:
        return build_static_page_response("opportunity-pool.html")

    @app.get("/legacy/sector-monitor")
    def legacy_sector_monitor_page() -> FileResponse:
        return build_static_page_response("index.html")

    @app.get("/legacy/limit-up-ladder")
    def legacy_limit_up_ladder_page() -> FileResponse:
        return build_static_page_response("limit-up.html")

    @app.get("/legacy/ai-center")
    def legacy_ai_center_page() -> FileResponse:
        return build_static_page_response("ai-center.html")

    @app.get("/legacy/workspace")
    def legacy_workspace_page() -> FileResponse:
        return build_static_page_response("workspace.html")

    @app.get("/api/page/{page_name}")
    def page_bootstrap(page_name: str, db: Session = Depends(get_db)) -> dict:
        try:
            return page_payloads.get_page_payload(page_name, db)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown page: {page_name}") from exc

    @app.get("/api/overview")
    def overview(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        limit: int = Query(default=10, ge=0, le=500),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return dashboard.get_latest_rankings(
            db,
            sector_type=sector_type,
            limit=limit,
            metric=metric,
            trading_date=trading_date,
        )

    @app.get("/api/trading-dates")
    def trading_dates(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        db: Session = Depends(get_db),
    ) -> dict:
        return {"sector_type": sector_type, "dates": dashboard.get_available_trading_dates(db, sector_type=sector_type)}

    @app.get("/api/sectors")
    def sectors(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return {
            "sector_type": sector_type,
            "trading_date": trading_date.isoformat() if trading_date else None,
            "sectors": dashboard.get_sector_names(db, sector_type=sector_type, trading_date=trading_date),
        }

    @app.get("/api/sector-catalog")
    def sector_catalog(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        db: Session = Depends(get_db),
    ) -> dict:
        sectors = gateway.fetch_sector_catalog(sector_type)
        if not sectors:
            sectors = dashboard.get_sector_names(db, sector_type=sector_type)
        return {"sector_type": sector_type, "sectors": sectors}

    @app.get("/api/watchlist")
    def watchlist(
        sector_type: str | None = Query(default=None, pattern="^(industry|concept)$"),
        db: Session = Depends(get_db),
    ) -> dict:
        return {"items": realtime_cache.list_watched_sectors(db, sector_type=sector_type)}

    @app.put("/api/watchlist")
    def save_watchlist(
        items: list[dict] = Body(default=[]),
        db: Session = Depends(get_db),
    ) -> dict:
        saved = realtime_cache.sync_watched_sectors(db, items)
        return {"items": saved}

    @app.get("/api/comparison")
    def comparison(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        granularity: str = Query(default="minute", pattern="^(minute|day)$"),
        lookback_days: int = Query(default=1, ge=1, le=30),
        limit: int = Query(default=8, ge=0, le=500),
        rank_view: str = Query(default="leaders", pattern="^(leaders|laggards)$"),
        include_sectors: str = Query(default=""),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        include_sector_names = [item for item in include_sectors.split(",") if item]
        if granularity == "day":
            latest_rankings = dashboard.get_latest_rankings(db, sector_type=sector_type, limit=limit, metric=metric)
            target_names = [item["sector_name"] for item in latest_rankings["laggards" if rank_view == "laggards" else "leaders"]]
            history_cache.ensure_daily_history(db, sector_type=sector_type, sector_names=list(dict.fromkeys(target_names + include_sector_names)))
        return dashboard.get_comparison_series(
            db,
            sector_type=sector_type,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            limit=limit,
            rank_view=rank_view,
            include_sector_names=include_sector_names,
            trading_date=trading_date,
        )

    @app.get("/api/series")
    def series(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        granularity: str = Query(default="minute", pattern="^(minute|day)$"),
        lookback_days: int = Query(default=1, ge=1, le=30),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        if granularity == "day":
            history_cache.ensure_daily_history(db, sector_type=sector_type, sector_names=[sector_name])
        return dashboard.get_sector_history(
            db,
            sector_type=sector_type,
            sector_name=sector_name,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            trading_date=trading_date,
        )

    @app.get("/api/sector-detail")
    def sector_detail(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        detail = dashboard.get_sector_snapshot(
            db,
            sector_type=sector_type,
            sector_name=sector_name,
            metric=metric,
            trading_date=trading_date,
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="sector not found")
        return detail

    @app.get("/api/sector-workspace")
    def sector_workspace(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        granularity: str = Query(default="minute", pattern="^(minute|day)$"),
        lookback_days: int = Query(default=1, ge=1, le=30),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        payload = dashboard.get_sector_workspace(
            session=db,
            sector_type=sector_type,
            sector_name=sector_name,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            trading_date=trading_date,
        )
        if payload["detail"] is None:
            raise HTTPException(status_code=404, detail="sector not found")
        return payload

    @app.get("/api/alerts")
    def alerts(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        limit: int = Query(default=10, ge=0, le=500),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return dashboard.get_alerts(db, sector_type=sector_type, metric=metric, limit=limit, trading_date=trading_date)

    @app.get("/api/sector-stocks")
    def sector_stocks(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        force_refresh: bool = Query(default=False),
        background_refresh: bool = Query(default=False),
        sort_by: str = Query(default="net_amount", pattern="^(net_amount|change_percent)$"),
        sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
        page: int = Query(default=1, ge=1, le=500),
        page_size: int = Query(default=10, ge=1, le=200),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return realtime_cache.get_sector_stocks(
            db,
            sector_type=sector_type,
            sector_name=sector_name,
            trading_date=trading_date,
            force_refresh=force_refresh,
            background_refresh=background_refresh,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @app.get("/api/individual-rankings")
    def individual_rankings(
        limit: int = Query(default=0, ge=0, le=10000),
        force_refresh: bool = Query(default=False),
        sort_by: str = Query(default="net_amount", pattern="^(net_amount|change_percent)$"),
        sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
        page: int = Query(default=1, ge=1, le=500),
        page_size: int = Query(default=15, ge=1, le=200),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return realtime_cache.get_individual_rankings(
            db,
            limit=limit,
            trading_date=trading_date,
            force_refresh=force_refresh,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

    @app.get("/api/stock-search")
    def stock_search(
        keyword: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=50),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return realtime_cache.search_individual_stocks(
            db,
            keyword=keyword,
            limit=limit,
            trading_date=trading_date,
        )

    @app.get("/api/monitor-signals")
    def monitor_signals(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        limit: int = Query(default=10, ge=0, le=500),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return dashboard.get_monitor_signals(
            db,
            sector_type=sector_type,
            metric=metric,
            limit=limit,
            trading_date=trading_date,
        )

    @app.post("/api/refresh")
    def refresh(db: Session = Depends(get_db)) -> dict:
        collected = collector.collect_snapshot(db)
        realtime_cache.refresh_individual_rankings(db)
        collected.update(realtime_cache.refresh_watched_sector_stocks(db))
        collected.update(_prefetch_priority_sector_stocks(db, dashboard, realtime_cache, trading_date=now_provider().date()))
        return collected

    @app.get("/api/status")
    def status(db: Session = Depends(get_db)) -> dict:
        latest = db.query(FundFlowSnapshot).order_by(FundFlowSnapshot.captured_at.desc()).first()
        now = now_provider()
        return {
            "scheduler_enabled": enable_scheduler,
            "market_open": is_trading_time(now),
            "last_snapshot_at": latest.captured_at.isoformat() if latest else None,
            "server_time": now.isoformat(),
            "watched_sector_count": len(realtime_cache.list_watched_sectors(db)),
        }

    @app.get("/api/home/market-overview")
    def home_market_overview(db: Session = Depends(get_db)) -> dict:
        return home_dashboard.get_market_overview(db)

    @app.get("/api/home/system-summary")
    def home_system_summary(db: Session = Depends(get_db)) -> dict:
        _ensure_home_summary_ready(db, dashboard, collector, now_provider)
        return home_dashboard.get_system_summary(db)

    @app.get("/api/home/status")
    def home_status(db: Session = Depends(get_db)) -> dict:
        return home_dashboard.get_status(db)

    @app.get("/api/alerts/feed")
    def alerts_feed(
        signal_type: str = Query(default="all"),
        strength: str = Query(default="all"),
        time_window: str = Query(default="today"),
        limit: int = Query(default=20, ge=1, le=100),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return market_signal.get_alerts_feed(
            db,
            signal_type=signal_type,
            strength=strength,
            time_window=time_window,
            limit=limit,
            trading_date=trading_date,
        )

    @app.get("/api/alerts/summary")
    def alerts_summary(
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return market_signal.get_alerts_summary(db, trading_date=trading_date)

    @app.get("/api/opportunities")
    def opportunities(
        mode: str = Query(default="strong-sector"),
        limit: int = Query(default=20, ge=1, le=100),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return market_signal.get_opportunities(db, mode=mode, limit=limit, trading_date=trading_date)

    @app.post("/api/opportunities/watch")
    def opportunity_watch(
        payload: dict = Body(default={}),
        db: Session = Depends(get_db),
    ) -> dict:
        if payload.get("watch_type") == "sector":
            items = workspace.get_workspace(db).get("watched_sectors", [])
            items.append({"sector_type": payload.get("sector_type") or "industry", "sector_name": payload.get("sector_name")})
            realtime_cache.sync_watched_sectors(db, items)
            return workspace.get_workspace(db)
        watch_payload = {
            "stock_code": payload.get("stock_code"),
            "stock_name": payload.get("stock_name"),
            "sector_name": payload.get("sector_name"),
            "watch_reason": payload.get("watch_reason"),
        }
        return workspace.add_watch_item(db, watch_payload)

    @app.get("/api/review/day")
    def review_day(
        trading_date: date = Query(...),
        db: Session = Depends(get_db),
    ) -> dict:
        return market_signal.get_review_day(db, trading_date=trading_date)

    @app.get("/api/review/timeline")
    def review_timeline(
        trading_date: date = Query(...),
        db: Session = Depends(get_db),
    ) -> dict:
        return market_signal.get_review_timeline(db, trading_date=trading_date)

    @app.get("/api/workspace")
    def workspace_state(db: Session = Depends(get_db)) -> dict:
        return workspace.get_workspace(db)

    @app.put("/api/workspace")
    def save_workspace_state(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        return workspace.save_workspace(db, payload)

    @app.post("/api/notes")
    def create_workspace_note(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        return workspace.add_note(db, payload)

    @app.get("/api/limit-up/dates")
    def limit_up_dates() -> dict:
        return limit_up.get_available_dates()

    @app.get("/api/limit-up/summary")
    def limit_up_summary(
        trading_date: date | None = Query(default=None),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
    ) -> dict:
        return limit_up.get_summary(trading_date or now_provider().date(), market_scope=market_scope)

    @app.get("/api/limit-up/temperature")
    def limit_up_temperature(
        trading_date: date | None = Query(default=None),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
    ) -> dict:
        return market_temperature.get_temperature(trading_date or now_provider().date(), market_scope=market_scope)

    @app.get("/api/limit-up/temperature-history")
    def limit_up_temperature_history(
        lookback_days: int = Query(default=20, ge=1, le=60),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
    ) -> dict:
        return market_temperature.get_temperature_history(lookback_days=lookback_days, market_scope=market_scope)

    @app.get("/api/limit-up/ladder")
    def limit_up_ladder(
        trading_date: date | None = Query(default=None),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
        sort_by: str = Query(default="board_count", pattern="^(board_count|turnover|turnover_rate|net_inflow|first_limit_up_time)$"),
    ) -> dict:
        return limit_up.get_ladder(trading_date or now_provider().date(), market_scope=market_scope, sort_by=sort_by)

    @app.get("/api/limit-up/broken")
    def limit_up_broken(
        trading_date: date | None = Query(default=None),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
        sort_by: str = Query(default="turnover", pattern="^(turnover|turnover_rate|net_inflow|first_limit_up_time)$"),
    ) -> dict:
        return limit_up.get_broken_pool(trading_date or now_provider().date(), market_scope=market_scope, sort_by=sort_by)

    @app.get("/api/limit-up/stock-detail")
    def limit_up_stock_detail(
        stock_code: str = Query(min_length=1),
        trading_date: date | None = Query(default=None),
    ) -> dict:
        try:
            return limit_up.get_stock_detail(trading_date or now_provider().date(), stock_code=stock_code)
        except KeyError:
            raise HTTPException(status_code=404, detail="stock not found in limit-up pools")

    @app.get("/api/limit-up/search")
    def limit_up_search(
        keyword: str = Query(min_length=1),
        trading_date: date | None = Query(default=None),
        market_scope: str = Query(default="all", pattern="^(all|mainboard|gem|star)$"),
    ) -> dict:
        return limit_up.search(trading_date or now_provider().date(), keyword=keyword, market_scope=market_scope)

    @app.get("/api/ai/jobs")
    def ai_jobs(db: Session = Depends(get_db)) -> dict:
        return ai_center.list_jobs(db)

    @app.get("/api/ai/overview/daily")
    def ai_daily_overview(
        trading_date: date | None = Query(default=None),
        run_type: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return ai_center.get_daily_overview(
            db,
            trading_date=trading_date or now_provider().date(),
            run_type=run_type,
        )

    @app.get("/api/ai/runs")
    def ai_runs(
        run_type: str | None = Query(default=None),
        job_type: str | None = Query(default=None),
        display_group: str | None = Query(default=None),
        status: str | None = Query(default=None),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return ai_center.list_runs(
            db,
            run_type=run_type,
            trading_date=trading_date,
            job_type=job_type,
            display_group=display_group,
            status=status,
        )

    @app.get("/api/ai/runs/{run_id}")
    def ai_run_detail(run_id: int, db: Session = Depends(get_db)) -> dict:
        payload = ai_center.get_run(db, run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="run not found")
        return payload

    @app.post("/api/ai/import-run")
    def ai_import_run(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.import_run(db, payload)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/ai/demo/seed")
    def ai_seed_demo(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            trading_date_raw = payload.get("trading_date")
            trading_date = date.fromisoformat(str(trading_date_raw)) if trading_date_raw else now_provider().date()
            return ai_center.seed_demo_data(db, trading_date=trading_date)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/ai/demo/clear")
    def ai_clear_demo(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            trading_date_raw = payload.get("trading_date")
            trading_date = date.fromisoformat(str(trading_date_raw)) if trading_date_raw else now_provider().date()
            return ai_center.clear_demo_data(db, trading_date=trading_date)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/ai/picks")
    def ai_picks(
        trading_date: date | None = Query(default=None),
        run_type: str | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return ai_center.list_picks(db, trading_date=trading_date, run_type=run_type)

    @app.get("/api/ai/picks/{pick_id}/review")
    def ai_pick_review(pick_id: int, db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.get_pick_review(db, pick_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/ai/picks/{pick_id}/review")
    def ai_add_pick_review(pick_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.add_review(db, pick_id, payload)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/ai/skills")
    def ai_skills(db: Session = Depends(get_db)) -> dict:
        return ai_center.list_skills(db)

    @app.post("/api/ai/skills/{skill_id}/revisions")
    def ai_create_revision(skill_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.create_revision(db, skill_id, payload)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/ai/jobs/{job_id}/activate-revision")
    def ai_activate_revision(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.activate_revision(db, job_id, int(payload.get("revision_id")))
        except (TypeError, ValueError) as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/ai/rulepacks")
    def ai_rulepacks(
        job_id: int | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        try:
            return ai_center.list_rulepacks(db, job_id=job_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/ai/rulepacks/promote")
    def ai_promote_rulepack(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.promote_rulepack(db, payload)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/ai/jobs/{job_id}/activate-rulepack")
    def ai_activate_rulepack(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.activate_rulepack(db, job_id, int(payload.get("rulepack_id")))
        except (TypeError, ValueError) as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/ai/backtests")
    def ai_create_backtest(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.create_backtest_batch(db, payload)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/ai/backtests")
    def ai_backtests(db: Session = Depends(get_db)) -> dict:
        return ai_center.list_backtests(db)

    @app.get("/api/ai/insights/summary")
    def ai_insights_summary(
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        return ai_center.get_insights_summary(db, trading_date=trading_date)

    @app.get("/api/ai/trading-days/{trading_date}")
    def ai_trading_day_review(trading_date: date, db: Session = Depends(get_db)) -> dict:
        return ai_center.get_trading_day_review(db, trading_date)

    @app.get("/api/ai/jobs/{job_id}/history")
    def ai_job_history(job_id: int, db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.get_job_history(db, job_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/ai/skills/{skill_id}/performance")
    def ai_skill_performance(skill_id: int, db: Session = Depends(get_db)) -> dict:
        try:
            return ai_center.get_skill_performance(db, skill_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    return app


def _collect_once(
    session_factory: sessionmaker[Session],
    dashboard: DashboardService,
    collector: FundFlowCollector,
    realtime_cache: RealtimeCacheService,
    now_provider: Callable[[], datetime],
    session: Session | None = None,
) -> None:
    now = now_provider()
    if not is_trading_time(now):
        return
    captured_at = now.replace(second=0, microsecond=0)
    if session is not None:
        collector.collect_snapshot(session, captured_at=captured_at)
        return
    with session_factory() as session:
        collector.collect_snapshot(session, captured_at=captured_at)


def _refresh_individual_rankings_once(
    session: Session,
    realtime_cache: RealtimeCacheService,
    now_provider: Callable[[], datetime],
) -> datetime | None:
    now = now_provider()
    if not is_trading_time(now):
        return None
    return realtime_cache.refresh_individual_rankings(session, trading_date=now.date())


def _refresh_watched_sector_stocks_once(
    session: Session,
    realtime_cache: RealtimeCacheService,
    now_provider: Callable[[], datetime],
) -> dict[str, int] | None:
    now = now_provider()
    if not is_trading_time(now):
        return None
    return realtime_cache.refresh_watched_sector_stocks(session, trading_date=now.date())


def _run_scheduled_job(
    name: str,
    session_factory: sessionmaker[Session],
    task: Callable[[Session], object],
) -> object | None:
    started = time.perf_counter()
    logger.info("scheduled job %s started", name)
    with session_factory() as session:
        try:
            result = task(session)
            logger.info("scheduled job %s finished in %.2fs: %s", name, time.perf_counter() - started, result)
            return result
        except Exception:
            if hasattr(session, "rollback"):
                session.rollback()
            logger.exception("scheduled job %s failed after %.2fs", name, time.perf_counter() - started)
            return None


def _prefetch_priority_sector_stocks(
    session: Session,
    dashboard: DashboardService,
    realtime_cache: RealtimeCacheService,
    trading_date: date,
    top_n: int = 10,
    cold_batch_size: int = 4,
) -> dict[str, int]:
    total_prefetched = 0
    cold_prefetched = 0

    watched_names = {
        (item["sector_type"], item["sector_name"])
        for item in realtime_cache.list_watched_sectors(session)
    }

    for sector_type in ("industry", "concept"):
        overview = dashboard.get_latest_rankings(
            session,
            sector_type=sector_type,
            limit=top_n,
            metric="net_amount",
            trading_date=trading_date,
        )
        hot_names = [
            *[item["sector_name"] for item in overview.get("leaders", [])],
            *[item["sector_name"] for item in overview.get("laggards", [])],
            *[name for item_type, name in watched_names if item_type == sector_type],
        ]
        total_prefetched += realtime_cache.prefetch_sector_batch(
            session,
            [{"sector_type": sector_type, "sector_name": name} for name in hot_names],
            trading_date=trading_date,
        )

        all_names = dashboard.get_sector_names(session, sector_type=sector_type, trading_date=trading_date)
        hot_name_set = set(hot_names)
        cold_names = [name for name in all_names if name not in hot_name_set]
        selected = realtime_cache.rotate_sector_batch(
            session,
            sector_type=sector_type,
            sector_names=cold_names,
            trading_date=trading_date,
            batch_size=cold_batch_size,
        )
        cold_prefetched += len(selected)

    return {"prefetched": total_prefetched, "cold_rotated": cold_prefetched}


app = create_app()
