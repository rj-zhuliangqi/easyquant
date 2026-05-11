from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.akshare_client import AkshareGateway
from app.config import DEFAULT_DATABASE_URL
from app.database import Base
from app.models import FundFlowSnapshot
from app.services.collector import FundFlowCollector
from app.services.dashboard import DashboardService
from app.services.history_cache import HistoryCacheService
from app.services.market_time import is_trading_time
from app.services.realtime_cache import RealtimeCacheService


def create_session_factory(database_url: str = DEFAULT_DATABASE_URL) -> sessionmaker[Session]:
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


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
    realtime_cache = RealtimeCacheService(gateway=gateway, now_provider=now_provider)
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
            scheduler.add_job(lambda: _collect_once(session_factory, dashboard, collector, realtime_cache, now_provider), "interval", minutes=1, id="collector")
            scheduler.start()
            _collect_once(session_factory, dashboard, collector, realtime_cache, now_provider)
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Sector Fund Monitor", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

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
        include_sectors: str = Query(default=""),
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        include_sector_names = [item for item in include_sectors.split(",") if item]
        if granularity == "day":
            latest_rankings = dashboard.get_latest_rankings(db, sector_type=sector_type, limit=limit, metric=metric)
            target_names = [item["sector_name"] for item in latest_rankings["leaders"]]
            history_cache.ensure_daily_history(db, sector_type=sector_type, sector_names=list(dict.fromkeys(target_names + include_sector_names)))
        return dashboard.get_comparison_series(
            db,
            sector_type=sector_type,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            limit=limit,
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

    return app


def _collect_once(
    session_factory: sessionmaker[Session],
    dashboard: DashboardService,
    collector: FundFlowCollector,
    realtime_cache: RealtimeCacheService,
    now_provider: Callable[[], datetime],
) -> None:
    now = now_provider()
    if not is_trading_time(now):
        return
    with session_factory() as session:
        collector.collect_snapshot(session, captured_at=now.replace(second=0, microsecond=0))
        realtime_cache.refresh_individual_rankings(session, trading_date=now.date())
        realtime_cache.refresh_watched_sector_stocks(session, trading_date=now.date())
        _prefetch_priority_sector_stocks(session, dashboard, realtime_cache, trading_date=now.date())


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
