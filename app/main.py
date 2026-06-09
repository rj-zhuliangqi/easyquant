from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
import subprocess
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
from app.dependencies import AuthMiddleware
from app.models import FundFlowSnapshot
from app.models_auth import User
from app.routers import auth as auth_router
from app.services.auth import AuthService
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
SPA_SHELL_CACHE_CONTROL = "no-cache, max-age=0"
SPA_SHELL_FILENAME = "spa/frontend/index.html"
SPA_NAVIGATION_PATHS = (
    "/",
    "/login",
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
        _recover_sqlite_if_corrupted(engine)
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


def _recover_sqlite_if_corrupted(engine: Engine) -> None:
    """Check SQLite integrity and dump/rebuild if corrupted."""
    db_url = str(engine.url)
    if not db_url.startswith("sqlite"):
        return
    db_path = db_url.replace("sqlite+pysqlite:///", "").replace("sqlite:///", "")
    if not db_path or not Path(db_path).exists():
        return

    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check")).scalar()
        if result == "ok":
            return
        logger.warning("SQLite integrity check failed: %s — attempting recovery", str(result)[:200])
    except Exception as exc:
        logger.warning("SQLite integrity check raised: %s — attempting recovery", exc)

    backup_path = db_path + ".corrupted." + time.strftime("%Y%m%d%H%M%S")
    logger.warning("Renaming corrupted DB to %s", backup_path)

    # Close existing connections and remove WAL/SHM files
    engine.dispose()
    for suffix in ("-shm", "-wal"):
        wal_path = Path(db_path + suffix)
        if wal_path.exists():
            wal_path.unlink()

    Path(db_path).rename(backup_path)

    # Also remove WAL/SHM for the backup
    for suffix in ("-shm", "-wal"):
        wal_path = Path(backup_path + suffix)
        if wal_path.exists():
            wal_path.unlink()

    dump_proc = subprocess.run(
        ["sqlite3", backup_path, ".dump"],
        capture_output=True, text=True, timeout=120,
    )
    if dump_proc.returncode == 0 and dump_proc.stdout:
        clean_lines = [
            line for line in dump_proc.stdout.splitlines()
            if not line.upper().startswith("ROLLBACK")
        ]
        rebuild_proc = subprocess.run(
            ["sqlite3", db_path],
            input="\n".join(clean_lines),
            capture_output=True, text=True, timeout=120,
        )
        if rebuild_proc.returncode != 0:
            logger.error("SQLite rebuild failed: %s", rebuild_proc.stderr[:500])
        else:
            logger.info("SQLite database recovered successfully from dump")
    else:
        logger.error("SQLite dump failed, starting with fresh DB: %s", dump_proc.stderr[:500])

    Base.metadata.create_all(engine)


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

    # Ensure auth schema (is_admin column on users table)
    if "users" in inspector.get_table_names():
        existing_user_cols = {row[1] for row in engine.connect().execute(text("PRAGMA table_info(users)")).fetchall()}
        if "is_admin" not in existing_user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            # Set first user as admin if is_admin not present
            with engine.begin() as conn:
                conn.execute(text("UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)"))

    if "ai_jobs" not in inspector.get_table_names() or "ai_runs" not in inspector.get_table_names():
        return

    required_columns = {
        "ai_jobs": {
            "job_type": "ALTER TABLE ai_jobs ADD COLUMN job_type VARCHAR(40) DEFAULT 'stock_pick'",
            "result_schema_version": "ALTER TABLE ai_jobs ADD COLUMN result_schema_version VARCHAR(20) DEFAULT '1.0'",
            "active_rulepack_id": "ALTER TABLE ai_jobs ADD COLUMN active_rulepack_id INTEGER",
            "display_group": "ALTER TABLE ai_jobs ADD COLUMN display_group VARCHAR(20) DEFAULT '盘中'",
            "engine_type": "ALTER TABLE ai_jobs ADD COLUMN engine_type VARCHAR(20) DEFAULT 'claude-code'",
            "engine_config_json": "ALTER TABLE ai_jobs ADD COLUMN engine_config_json TEXT DEFAULT '{}'",
            "auto_schedule": "ALTER TABLE ai_jobs ADD COLUMN auto_schedule BOOLEAN DEFAULT 1",
            "last_executed_at": "ALTER TABLE ai_jobs ADD COLUMN last_executed_at DATETIME",
        },
        "ai_runs": {
            "result_type": "ALTER TABLE ai_runs ADD COLUMN result_type VARCHAR(40)",
            "result_payload_json": "ALTER TABLE ai_runs ADD COLUMN result_payload_json TEXT",
            "push_payload_json": "ALTER TABLE ai_runs ADD COLUMN push_payload_json TEXT",
            "error_stage": "ALTER TABLE ai_runs ADD COLUMN error_stage VARCHAR(40)",
            "duration_ms": "ALTER TABLE ai_runs ADD COLUMN duration_ms INTEGER",
            "engine_type": "ALTER TABLE ai_runs ADD COLUMN engine_type VARCHAR(20)",
            "engine_config_json": "ALTER TABLE ai_runs ADD COLUMN engine_config_json TEXT",
            "token_usage_json": "ALTER TABLE ai_runs ADD COLUMN token_usage_json TEXT",
        },
        "ai_picks": {
            "pick_level": "ALTER TABLE ai_picks ADD COLUMN pick_level VARCHAR(40)",
            "reason_detail": "ALTER TABLE ai_picks ADD COLUMN reason_detail TEXT",
            "capital_profile_json": "ALTER TABLE ai_picks ADD COLUMN capital_profile_json TEXT",
            "signal_context": "ALTER TABLE ai_picks ADD COLUMN signal_context VARCHAR(500)",
            "risk_flags_json": "ALTER TABLE ai_picks ADD COLUMN risk_flags_json TEXT",
            "entry_hint": "ALTER TABLE ai_picks ADD COLUMN entry_hint VARCHAR(500)",
            "theme_tags_json": "ALTER TABLE ai_picks ADD COLUMN theme_tags_json TEXT",
        },
    }

    with engine.begin() as conn:
        for table_name, statements in required_columns.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()}
            for column_name, ddl in statements.items():
                if column_name not in existing:
                    conn.execute(text(ddl))

        # Create new tables if they don't exist
        existing_tables = set(inspector.get_table_names())

        if "ai_run_artifacts" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE ai_run_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES ai_runs(id),
                    artifact_type VARCHAR(40) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    content_json TEXT,
                    file_path VARCHAR(500),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_ai_run_artifacts_run_type ON ai_run_artifacts (run_id, artifact_type)"))

        if "ai_skill_templates" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE ai_skill_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id INTEGER NOT NULL REFERENCES ai_skills(id),
                    template_type VARCHAR(40) NOT NULL,
                    prompt_template TEXT NOT NULL,
                    config_json TEXT,
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_ai_skill_templates_skill_active ON ai_skill_templates (skill_id, is_active)"))


def build_static_page_response(filename: str) -> FileResponse:
    response = FileResponse(Path(__file__).parent / "static" / filename)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"


def _check_cli_available(name: str) -> bool:
    """Check if a CLI tool is available in PATH or common install locations."""
    import shutil

    if shutil.which(name) is not None:
        return True

    # Fallback: check common install paths (e.g. uv/uvicorn strips PATH)
    home = Path.home()
    common_paths = [
        home / ".local" / "bin" / name,
        home / ".hermes" / "node" / "bin" / name,
        home / ".cargo" / "bin" / name,
        home / ".nvm" / "versions" / "node" / "*" / "bin" / name,
        Path("/opt") / "homebrew" / "bin" / name,
        Path("/usr") / "local" / "bin" / name,
    ]
    for p in common_paths:
        if "*" in str(p):
            import glob

            if glob.glob(str(p)):
                return True
        elif p.exists():
            return True
    return False


def _find_cli_path(name: str) -> str | None:
    """Find the full path to a CLI tool, checking PATH and common install locations."""
    import shutil

    # First try shutil.which
    path = shutil.which(name)
    if path:
        return path

    # Fallback: check common install paths
    home = Path.home()
    common_paths = [
        home / ".local" / "bin" / name,
        home / ".hermes" / "node" / "bin" / name,
        home / ".cargo" / "bin" / name,
        Path("/opt") / "homebrew" / "bin" / name,
        Path("/usr") / "local" / "bin" / name,
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return None


def build_spa_shell_response() -> FileResponse:
    response = FileResponse(Path(__file__).parent / "static" / SPA_SHELL_FILENAME)
    response.headers["Cache-Control"] = SPA_SHELL_CACHE_CONTROL
    return response


def _parse_cron_to_aps_kwargs(cron_expr: str) -> dict[str, str]:
    """Parse standard 5-field cron expression to APScheduler cron kwargs.

    Format: minute hour day month day_of_week
    Example: "20 8 * * 1-5" -> {"minute": "20", "hour": "8", "day": "*", "month": "*", "day_of_week": "1-5"}
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr!r} (expected 5 fields)")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


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
    # Ensure scheduler-related logs go to stderr (captured by launchd)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(_handler)
    # Also configure skill_executor logger
    _se_logger = logging.getLogger("app.services.skill_executor")
    if not any(isinstance(h, logging.StreamHandler) for h in _se_logger.handlers):
        _se_handler = logging.StreamHandler()
        _se_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        _se_logger.addHandler(_se_handler)
        logger.setLevel(logging.INFO)

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
    auth_service = AuthService()
    with session_factory() as bootstrap_session:
        try:
            ai_center.ensure_builtin_registry(bootstrap_session)
        except OperationalError:
            bootstrap_session.rollback()
            logger.warning("ai center builtin registry bootstrap skipped because local database schema is behind")
        try:
            auth_service.ensure_default_admin(bootstrap_session)
        except OperationalError:
            bootstrap_session.rollback()
            logger.warning("auth default admin bootstrap skipped because local database schema is behind")
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
            # Register AI Skill cron jobs
            try:
                with session_factory() as session:
                    from app.models import AiJob as AiJobModel
                    from sqlalchemy import select
                    ai_jobs = list(session.scalars(select(AiJobModel).where(AiJobModel.enabled == True, AiJobModel.auto_schedule == True, AiJobModel.schedule_rrule_or_cron.isnot(None))))
                    for job in ai_jobs:
                        cron_expr = job.schedule_rrule_or_cron
                        if not cron_expr:
                            continue
                        try:
                            cron_kwargs = _parse_cron_to_aps_kwargs(cron_expr)
                            job_id = job.id
                            scheduler.add_job(
                                lambda jid=job_id: _execute_ai_skill_job(jid, session_factory, ai_center, now_provider),
                                "cron",
                                id=f"ai-skill-{job.id}",
                                max_instances=1,
                                coalesce=True,
                                misfire_grace_time=3600,
                                replace_existing=True,
                                **cron_kwargs,
                            )
                            next_run = None
                            try:
                                next_run = scheduler.get_job(f"ai-skill-{job.id}").next_run_time
                            except (AttributeError, TypeError):
                                pass
                            logger.info(
                                "registered ai-skill cron job: %s (id=%d, cron=%s, next_run=%s)",
                                job.name, job.id, cron_expr,
                                next_run.isoformat() if next_run else "N/A",
                            )
                        except ValueError as exc:
                            logger.warning("failed to parse cron for job %d (%s): %s", job.id, job.name, exc)
            except Exception:
                logger.exception("failed to register ai-skill cron jobs")
            # Catch-up: run jobs that should have fired today but haven't
            try:
                with session_factory() as session:
                    from app.models import AiJob as AiJobModel, AiRun as AiRunModel, AiSkill as AiSkillModel
                    now = now_provider()
                    today = now.date()
                    catchup_jobs = list(session.scalars(
                        select(AiJobModel).where(
                            AiJobModel.enabled == True,
                            AiJobModel.auto_schedule == True,
                            AiJobModel.schedule_rrule_or_cron.isnot(None),
                        )
                    ))
                    for catchup_job in catchup_jobs:
                        cron_expr = catchup_job.schedule_rrule_or_cron
                        if not cron_expr:
                            continue
                        try:
                            cron_kwargs = _parse_cron_to_aps_kwargs(cron_expr)
                        except ValueError:
                            continue
                        # Check day-of-week constraint
                        dow = cron_kwargs.get("day_of_week", "*")
                        if dow != "*":
                            weekday_map = {"1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "0": 6}
                            allowed_days: set[int] = set()
                            for part in dow.split(","):
                                if "-" in part:
                                    start, end = part.split("-")
                                    for d in range(int(start), int(end) + 1):
                                        allowed_days.add(weekday_map.get(str(d), -1))
                                else:
                                    allowed_days.add(weekday_map.get(part, -1))
                            if now.weekday() not in allowed_days:
                                continue
                        scheduled_hour = int(cron_kwargs.get("hour", "0"))
                        scheduled_minute = int(cron_kwargs.get("minute", "0"))
                        scheduled_time_today = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
                        if now <= scheduled_time_today:
                            continue  # Not yet time for this job today
                        # Check if this job already ran today
                        already_ran = session.scalar(
                            select(AiRunModel.id).where(
                                AiRunModel.job_id == catchup_job.id,
                                AiRunModel.trading_date == today,
                                AiRunModel.run_type == "production",
                            ).limit(1)
                        ) is not None
                        if already_ran:
                            continue
                        if catchup_job.last_executed_at and catchup_job.last_executed_at.date() == today:
                            continue
                        catchup_job_id = catchup_job.id
                        scheduler.add_job(
                            lambda jid=catchup_job_id: _execute_ai_skill_job(jid, session_factory, ai_center, now_provider),
                            "date",
                            run_date=datetime.now() + timedelta(seconds=5),
                            id=f"ai-skill-catchup-{catchup_job.id}",
                            max_instances=1,
                            misfire_grace_time=3600,
                            replace_existing=True,
                        )
                        logger.info(
                            "scheduled catch-up for ai-skill job: %s (id=%d, scheduled_time=%02d:%02d, now=%s)",
                            catchup_job.name, catchup_job.id, scheduled_hour, scheduled_minute, now.strftime("%H:%M"),
                        )
            except Exception:
                logger.exception("failed to schedule ai-skill catch-up jobs")
            scheduler.start()
            ai_skill_job_count = sum(1 for j in scheduler.get_jobs() if j.id.startswith("ai-skill-"))
            logger.info("scheduler started with %d AI skill cron jobs registered", ai_skill_job_count)
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Sector Fund Monitor", lifespan=lifespan)

    # Store auth service and session factory for middleware access
    app.state.auth_service = auth_service
    app.state.session_factory = session_factory
    if enable_scheduler:
        app.state.scheduler = scheduler

    # Auth middleware (protects /api/ except /api/auth/)
    app.add_middleware(AuthMiddleware)

    # Auth routes
    app.include_router(auth_router.router)

    # Helper for auth router to access service
    def get_auth_service():
        return auth_service

    # Expose get_db for auth router
    app.state.get_db = get_db

    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/login")
    def login_page() -> FileResponse:
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

    @app.get("/user-mgmt")
    def user_mgmt_page() -> FileResponse:
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

    @app.get("/api/ai/scheduler-status")
    def ai_scheduler_status(db: Session = Depends(get_db)) -> dict:
        """Return scheduler state and AI skill job registration status."""
        from app.models import AiJob as AiJobModel
        from sqlalchemy import select

        sched = getattr(app.state, "scheduler", None)
        if sched is None or not sched.running:
            return {"scheduler_running": False, "registered_jobs": [], "db_job_statuses": []}

        registered = []
        for aps_job in sched.get_jobs():
            if aps_job.id.startswith("ai-skill-"):
                registered.append({
                    "aps_job_id": aps_job.id,
                    "next_run_time": aps_job.next_run_time.isoformat() if aps_job.next_run_time else None,
                    "trigger": str(aps_job.trigger),
                })

        registered_ids = {j["aps_job_id"] for j in registered}
        db_jobs = list(db.scalars(
            select(AiJobModel).where(AiJobModel.schedule_rrule_or_cron.isnot(None))
        ))
        job_statuses = []
        for db_job in db_jobs:
            aps_id = f"ai-skill-{db_job.id}"
            job_statuses.append({
                "id": db_job.id,
                "name": db_job.name,
                "cron": db_job.schedule_rrule_or_cron,
                "auto_schedule": db_job.auto_schedule,
                "enabled": db_job.enabled,
                "engine_type": db_job.engine_type,
                "registered_in_scheduler": aps_id in registered_ids,
                "last_executed_at": db_job.last_executed_at.isoformat() if db_job.last_executed_at else None,
            })

        return {
            "scheduler_running": True,
            "registered_ai_skill_jobs": len(registered),
            "registered_jobs": registered,
            "db_job_statuses": job_statuses,
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

    # ── Job Results (inbox scan) ──────────────────────────────────────

    @app.get("/api/ai/job-results")
    def ai_job_results_list(
        trading_date: date | None = Query(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        """返回指定日期所有任务在 inbox 中的执行结果列表"""
        target_date = trading_date or now_provider().date()
        results = []
        for f in sorted(AI_CENTER_INBOX_DIR.glob("*.json"), reverse=True):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
                f_date = payload.get("trading_date")
                if f_date != target_date.isoformat():
                    continue
                results.append({
                    "job_name": payload.get("job_name") or payload.get("skill_name"),
                    "job_type": payload.get("job_type"),
                    "trading_date": f_date,
                    "has_raw_output": bool(payload.get("raw_output")),
                    "run_type": payload.get("run_type"),
                    "file_name": f.name,
                    "summary_headline": (payload.get("summary") or {}).get("market_phase") or (payload.get("summary") or {}).get("headline"),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return {"trading_date": target_date.isoformat(), "items": results}

    @app.get("/api/ai/job-results/{job_name:path}/latest")
    def ai_job_result_detail(
        job_name: str,
        trading_date: date | None = Query(default=None),
    ) -> dict:
        """返回指定 job_name + 日期的完整结果（含 raw_output markdown）"""
        target_date = trading_date or now_provider().date()
        for f in sorted(AI_CENTER_INBOX_DIR.glob("*.json"), reverse=True):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
                f_date = payload.get("trading_date")
                f_name = payload.get("job_name") or payload.get("skill_name")
                if f_date == target_date.isoformat() and f_name == job_name:
                    return {
                        "job_name": f_name,
                        "job_type": payload.get("job_type"),
                        "trading_date": f_date,
                        "raw_output": payload.get("raw_output"),
                        "summary": payload.get("summary"),
                        "result_payload": payload.get("result_payload"),
                        "meta": payload.get("_meta"),
                    }
            except (json.JSONDecodeError, OSError):
                continue
        return {"job_name": job_name, "trading_date": target_date.isoformat(), "raw_output": None, "summary": None}

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

    # ── Skill Execution Endpoints ──────────────────────────────────────

    @app.post("/api/ai/jobs/{job_id}/execute")
    def ai_execute_job(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        """手动触发一个 AI Job 的执行"""
        from app.services.skill_executor import get_executor, prefetch_market_data
        from app.models import AiJob as AiJobModel, AiSkill as AiSkillModel

        job = session.get(AiJobModel, job_id) if (session := db) else None
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        trading_date_val = payload.get("trading_date")
        trading_date_obj = date.fromisoformat(str(trading_date_val)) if trading_date_val else now_provider().date()

        engine_type = job.engine_type or "claude-code"
        engine_config = json.loads(job.engine_config_json or "{}")

        try:
            executor = get_executor(engine_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Prefetch market data
        data_file = prefetch_market_data(trading_date_obj)

        skill_name = job.name
        skill = session.get(AiSkillModel, job.skill_id) if job.skill_id else None
        skill_desc = skill.description if skill else ""

        result = executor.execute(
            skill_name=skill_name,
            trading_date=trading_date_obj,
            data_file=data_file,
            output_dir=str(AI_CENTER_INBOX_DIR),
            config=engine_config,
            skill_prompt=skill_desc,
        )

        # Update last_executed_at
        job.last_executed_at = now_provider()
        session.add(job)
        session.commit()

        return {
            "success": result.success,
            "skill_name": result.skill_name,
            "trading_date": result.trading_date,
            "engine_type": result.engine_type,
            "duration_ms": result.duration_ms,
            "output_files": result.output_files,
            "error": result.error,
        }

    # ── Job Toggle Endpoints ───────────────────────────────────────────

    @app.patch("/api/ai/jobs/{job_id}/toggle-schedule")
    def ai_toggle_job_schedule(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        """切换 AI Job 的自动调度开关 (auto_schedule)"""
        from app.models import AiJob as AiJobModel

        job = session.get(AiJobModel, job_id) if (session := db) else None
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        # Toggle or set explicit value
        if "auto_schedule" in payload:
            job.auto_schedule = bool(payload["auto_schedule"])
        else:
            job.auto_schedule = not job.auto_schedule

        session.add(job)
        session.commit()

        # Dynamically update APScheduler
        _sync_ai_job_to_scheduler(job, app.state.scheduler, session_factory, ai_center, now_provider)

        return {
            "id": job.id,
            "name": job.name,
            "auto_schedule": job.auto_schedule,
            "enabled": job.enabled,
        }

    @app.patch("/api/ai/jobs/{job_id}/toggle-enabled")
    def ai_toggle_job_enabled(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        """切换 AI Job 的启用状态 (enabled)"""
        from app.models import AiJob as AiJobModel

        job = session.get(AiJobModel, job_id) if (session := db) else None
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        # Toggle or set explicit value
        if "enabled" in payload:
            job.enabled = bool(payload["enabled"])
        else:
            job.enabled = not job.enabled

        session.add(job)
        session.commit()

        # Dynamically update APScheduler
        _sync_ai_job_to_scheduler(job, app.state.scheduler, session_factory, ai_center, now_provider)

        return {
            "id": job.id,
            "name": job.name,
            "auto_schedule": job.auto_schedule,
            "enabled": job.enabled,
        }

    # ── Skill Chat / Creation Endpoints ───────────────────────────────

    _SKILL_CHAT_SYSTEM_PROMPT = """你是一个专业的A股选股策略专家。请根据用户的需求，生成选股策略配置或回答策略相关问题。

如果用户要求创建新策略，请生成以下格式的JSON：

{
  "skill_name": "策略名称（简短）",
  "skill_category": "stock-pick|news-scan|review|stock-confirm|position-review|weekly-review",
  "description": "策略描述（一句话）",
  "revision_title": "版本标题",
  "revision_content": "策略执行逻辑的详细描述，包括选股条件、过滤规则、排序方式等",
  "job_name": "定时任务名称（如 09:30 某某选股）",
  "schedule_label": "显示标签（如 09:30）",
  "schedule_rrule_or_cron": "标准5字段cron表达式",
  "job_type": "stock_pick|news_scan|day_review|stock_confirm|position_review|weekly_review",
  "display_group": "盘前|盘中|盘后|夜间|周报",
  "result_schema_version": "2.0"
}

Cron表达式规则（标准5字段：分 时 日 月 星期）：
- 盘前任务：20 8 * * 1-5（工作日8:20）
- 盘中任务：26 9 * * 1-5（工作日9:26）
- 盘后任务：0 19 * * 1-5（工作日19:00）
- 夜间任务：0 20 * * 1-5（工作日20:00）
- 周报任务：0 22 * * 5（周五22:00）

请用中文回复，JSON配置放在代码块中。"""

    @app.post("/api/ai/skill-chat")
    def ai_skill_chat(payload: dict = Body(default={})) -> dict:
        """AI Skill 对话入口 - 通过自然语言创建或修改选股策略"""
        message = payload.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        history = payload.get("history", [])
        conversation = []
        for h in history:
            if h.get("role") == "user":
                conversation.append(f"用户: {h.get('content', '')}")
            elif h.get("role") == "assistant":
                conversation.append(f"助手: {h.get('content', '')}")

        conversation_text = "\n".join(conversation)

        full_prompt = f"""{_SKILL_CHAT_SYSTEM_PROMPT}

{conversation_text}

用户: {message}

请回复："""

        # Build the actual prompt for claude CLI
        cli_prompt = f"""{_SKILL_CHAT_SYSTEM_PROMPT}

{conversation_text}

用户: {message}

请回复："""

        import subprocess
        import time

        logger.info("skill-chat: processing message from user")
        start = time.time()

        # Find claude CLI path
        claude_path = _find_cli_path("claude")
        if not claude_path:
            return {
                "response": "Claude Code CLI 未找到，请检查安装。",
                "skill_draft": None,
                "duration_ms": 0,
            }

        try:
            proc = subprocess.run(
                [
                    claude_path, "-p", cli_prompt,
                    "--allowedTools", "Bash(curl*)", "Bash(python*)", "Write", "Read",
                    "--output-format", "text",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            duration_ms = int((time.time() - start) * 1000)

            if proc.returncode != 0:
                logger.error("skill-chat claude-code exited with code %d: %s", proc.returncode, proc.stderr[:500])
                return {
                    "response": f"执行出错: {proc.stderr[:500]}",
                    "skill_draft": None,
                    "duration_ms": duration_ms,
                }

            output = proc.stdout
            logger.info("skill-chat completed in %dms, output length=%d", duration_ms, len(output))

            # Try to extract JSON skill draft from output
            skill_draft = None
            import re
            # Look for JSON code block
            json_match = re.search(r'```json\s*(.*?)\s*```', output, re.DOTALL)
            if not json_match:
                json_match = re.search(r'```\s*(\{.*?\})\s*```', output, re.DOTALL)
            if json_match:
                try:
                    skill_draft = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            return {
                "response": output,
                "skill_draft": skill_draft,
                "duration_ms": duration_ms,
            }

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            logger.error("skill-chat timed out after %dms", duration_ms)
            return {
                "response": "请求超时，请重试或简化需求描述。",
                "skill_draft": None,
                "duration_ms": duration_ms,
            }

    @app.put("/api/ai/jobs/{job_id}/engine")
    def ai_update_job_engine(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
        """更新 AI Job 的执行引擎配置"""
        from app.models import AiJob as AiJobModel

        job = session.get(AiJobModel, job_id) if (session := db) else None
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        if "engine_type" in payload:
            job.engine_type = payload["engine_type"]
        if "engine_config" in payload:
            job.engine_config_json = json.dumps(payload["engine_config"], ensure_ascii=False)
        if "auto_schedule" in payload:
            job.auto_schedule = bool(payload["auto_schedule"])

        session.add(job)
        session.commit()

        return {
            "id": job.id,
            "name": job.name,
            "engine_type": job.engine_type,
            "engine_config": json.loads(job.engine_config_json or "{}"),
            "auto_schedule": job.auto_schedule,
        }

    @app.get("/api/ai/engines")
    def ai_list_engines() -> dict:
        """列出可用的执行引擎"""
        return {
            "engines": [
                {
                    "type": "claude-code",
                    "name": "Claude Code CLI",
                    "description": "Anthropic Claude Code 命令行工具",
                    "available": _check_cli_available("claude"),
                    "config_fields": ["model", "timeout_s", "allowed_tools"],
                },
                {
                    "type": "goose",
                    "name": "Goose CLI",
                    "description": "Block Goose 开源 Agent",
                    "available": _check_cli_available("goose"),
                    "config_fields": ["provider", "model", "timeout_s", "extensions"],
                },
                {
                    "type": "custom",
                    "name": "Custom Script",
                    "description": "自定义脚本执行器",
                    "available": True,
                    "config_fields": ["command", "timeout_s"],
                },
            ]
        }

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


def _execute_ai_skill_job(
    job_id: int,
    session_factory: sessionmaker[Session],
    ai_center: AiCenterService,
    now_provider: Callable[[], datetime],
) -> dict | None:
    """Execute an AI Skill job: fetch market data, run skill via CLI, import results."""
    from app.services.skill_executor import get_executor, prefetch_market_data
    from app.models import AiJob as AiJobModel
    from app.models import AiSkill as AiSkillModel

    started = time.perf_counter()
    logger.info("ai-skill job %d started", job_id)

    with session_factory() as session:
        try:
            job = session.get(AiJobModel, job_id)
            if job is None:
                logger.warning("ai-skill job %d not found", job_id)
                return None
            if not job.enabled:
                logger.info("ai-skill job %d is disabled, skipping", job_id)
                return None

            skill = session.get(AiSkillModel, job.skill_id) if job.skill_id else None
            if skill is None:
                logger.warning("ai-skill job %d: skill %s not found", job_id, job.skill_id)
                return None

            trading_date = now_provider().date()
            engine_type = job.engine_type or "claude-code"
            engine_config = json.loads(job.engine_config_json or "{}")

            # Prefetch market data
            data_file = prefetch_market_data(trading_date)

            # Get executor and run
            executor = get_executor(engine_type)
            result = executor.execute(
                skill_name=job.name,
                trading_date=trading_date,
                data_file=data_file,
                output_dir=str(AI_CENTER_INBOX_DIR),
                config=engine_config,
                skill_prompt=skill.description or "",
            )

            # Update last_executed_at
            job.last_executed_at = now_provider()
            session.add(job)
            session.commit()

            # Patch output files: ensure skill_name matches DB skill name for import
            if result.output_files and skill.name:
                for fpath in result.output_files:
                    try:
                        from pathlib import Path as P
                        p = P(fpath)
                        payload = json.loads(p.read_text(encoding="utf-8"))
                        if payload.get("skill_name") != skill.name:
                            payload["skill_name"] = skill.name
                            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass

            # Import results into DB
            if result.success:
                try:
                    imported = ai_center.scan_import_directory(
                        session,
                        inbox_dir=AI_CENTER_INBOX_DIR,
                        processed_dir=AI_CENTER_PROCESSED_DIR,
                    )
                    logger.info("ai-skill job %d: imported=%d, failed=%d", job_id, imported.get("imported", 0), imported.get("failed", 0))
                except Exception:
                    logger.exception("ai-skill job %d: failed to import results", job_id)

            duration = time.perf_counter() - started
            logger.info(
                "ai-skill job %d finished in %.2fs: success=%s, output_files=%d",
                job_id, duration, result.success, len(result.output_files),
            )

            return {
                "success": result.success,
                "skill_name": result.skill_name,
                "trading_date": result.trading_date,
                "duration_ms": result.duration_ms,
                "output_files": result.output_files,
                "error": result.error,
            }

        except Exception:
            if hasattr(session, "rollback"):
                session.rollback()
            logger.exception("ai-skill job %d failed after %.2fs", job_id, time.perf_counter() - started)
            return None


def _sync_ai_job_to_scheduler(
    job: "AiJob",
    scheduler: BackgroundScheduler,
    session_factory: sessionmaker[Session],
    ai_center: AiCenterService,
    now_provider: Callable[[], datetime],
) -> None:
    """Dynamically add/remove an AI Job from the APScheduler based on its enabled + auto_schedule state."""
    from app.models import AiJob as AiJobModel

    aps_job_id = f"ai-skill-{job.id}"

    if not job.enabled or not job.auto_schedule or not job.schedule_rrule_or_cron:
        # Remove from scheduler if present
        existing = scheduler.get_job(aps_job_id)
        if existing is not None:
            scheduler.remove_job(aps_job_id)
            logger.info("removed ai-skill cron job: %s (id=%d, enabled=%s, auto_schedule=%s)",
                        job.name, job.id, job.enabled, job.auto_schedule)
        return

    # Add/update in scheduler
    try:
        cron_kwargs = _parse_cron_to_aps_kwargs(job.schedule_rrule_or_cron)
        job_id = job.id
        scheduler.add_job(
            lambda jid=job_id: _execute_ai_skill_job(jid, session_factory, ai_center, now_provider),
            "cron",
            id=aps_job_id,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            replace_existing=True,
            **cron_kwargs,
        )
        next_run = None
        try:
            next_run = scheduler.get_job(aps_job_id).next_run_time
        except (AttributeError, TypeError):
            pass
        logger.info(
            "synced ai-skill cron job: %s (id=%d, cron=%s, next_run=%s)",
            job.name, job.id, job.schedule_rrule_or_cron,
            next_run.isoformat() if next_run else "N/A",
        )
    except ValueError as exc:
        logger.warning("failed to sync ai-skill job %d (%s): %s", job.id, job.name, exc)


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
