from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
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
    collector = FundFlowCollector(gateway=gateway)
    dashboard = DashboardService()
    history_cache = HistoryCacheService(gateway=gateway)
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    now_provider = now_provider or datetime.now

    def get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if enable_scheduler:
            scheduler.add_job(lambda: _collect_once(session_factory, collector, now_provider), "interval", minutes=1, id="collector")
            scheduler.start()
            _collect_once(session_factory, collector, now_provider)
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
        limit: int = Query(default=10, ge=1, le=30),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        db: Session = Depends(get_db),
    ) -> dict:
        return dashboard.get_latest_rankings(db, sector_type=sector_type, limit=limit, metric=metric)

    @app.get("/api/comparison")
    def comparison(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        granularity: str = Query(default="minute", pattern="^(minute|day)$"),
        lookback_days: int = Query(default=1, ge=1, le=10),
        limit: int = Query(default=8, ge=1, le=20),
        include_sectors: str = Query(default=""),
        db: Session = Depends(get_db),
    ) -> dict:
        include_sector_names = [item for item in include_sectors.split(",") if item]
        if granularity == "day":
            latest_rankings = dashboard.get_latest_rankings(db, sector_type=sector_type, limit=limit, metric=metric)
            target_names = [item["sector_name"] for item in latest_rankings["leaders"][:limit]]
            history_cache.ensure_daily_history(db, sector_type=sector_type, sector_names=list(dict.fromkeys(target_names + include_sector_names)))
        return dashboard.get_comparison_series(
            db,
            sector_type=sector_type,
            metric=metric,
            granularity=granularity,
            lookback_days=lookback_days,
            limit=limit,
            include_sector_names=include_sector_names,
        )

    @app.get("/api/series")
    def series(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        granularity: str = Query(default="minute", pattern="^(minute|day)$"),
        lookback_days: int = Query(default=1, ge=1, le=10),
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
        )

    @app.get("/api/sector-detail")
    def sector_detail(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        sector_name: str = Query(min_length=1),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        db: Session = Depends(get_db),
    ) -> dict:
        detail = dashboard.get_sector_snapshot(db, sector_type=sector_type, sector_name=sector_name, metric=metric)
        if detail is None:
            raise HTTPException(status_code=404, detail="sector not found")
        return detail

    @app.get("/api/alerts")
    def alerts(
        sector_type: str = Query(pattern="^(industry|concept)$"),
        metric: str = Query(default="net_strength", pattern="^(net_strength|net_amount)$"),
        limit: int = Query(default=10, ge=1, le=30),
        db: Session = Depends(get_db),
    ) -> dict:
        return dashboard.get_alerts(db, sector_type=sector_type, metric=metric, limit=limit)

    @app.get("/api/sector-stocks")
    def sector_stocks(sector_name: str = Query(min_length=1)) -> dict:
        data = gateway.fetch_sector_stocks(sector_name)
        return {"sector_name": sector_name, "stocks": data.fillna("").to_dict(orient="records")}

    @app.get("/api/individual-rankings")
    def individual_rankings(limit: int = Query(default=20, ge=1, le=100)) -> dict:
        data = gateway.fetch_individual_realtime().fillna("")
        return {"updated_at": None, "stocks": data.head(limit).to_dict(orient="records")}

    @app.post("/api/refresh")
    def refresh(db: Session = Depends(get_db)) -> dict:
        return collector.collect_snapshot(db)

    @app.get("/api/status")
    def status(db: Session = Depends(get_db)) -> dict:
        latest = db.query(FundFlowSnapshot).order_by(FundFlowSnapshot.captured_at.desc()).first()
        now = now_provider()
        return {
            "scheduler_enabled": enable_scheduler,
            "market_open": is_trading_time(now),
            "last_snapshot_at": latest.captured_at.isoformat() if latest else None,
            "server_time": now.isoformat(),
        }

    return app


def _collect_once(
    session_factory: sessionmaker[Session],
    collector: FundFlowCollector,
    now_provider: Callable[[], datetime],
) -> None:
    now = now_provider()
    if not is_trading_time(now):
        return
    with session_factory() as session:
        collector.collect_snapshot(session, captured_at=now.replace(second=0, microsecond=0))


app = create_app()
