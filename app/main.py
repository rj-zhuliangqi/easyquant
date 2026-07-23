from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import fcntl
import json
import logging
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import uuid
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import StreamingResponse
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
from app.time_utils import now_cn
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
from app.services.daily_bars import DailyBarsService
from app.services.history_cache import HistoryCacheService
from app.services.home_dashboard import HomeDashboardService
from app.services.limit_up import LimitUpService
from app.services.market_signal import MarketSignalService
from app.services.market_temperature import MarketTemperatureService
from app.services.market_time import is_trading_day, is_trading_time
from app.services.news_service import NewsService
from app.services.page_payloads import PagePayloadService
from app.services.realtime_cache import RealtimeCacheService
from app.services.screener import ScreenerService
from app.services.workspace import WorkspaceService


logger = logging.getLogger(__name__)
STATIC_ASSET_VERSION = "20260602-navrestore"
SPA_SHELL_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
SPA_SHELL_FILENAME = "spa/frontend/index.html"
SPA_NAVIGATION_PATHS = (
    "/",
    "/login",
    "/news",
    "/alerts",
    "/opportunity-pool",
    "/sector-monitor",
    "/limit-up-ladder",
    "/ai-center",
    "/ai-jobs",
    "/review",
    "/workspace",
    "/screener",
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
    """检查 SQLite 完整性，仅在**确认损坏**时重建。

    关键修正：``OperationalError``（如 "database is locked"）≠ 损坏。
    撞锁时只重试（最多 3 次、间隔 2s），重试仍失败则**放弃启动并报错**，
    绝不 rename/删除 WAL -- 这正是过去连环损坏的根因（B 进程撞锁被误判
    损坏 -> 删掉 A 进程正在写的 WAL -> 真损坏）。

    只有 ``integrity_check`` 成功执行并返回非 "ok" 才判定损坏，且恢复前：
    1. 用 fcntl.flock 加排他锁（LOCK_EX|LOCK_NB）确认无其他进程在恢复；
    2. WAL/SHM 一并 rename 备份（而非 unlink 删除），保留未 checkpoint 数据。
    """
    db_url = str(engine.url)
    if not db_url.startswith("sqlite"):
        return
    db_path = db_url.replace("sqlite+pysqlite:///", "").replace("sqlite:///", "")
    if not db_path or not Path(db_path).exists():
        return

    # 阶段 1：重试执行 integrity_check -- 撞锁只重试，不当损坏
    integrity_result: str | None = None
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with engine.connect() as conn:
                integrity_result = conn.execute(text("PRAGMA integrity_check")).scalar()
            break
        except OperationalError as exc:
            last_exc = exc
            logger.warning("SQLite integrity_check 撞锁/异常，重试 %d/3: %s", attempt + 1, exc)
            time.sleep(2)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("SQLite integrity_check 异常，重试 %d/3: %s", attempt + 1, exc)
            time.sleep(2)
    else:
        # 3 次重试均失败：放弃启动，绝不删除/重命名，保护数据
        raise RuntimeError(
            "SQLite integrity_check 连续失败（可能被其他进程占用），拒绝启动以保护数据；"
            f"请确认没有其他 easyquant 实例在运行。最后错误: {last_exc}"
        ) from last_exc

    if integrity_result == "ok":
        return
    logger.warning("SQLite integrity check failed: %s - attempting recovery", str(integrity_result)[:200])

    # 阶段 2：确认损坏 -> 加排他锁后恢复
    engine.dispose()
    db_file = Path(db_path)
    try:
        with open(db_file, "rb") as lock_fh:
            try:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    f"数据库确认损坏但被其他进程占用，无法加排他锁执行恢复: {exc}"
                ) from exc
            _rebuild_sqlite_db(db_path)
    except FileNotFoundError:
        # dispose 后文件已不存在（被其他流程移走），直接重建
        _rebuild_sqlite_db(db_path)
    finally:
        Base.metadata.create_all(engine)


def _rebuild_sqlite_db(db_path: str) -> None:
    """dump -> 重建损坏的 SQLite 库。WAL/SHM rename 备份而非删除。"""
    backup_path = db_path + ".corrupted." + time.strftime("%Y%m%d%H%M%S")
    logger.warning("Renaming corrupted DB to %s", backup_path)

    # WAL/SHM 一并 rename 备份（保留未 checkpoint 数据，便于事后排查）
    for suffix in ("-shm", "-wal"):
        side = Path(db_path + suffix)
        if side.exists():
            side.rename(Path(backup_path + suffix))

    Path(db_path).rename(backup_path)

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


def ensure_indexes(engine: Engine) -> None:
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            try:
                index.create(bind=engine, checkfirst=True)
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise


def _add_missing_columns(engine: Engine, table: str, columns: dict[str, str]) -> None:
    """P5-3: 极简 schema 漂移助手 — 仅做"缺则 ADD COLUMN"差分。

    表结构本身以 ``app/models.py`` 为唯一真相（``Base.metadata.create_all``
    负责建表），本函数只补历史库缺的新列。``columns`` 形如
    ``{"col_name": "ALTER TABLE x ADD COLUMN col_name TYPE DEFAULT ..."}``。
    """
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return  # 表本身不存在时交给 create_all 处理
    existing = {row[1] for row in engine.connect().execute(text(f"PRAGMA table_info({table})")).fetchall()}
    missing = [(col, ddl) for col, ddl in columns.items() if col not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for _, ddl in missing:
            conn.execute(text(ddl))
    logger.info("schema migration: added %d column(s) to %s (%s)",
                len(missing), table, ", ".join(col for col, _ in missing))


def ensure_ai_center_schema(engine: Engine) -> None:
    """P5-3: 仅做缺列补齐；新表由 ``Base.metadata.create_all`` 创建。

    历史上 ``ensure_ai_center_schema`` 同时承担建表+列漂移维护，逻辑分散在
    ``main.py`` 与 ``models.py`` 两份真相里（容易漂移）。现在表结构以
    ``models.py`` 为准，本函数只补老库可能缺的新列。
    """
    # users.is_admin（2026-06 引入）
    _add_missing_columns(engine, "users", {
        "is_admin": "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0",
    })
    # ai_jobs / ai_runs / ai_picks 增量列（按需扩展，新表走 create_all）
    _add_missing_columns(engine, "ai_jobs", {
        "job_type": "ALTER TABLE ai_jobs ADD COLUMN job_type VARCHAR(40) DEFAULT 'stock_pick'",
        "result_schema_version": "ALTER TABLE ai_jobs ADD COLUMN result_schema_version VARCHAR(20) DEFAULT '1.0'",
        "active_rulepack_id": "ALTER TABLE ai_jobs ADD COLUMN active_rulepack_id INTEGER",
        "display_group": "ALTER TABLE ai_jobs ADD COLUMN display_group VARCHAR(20) DEFAULT '盘中'",
        "engine_type": "ALTER TABLE ai_jobs ADD COLUMN engine_type VARCHAR(20) DEFAULT 'claude-code'",
        "engine_config_json": "ALTER TABLE ai_jobs ADD COLUMN engine_config_json TEXT DEFAULT '{}'",
        "auto_schedule": "ALTER TABLE ai_jobs ADD COLUMN auto_schedule BOOLEAN DEFAULT 1",
        "last_executed_at": "ALTER TABLE ai_jobs ADD COLUMN last_executed_at DATETIME",
    })
    _add_missing_columns(engine, "ai_runs", {
        "result_type": "ALTER TABLE ai_runs ADD COLUMN result_type VARCHAR(40)",
        "result_payload_json": "ALTER TABLE ai_runs ADD COLUMN result_payload_json TEXT",
        "push_payload_json": "ALTER TABLE ai_runs ADD COLUMN push_payload_json TEXT",
        "error_stage": "ALTER TABLE ai_runs ADD COLUMN error_stage VARCHAR(40)",
        "duration_ms": "ALTER TABLE ai_runs ADD COLUMN duration_ms INTEGER",
        "engine_type": "ALTER TABLE ai_runs ADD COLUMN engine_type VARCHAR(20)",
        "engine_config_json": "ALTER TABLE ai_runs ADD COLUMN engine_config_json TEXT",
        "token_usage_json": "ALTER TABLE ai_runs ADD COLUMN token_usage_json TEXT",
    })
    _add_missing_columns(engine, "ai_picks", {
        "pick_level": "ALTER TABLE ai_picks ADD COLUMN pick_level VARCHAR(40)",
        "reason_detail": "ALTER TABLE ai_picks ADD COLUMN reason_detail TEXT",
        "capital_profile_json": "ALTER TABLE ai_picks ADD COLUMN capital_profile_json TEXT",
        "signal_context": "ALTER TABLE ai_picks ADD COLUMN signal_context VARCHAR(500)",
        "risk_flags_json": "ALTER TABLE ai_picks ADD COLUMN risk_flags_json TEXT",
        "entry_hint": "ALTER TABLE ai_picks ADD COLUMN entry_hint VARCHAR(500)",
        "theme_tags_json": "ALTER TABLE ai_picks ADD COLUMN theme_tags_json TEXT",
    })
    # screener_presets 增量列（2026-07-22 选股器重构：策略分类 + 评分模式）
    _add_missing_columns(engine, "screener_presets", {
        "category": "ALTER TABLE screener_presets ADD COLUMN category VARCHAR(40) DEFAULT '量价突破'",
        "match_mode": "ALTER TABLE screener_presets ADD COLUMN match_mode VARCHAR(10) DEFAULT 'all'",
        "min_score": "ALTER TABLE screener_presets ADD COLUMN min_score INTEGER DEFAULT 0",
        "ir_json": "ALTER TABLE screener_presets ADD COLUMN ir_json TEXT",
    })
    # users 表加 is_admin 后：把最早一个用户升为管理员（首次部署兜底）
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_admin = 1")).scalar()
    if row == 0:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)"))


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


# ── Skill Chat SSE ─────────────────────────────────────────────
# _SKILL_CHAT_TIMEOUT_SECONDS: subprocess 兜底超时（远大于 cloudflared 100s 边缘空闲超时，
#   中间只要有 SSE delta/心跳流出，cloudflared 不会切断）
# _SKILL_CHAT_HEARTBEAT_SECONDS: SSE 注释行 ": ping\n\n" 周期，防止 cloudflared idle 切断
_SKILL_CHAT_TIMEOUT_SECONDS = 300
_SKILL_CHAT_HEARTBEAT_SECONDS = 15

# 系统 prompt 必须下沉到模块级，因为 helper 函数（_build_skill_chat_prompt 等）会在模块作用域调用
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


def _build_skill_chat_prompt(history: list, message: str) -> str:
    """拼装 Claude CLI 单次调用的最终 prompt。"""
    conversation = []
    for h in history:
        if h.get("role") == "user":
            conversation.append(f"用户: {h.get('content', '')}")
        elif h.get("role") == "assistant":
            conversation.append(f"助手: {h.get('content', '')}")
    conversation_text = "\n".join(conversation)
    return f"""{_SKILL_CHAT_SYSTEM_PROMPT}

{conversation_text}

用户: {message}

请回复："""


def _extract_skill_draft(output: str):
    """从 Claude 文本输出中提取 ```json ... ``` 代码块作为 skill 草案。"""
    if not output:
        return None
    json_match = re.search(r'```json\s*(.*?)\s*```', output, re.DOTALL)
    if not json_match:
        json_match = re.search(r'```\s*(\{.*?\})\s*```', output, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group(1))
    except json.JSONDecodeError:
        return None


def _skill_chat_event(payload: dict) -> bytes:
    """把 dict 序列化成 SSE `data: {...}\\n\\n` 字节流。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _kill_proc(proc: subprocess.Popen | None) -> None:
    """安全终止 Claude 子进程并等待回收（用于客户端断开 / 兜底超时）。"""
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            logger.exception("skill-chat: proc.kill() failed")
        try:
            proc.wait(timeout=5)
        except Exception:
            logger.exception("skill-chat: proc.wait() after kill failed")


def _skill_chat_kill_watcher(proc: subprocess.Popen, stop_event: threading.Event) -> None:
    """后台 watcher 线程：到 _SKILL_CHAT_TIMEOUT_SECONDS 兜底 kill 子进程。"""
    deadline = time.time() + _SKILL_CHAT_TIMEOUT_SECONDS
    while not stop_event.is_set():
        if time.time() >= deadline:
            logger.warning(
                "skill-chat: watcher reached timeout (%ds), killing proc",
                _SKILL_CHAT_TIMEOUT_SECONDS,
            )
            _kill_proc(proc)
            return
        # 1s 轮询间隔足以兜底（及时 kill 即可）
        if stop_event.wait(1.0):
            return
        if proc.poll() is not None:
            return


def _skill_chat_stream_generator(claude_path: str, cli_prompt: str):
    """SSE 流式生成器：按行读 Claude stdout，每行 yield delta；15s 一次心跳。"""
    start = time.time()
    full_output_chunks: list[str] = []
    proc: subprocess.Popen | None = None
    stop_event = threading.Event()
    watcher: threading.Thread | None = None
    timed_out = False

    try:
        try:
            proc = subprocess.Popen(
                [
                    claude_path, "-p", cli_prompt,
                    "--allowedTools", "Bash(curl*)", "Bash(python*)", "Write", "Read",
                    "--output-format", "text",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                text=True,
            )
        except OSError as exc:
            logger.exception("skill-chat: failed to spawn claude")
            yield _skill_chat_event({"type": "error", "message": f"无法启动 Claude CLI: {exc}"})
            yield _skill_chat_event({"type": "done", "response": "", "skill_draft": None, "duration_ms": 0})
            return

        watcher = threading.Thread(
            target=_skill_chat_kill_watcher,
            args=(proc, stop_event),
            daemon=True,
        )
        watcher.start()

        # 用独立线程阻塞读 stdout，主循环靠 queue.get(timeout) 驱动心跳，
        # 避免 readline 阻塞期间零心跳（cloudflared 100s 空闲 -> 524）。
        line_queue: "queue.Queue[str | None]" = queue.Queue()

        def _stdout_reader() -> None:
            try:
                for line in iter(proc.stdout.readline, ""):
                    line_queue.put(line)
            except Exception:
                logger.exception("skill-chat: stdout reader thread failed")
            finally:
                line_queue.put(None)  # EOF / 异常哨兵

        reader_thread = threading.Thread(target=_stdout_reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                try:
                    line = line_queue.get(timeout=_SKILL_CHAT_HEARTBEAT_SECONDS)
                except queue.Empty:
                    # 阻塞读期间无输出 -> 主动发心跳，重置 cloudflared 空闲计时
                    yield b": ping\n\n"
                    continue
                if line is None:
                    break
                full_output_chunks.append(line)
                yield _skill_chat_event({"type": "delta", "text": line})
        except (GeneratorExit, ConnectionError):
            logger.info("skill-chat: client disconnected, killing proc")
            _kill_proc(proc)
            return
        finally:
            stop_event.set()

        if watcher and watcher.is_alive():
            watcher.join(timeout=1.0)

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("skill-chat: proc.wait() timed out, killing")
            _kill_proc(proc)

        duration_ms = int((time.time() - start) * 1000)
        full_output = "".join(full_output_chunks)
        skill_draft = _extract_skill_draft(full_output)

        # watcher 兜底超时已 kill → returncode 不为 0
        if proc.returncode not in (0, None):
            stderr_text = (proc.stderr.read() if proc.stderr else "")[:500]
            if not full_output and "timed out" in stderr_text.lower():
                timed_out = True
            logger.error(
                "skill-chat: claude exit=%d duration=%dms stderr=%s",
                proc.returncode, duration_ms, stderr_text,
            )
            if timed_out:
                yield _skill_chat_event({
                    "type": "error",
                    "message": f"请求超时（{_SKILL_CHAT_TIMEOUT_SECONDS}s），请重试或简化需求描述。",
                })
            else:
                yield _skill_chat_event({
                    "type": "error",
                    "message": f"Claude 退出码 {proc.returncode}: {stderr_text}",
                })
            yield _skill_chat_event({
                "type": "done",
                "response": full_output or stderr_text or "执行出错",
                "skill_draft": None,
                "duration_ms": duration_ms,
            })
            return

        logger.info(
            "skill-chat (stream): completed duration=%dms output_length=%d has_draft=%s",
            duration_ms, len(full_output), bool(skill_draft),
        )
        yield _skill_chat_event({
            "type": "done",
            "response": full_output,
            "skill_draft": skill_draft,
            "duration_ms": duration_ms,
        })
    except GeneratorExit:
        _kill_proc(proc)
        raise
    except Exception as exc:
        logger.exception("skill-chat: unexpected error in stream generator")
        try:
            yield _skill_chat_event({"type": "error", "message": f"内部错误: {exc}"})
            duration_ms = int((time.time() - start) * 1000)
            yield _skill_chat_event({
                "type": "done",
                "response": "",
                "skill_draft": None,
                "duration_ms": duration_ms,
            })
        except GeneratorExit:
            _kill_proc(proc)
            raise
    finally:
        stop_event.set()
        if watcher and watcher.is_alive():
            watcher.join(timeout=1.0)
        _kill_proc(proc)


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


def _run_screener_bars_incremental(
    session: Session,
    daily_bars: DailyBarsService,
) -> None:
    """15:40 收盘增量：日线增量 + prune + 持久化层 prune。

    资金流已拆到独立的 ``_run_screener_fundflow_today``（批量 clist，秒级），
    不再在此逐只拉，避免慢任务把资金流回补拖到被 misfire 杀掉。
    """
    universe = daily_bars.get_universe(session, min_amount=50_000_000.0)
    if universe.empty:
        logger.warning("screener bars incremental: universe 为空，跳过")
        return
    codes = universe["code"].astype(str).str.zfill(6).tolist()
    logger.info("screener bars incremental: universe=%d, 开始补最近 10 日日线", len(codes))
    daily_bars.ensure_recent_bars(session, codes, days=10)
    logger.info("screener bars incremental: 日线补完，开始 prune")
    try:
        daily_bars.prune_old_bars(session)
        daily_bars.prune_old_fund_flow(session)
    except Exception:
        logger.exception("screener incremental prune failed")
    # 持久化层 prune (2026-07-21)：4 张新表各保留 250 交易日
    _prune_persistence_tables(session)


def _run_screener_fundflow_today(
    session: Session,
    daily_bars: DailyBarsService,
) -> None:
    """15:40 收盘增量：全市场"今日"资金流批量入库（1 次 clist，秒级）。

    替代旧的逐只 ``_backfill_fund_flow``（5000 次 HTTP，常被 misfire 杀到只剩 1 只）。
    这是选股器资金类条件（放量突破/主力抢筹/缩量回踩）能选出票的前提。
    """
    inserted = daily_bars.backfill_fund_flow_today(session)
    logger.info("screener fundflow today: 写入 %d 行", inserted)


def _run_screener_eod_backfill(
    session: Session,
    daily_bars: DailyBarsService,
    now_provider: Callable[[], datetime],
) -> None:
    """15:40 EOD 回补：TuShare 按日期批量优先（~10 秒），失败降级逐只 + clist 资金流。

    TuShare 可用时一次拉全市场日线/daily_basic/资金流/涨跌停（替代逐只 90 分钟）；
    TuShare 挂或 bars=0 时降级到原 ``_run_screener_bars_incremental`` +
    ``_run_screener_fundflow_today``（逐只 + clist 批量）。
    """
    today = now_provider().date()
    if daily_bars.tushare_gateway is not None:
        try:
            stats = daily_bars.backfill_by_date(session, today)
            if stats.get("bars", 0) > 0:
                logger.info(
                    "screener eod: tushare 批量成功 bars=%d basic=%d flow=%d limit=%d, 跳过逐只",
                    stats["bars"], stats["basic"], stats["flow"], stats["limit"],
                )
                try:
                    daily_bars.prune_old_bars(session)
                    daily_bars.prune_old_fund_flow(session)
                except Exception:  # noqa: BLE001
                    logger.exception("screener eod prune failed")
                _prune_persistence_tables(session)
                return
            logger.warning("screener eod: tushare 批量 bars=0，降级逐只")
        except Exception:  # noqa: BLE001
            logger.exception("screener eod: tushare backfill_by_date 失败，降级逐只")
    # 降级：逐只日线 + 批量资金流（原 15:40 路径）
    _run_screener_bars_incremental(session, daily_bars)
    _run_screener_fundflow_today(session, daily_bars)


def _prune_persistence_tables(session: Session) -> None:
    """对 5 张新表执行 prune_old(keep_days=250)。单表失败不阻塞其他。"""
    from app.services.daily_eod import DailyEodService
    from app.services.indicators_daily import IndicatorsDailyService
    from app.services.limit_up_history import LimitUpHistoryService
    from app.services.limit_up_indicators import LimitUpIndicatorsService
    from app.services.lhb_history import LhbHistoryService

    for svc_cls, name in (
        (DailyEodService, "stock_realtime_eod"),
        (IndicatorsDailyService, "stock_indicators_daily"),
        (LimitUpHistoryService, "stock_limit_up_history"),
        (LimitUpIndicatorsService, "stock_limit_up_indicators"),
        (LhbHistoryService, "stock_lhb_detail"),
    ):
        try:
            deleted = svc_cls().prune_old(session, keep_trading_days=250)
            if deleted:
                logger.info("prune %s: -%d 行", name, deleted)
        except Exception:
            logger.exception("prune %s failed", name)


def _persistence_freshness(session: Session) -> dict[str, dict]:
    """选股器 status 用：5 张关键表的最新日期/行数/当日股票数，直接暴露哪张表断了。

    单表查询失败不阻塞其他（表可能尚未建）。资金流表额外给"最新日股票数"，
    这是 2026-07-22 事故的关键指标（曾出现最新日仅 1 只 -> 选股器全空）。
    """
    from sqlalchemy import text as _text

    specs = [
        ("stock_fund_flow_daily", True),    # 额外查当日股票数
        ("stock_realtime_eod", False),
        ("stock_indicators_daily", False),
        ("stock_limit_up_history", False),
        ("stock_limit_up_indicators", False),
        ("stock_lhb_detail", False),
    ]
    out: dict[str, dict] = {}
    for table, with_day_count in specs:
        try:
            row_count = session.execute(_text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            latest = session.execute(_text(f"SELECT MAX(trading_date) FROM {table}")).scalar()
            entry: dict = {"row_count": int(row_count), "latest_date": str(latest) if latest else None}
            if with_day_count and latest is not None:
                day_count = session.execute(
                    _text(f"SELECT COUNT(DISTINCT stock_code) FROM {table} WHERE trading_date=:d"),
                    {"d": latest},
                ).scalar() or 0
                entry["latest_day_stocks"] = int(day_count)
            out[table] = entry
        except Exception:
            logger.exception("persistence_freshness %s failed", table)
            out[table] = {"row_count": 0, "latest_date": None, "error": True}
    return out


# ---------------- 持久化层 cron workers (2026-07-21) ----------------


def _run_eod_aggregate(session: Session, gateway: Any, now_provider: Callable[[], datetime]) -> None:
    """15:50 — 把 intraday snapshot 聚合到 stock_realtime_eod。"""
    from app.services.daily_eod import DailyEodService
    today = now_provider().date()
    n = DailyEodService(gateway=gateway).aggregate_from_snapshots(session, today)
    logger.info("cron eod-aggregate %s: 写入 %s 行 -> stock_realtime_eod", today, n)


def _run_limit_up_history(session: Session, gateway: Any, now_provider: Callable[[], datetime]) -> None:
    """16:00 — 4 池涨停入库。force=True 跳过时间门（cron 自己就是收盘后）。"""
    from app.services.limit_up_history import LimitUpHistoryService
    today = now_provider().date()
    res = LimitUpHistoryService(gateway=gateway, now_provider=now_provider).refresh_for_date(
        session, today, force=True,
    )
    logger.info("cron limit-up-history %s: %s -> stock_limit_up_history", today, res)


def _run_limit_up_indicators_rebuild(session: Session, now_provider: Callable[[], datetime]) -> None:
    """16:10 — 涨停指标聚合。"""
    from app.services.limit_up_indicators import LimitUpIndicatorsService
    today = now_provider().date()
    n = LimitUpIndicatorsService().rebuild_for_date(session, today)
    logger.info("cron limit-up-indicators %s: 写入 %s 行 -> stock_limit_up_indicators", today, n)


def _run_indicators_daily(session: Session, now_provider: Callable[[], datetime]) -> None:
    """16:30 — bars/fundflow 派生指标快照。"""
    from app.services.indicators_daily import IndicatorsDailyService
    today = now_provider().date()
    res = IndicatorsDailyService(now_provider=now_provider).compute_for_date(session, today)
    logger.info("cron indicators-daily %s: %s -> stock_indicators_daily", today, res)


def _run_lhb_history(session: Session, gateway: Any, now_provider: Callable[[], datetime]) -> None:
    """17:00 - 龙虎榜明细入库（17:00 后出齐）。force=True 跳时间门。"""
    from app.services.lhb_history import LhbHistoryService
    today = now_provider().date()
    n = LhbHistoryService(gateway=gateway, now_provider=now_provider).refresh_for_date(
        session, today, force=True,
    )
    logger.info("cron lhb-history %s: +%d 行 -> stock_lhb_detail", today, n)


def _run_screener_preset_hits(session: Session, screener: Any, now_provider: Callable[[], datetime]) -> None:
    """17:10 - 跑所有预设记录当日命中数（lhb/indicators 已就绪）。"""
    today = now_provider().date()
    res = screener.snapshot_preset_hits(session, today)
    logger.info("cron screener-preset-hits %s: %s -> screener_preset_hits", today, res)


def _run_vacuum(session: Session) -> None:
    """周日 02:17 - VACUUM 回收 prune 后的空闲页。

    注意：VACUUM 会重写整个 DB 文件，期间表级写锁；必须在低峰时段跑。
    """
    from sqlalchemy import text
    try:
        session.execute(text("VACUUM"))
        session.commit()
        logger.info("VACUUM completed")
    except Exception:
        logger.exception("VACUUM failed")


def _maybe_kickoff_screener_backfill(
    session: Session,
    daily_bars: DailyBarsService,
    screener: ScreenerService,
    session_factory: sessionmaker[Session],
) -> None:
    """启动补偿：数据过期则后台线程触发全量回补（同样互斥锁保护）。"""
    from datetime import timedelta
    from datetime import date as _date

    if daily_bars.progress.running:
        return
    coverage = daily_bars.coverage(session)
    latest_date = coverage.get("latest_date")
    today = daily_bars.now_provider().date()
    if not latest_date:
        stale = True
    else:
        try:
            latest_date_obj = _date.fromisoformat(latest_date)
        except Exception:  # noqa: BLE001
            stale = True
        else:
            stale = (today - latest_date_obj) > timedelta(days=5)
    if not stale:
        return
    thread = threading.Thread(
        target=_threaded_full_backfill,
        args=(daily_bars, screener, session_factory),
        daemon=True,
    )
    thread.start()


def _threaded_full_backfill(
    daily_bars: DailyBarsService,
    screener: ScreenerService,
    session_factory: sessionmaker[Session],
) -> None:
    """后台线程跑 backfill_all（不能在主请求线程中跑，避免阻塞启动）。"""
    try:
        with session_factory() as session:
            result = daily_bars.backfill_all(session)
            logger.info("screener startup backfill: %s", result.get("progress", {}).get("message"))
            screener.invalidate_cache()
    except Exception:
        logger.exception("screener startup backfill failed")



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

    # 数据源去代理: 国内 A 股数据源(东财/同花顺/腾讯/新浪)不应该被本地系统代理劫持。
    # 关键事件: 2026-07-20 Clash 关闭时 macOS 系统代理指向 7890 无监听,
    # akshare 全量 ProxyError -> 选股器一只都拉不到; 加 NO_PROXY 让 urllib/requests
    # 直接访问国内站, 不依赖本地代理是否启动。生产 cloudflared 隧道是另一条路, 不受影响。
    _no_proxy_domains = (
        "*"  # 简单粗暴: 这个后端只聊 A 股数据, 全走直连最稳; 若以后接入境外 API 再细化
    )
    os.environ.setdefault("NO_PROXY", _no_proxy_domains)
    os.environ.setdefault("no_proxy", _no_proxy_domains)
    # 同时清掉已存在的 *_PROXY 环境变量, 防止被 NO_PROXY 之外另一处覆盖
    for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy", "ALL_PROXY"):
        os.environ.pop(_k, None)

    # 关键: macOS 上 urllib.request.getproxies() 同时读 env 和系统 scutil 设置,
    # 仅设 NO_PROXY env 不一定能 override 系统代理 -> requests 仍走 7890 死代理。
    # monkey-patch 直接强制 getproxies 返空 dict, 进程内所有 requests/akshare 都看不到代理。
    import urllib.request as _urllib_request

    def _force_no_proxy(*_args, **_kwargs) -> dict[str, str]:
        return {}

    _urllib_request.getproxies = _force_no_proxy
    try:
        import requests.utils as _requests_utils
        _requests_utils.getproxies = _force_no_proxy  # type: ignore[assignment]
    except ImportError:
        pass

    logger.info("NO_PROXY 已生效 (env 清空 + getproxies monkey-patch): 选股器数据源直连, 不依赖 Clash")

    session_factory = session_factory or create_session_factory()
    now_provider = now_provider or datetime.now
    # TuShare 2000 档 EOD 主源 + AKShare 备（盘中实时/涨停池细分/逐只 fallback）。
    # token 未配置或初始化失败时降级纯 AKShare，不影响现有功能。
    tushare_gw: Any = None
    if gateway is None:
        try:
            from app.tushare_client import TushareGateway
            tushare_gw = TushareGateway()
        except Exception:  # noqa: BLE001
            logger.warning("TushareGateway 初始化失败，降级纯 AKShare", exc_info=True)
        akshare_gw = AkshareGateway()
        if tushare_gw is not None:
            from app.gateway_composite import CompositeGateway
            gateway = CompositeGateway(primary=tushare_gw, fallback=akshare_gw)
            logger.info("gateway: CompositeGateway(tushare + akshare)")
        else:
            gateway = akshare_gw
            logger.info("gateway: AkshareGateway（tushare 未配置）")
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
    news_service = NewsService()
    daily_bars = DailyBarsService(gateway=gateway, now_provider=now_provider, tushare_gateway=tushare_gw)
    screener = ScreenerService(daily_bars_service=daily_bars)
    from app.services.backtest import BacktestService
    backtest = BacktestService(screener=screener, now_provider=now_provider)
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
        try:
            screener.seed_builtin_presets(bootstrap_session)
        except OperationalError:
            bootstrap_session.rollback()
            logger.warning("screener builtin presets bootstrap skipped because local database schema is behind")
        # 注意：启动补偿自动回补已禁用。曾在启动时后台跑全量回补（~4000 次网络调用），
        # 长事务与生产写入冲突曾导致 DB 文件被截断为 0 字节。回补改为只由前端
        # 「更新数据」按钮（POST /api/screener/backfill）或 15:40 cron 增量触发，
        # 由用户主动发起，避免启动期长写事务。
        # try:
        #     _maybe_kickoff_screener_backfill(bootstrap_session, daily_bars, screener, session_factory)
        # except OperationalError:
        #     bootstrap_session.rollback()
        #     logger.warning("screener backfill kickoff skipped because local database schema is behind")
        # except Exception:
        #     logger.exception("screener backfill kickoff failed")
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
            # Screener 收盘增量 — 15:40（hx_A 股收盘后约 10 分钟）
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "screener-eod-backfill",
                    session_factory,
                    lambda session: _run_screener_eod_backfill(session, daily_bars, now_provider),
                ),
                "cron",
                minute="40",
                hour="15",
                day_of_week="mon-fri",
                id="screener-eod-backfill",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # === 持久化层 (2026-07-21) ===
            # 15:50 — intraday snapshot → stock_realtime_eod
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "eod-aggregate-realtime-snapshots",
                    session_factory,
                    lambda session: _run_eod_aggregate(session, gateway, now_provider),
                ),
                "cron",
                minute="50",
                hour="15",
                day_of_week="mon-fri",
                id="eod-aggregate-realtime-snapshots",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 16:00 — 4 池涨停入库 → stock_limit_up_history
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "limit-up-history-refresh",
                    session_factory,
                    lambda session: _run_limit_up_history(session, gateway, now_provider),
                ),
                "cron",
                minute="0",
                hour="16",
                day_of_week="mon-fri",
                id="limit-up-history-refresh",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 16:10 — 涨停指标聚合 → stock_limit_up_indicators
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "limit-up-indicators-rebuild",
                    session_factory,
                    lambda session: _run_limit_up_indicators_rebuild(session, now_provider),
                ),
                "cron",
                minute="10",
                hour="16",
                day_of_week="mon-fri",
                id="limit-up-indicators-rebuild",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 16:30 — bars/fundflow 派生指标快照 → stock_indicators_daily
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "indicators-daily-compute",
                    session_factory,
                    lambda session: _run_indicators_daily(session, now_provider),
                ),
                "cron",
                minute="30",
                hour="16",
                day_of_week="mon-fri",
                id="indicators-daily-compute",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 17:00 - 龙虎榜明细 -> stock_lhb_detail（17:00 后出齐）
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "lhb-history-refresh",
                    session_factory,
                    lambda session: _run_lhb_history(session, gateway, now_provider),
                ),
                "cron",
                minute="0",
                hour="17",
                day_of_week="mon-fri",
                id="lhb-history-refresh",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 17:10 - 预设命中快照（lhb 17:00 / indicators 16:30 均已就绪）
            scheduler.add_job(
                lambda: _run_scheduled_job(
                    "screener-preset-hits-snapshot",
                    session_factory,
                    lambda session: _run_screener_preset_hits(session, screener, now_provider),
                ),
                "cron",
                minute="10",
                hour="17",
                day_of_week="mon-fri",
                id="screener-preset-hits-snapshot",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            # 周日 02:17 - VACUUM 压缩 DB（prune 后回收空间）。避开整点减轻并发。
            scheduler.add_job(
                lambda: _run_scheduled_job("vacuum-sunday", session_factory, lambda session: _run_vacuum(session)),
                "cron",
                minute="17",
                hour="2",
                day_of_week="sun",
                id="vacuum-sunday",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=7200,
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
            # 实时资讯轮询 — 每 5 分钟从东财/同花顺/新浪抓取并入库，
            # hour=6-23 夜间停止（消息源也基本静默）。
            # 通过环境变量 EQ_NEWS_FETCH_DISABLED=1 可一键关闭（回滚预案）。
            if not os.environ.get("EQ_NEWS_FETCH_DISABLED"):
                scheduler.add_job(
                    lambda: _run_scheduled_job(
                        "news-realtime-fetch",
                        session_factory,
                        lambda session: news_service.fetch_and_persist(session),
                    ),
                    "cron",
                    minute="*/5",
                    hour="6-23",
                    id="news-realtime-fetch",
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=120,
                )
                scheduler.add_job(
                    lambda: _run_scheduled_job(
                        "news-realtime-fetch-startup",
                        session_factory,
                        lambda session: news_service.fetch_and_persist(session),
                    ),
                    "date",
                    run_date=now_provider(),
                    id="news-realtime-fetch-startup",
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=60,
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
                        try:
                            scheduled_hour = int(cron_kwargs.get("hour", "0"))
                            scheduled_minute = int(cron_kwargs.get("minute", "0"))
                        except ValueError:
                            # 复杂 cron（*/2、8,12 等）无法取单一时刻，跳过 catch-up（P5-1h：
                            # 原 int() ValueError 未捕获会杀掉整个 catch-up 循环）
                            logger.debug("catch-up skip job %s: complex cron %r", catchup_job.name, cron_expr)
                            continue
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
                            run_date=now_cn().replace(tzinfo=None) + timedelta(seconds=5),
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

    @app.get("/news")
    def news_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/review")
    def review_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/ai-jobs")
    def ai_jobs_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/opportunity-pool")
    def opportunity_pool_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/review-center")
    def review_center_page() -> RedirectResponse:
        # Legacy alias — pre-SPA users had bookmarked this. The SPA equivalent
        # now lives at /review (top-level route) but keep this redirect for
        # link compatibility.
        response = RedirectResponse(url="/review")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.get("/workspace")
    def workspace_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/api/page/{page_name}")
    def page_bootstrap(page_name: str, db: Session = Depends(get_db)) -> dict:
        try:
            return page_payloads.get_page_payload(page_name, db)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown page: {page_name}") from exc

    @app.get("/ai-center")
    def ai_center_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/user-mgmt")
    def user_mgmt_page() -> FileResponse:
        return build_spa_shell_response()

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

    @app.get("/api/news/realtime")
    def news_realtime(
        limit: int = Query(default=50, ge=1, le=200),
        hours: int | None = Query(default=48, ge=1, le=168),
        importance: int = Query(default=0, ge=0, le=2),
        sort: str = Query(default="mixed", pattern="^(mixed|latest|important|hot)$"),
        sources: str | None = Query(default=None, description="CSV，如 eastmoney_724,ths_live"),
        industries: str | None = Query(default=None, description="CSV，如 化工,锂电"),
        actions: str | None = Query(default=None, description="CSV，如 涨价,政策"),
        since_id: int | None = Query(default=None, description="加载更多游标：取小于该 id 的条目"),
        db: Session = Depends(get_db),
    ) -> dict:
        """实时资讯流查询接口 — 由前端 RealtimeFeed.vue 调用，每 60s 自动刷新。"""

        def _split_csv(value: str | None) -> list[str] | None:
            if not value:
                return None
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts or None

        return news_service.list_recent_news(
            db,
            limit=limit,
            hours=hours,
            importance_min=importance,
            sources=_split_csv(sources),
            industries=_split_csv(industries),
            actions=_split_csv(actions),
            since_id=since_id,
            sort=sort,
        )

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

    # ── Job Toggle Endpoints ───────────────────────────────────────────

    @app.post("/api/ai/jobs/{job_id}/execute")
    def ai_execute_job_now(job_id: int) -> dict:
        """Manually trigger an AI Job execution outside its cron schedule.

        The work is dispatched to a background thread (the same path the
        scheduler uses), so this endpoint returns immediately with status
        `dispatched`. The caller polls `/api/ai/jobs` or `/api/ai/runs` to
        observe completion.
        """

        import threading

        from app.models import AiJob as AiJobModel

        with session_factory() as probe_session:
            job = probe_session.get(AiJobModel, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            if not job.enabled:
                raise HTTPException(status_code=400, detail="job is disabled")
            job_snapshot = {"id": job.id, "name": job.name}

        def _run() -> None:
            try:
                _execute_ai_skill_job(job_id, session_factory, ai_center, now_provider)
            except Exception:  # noqa: BLE001
                logger.exception("manual execute of ai job %d failed", job_id)

        threading.Thread(target=_run, name=f"ai-manual-{job_id}", daemon=True).start()

        return {
            "status": "dispatched",
            "job_id": job_snapshot["id"],
            "job_name": job_snapshot["name"],
            "dispatched_at": now_provider().isoformat(),
        }

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

    @app.post("/api/ai/skill-chat", response_model=None)
    def ai_skill_chat(request: Request, payload: dict = Body(default={})):
        """AI Skill 对话入口 - 默认走 SSE 流式；?stream=false 走旧 JSON 回退"""
        message = payload.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        history = payload.get("history", [])

        # stream 决策：query 优先，其次 body 字段，最后默认 True
        stream_q = request.query_params.get("stream", "true").lower()
        stream = stream_q not in ("false", "0", "no")
        if isinstance(payload.get("stream"), bool):
            stream = payload["stream"]

        cli_prompt = _build_skill_chat_prompt(history, message)

        claude_path = _find_cli_path("claude")

        # ── 分支 A：?stream=false → 旧 JSON 回退 ────────────────────────
        if not stream:
            import time as _time
            start = _time.time()
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
                duration_ms = int((_time.time() - start) * 1000)
                if proc.returncode != 0:
                    logger.error("skill-chat (non-stream) exit=%d stderr=%s", proc.returncode, proc.stderr[:500])
                    return {
                        "response": f"执行出错: {proc.stderr[:500]}",
                        "skill_draft": None,
                        "duration_ms": duration_ms,
                    }
                return {
                    "response": proc.stdout,
                    "skill_draft": _extract_skill_draft(proc.stdout),
                    "duration_ms": duration_ms,
                }
            except subprocess.TimeoutExpired:
                return {
                    "response": "请求超时，请重试或简化需求描述。",
                    "skill_draft": None,
                    "duration_ms": 120000,
                }

        # ── 分支 B：SSE 流式（默认） ─────────────────────────────────
        if not claude_path:
            def _cli_missing_gen():
                yield _skill_chat_event({"type": "error", "message": "Claude Code CLI 未找到，请检查安装。"})
                yield _skill_chat_event({
                    "type": "done",
                    "response": "Claude Code CLI 未找到，请检查安装。",
                    "skill_draft": None,
                    "duration_ms": 0,
                })
            return StreamingResponse(
                _cli_missing_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
            )

        return StreamingResponse(
            _skill_chat_stream_generator(claude_path, cli_prompt),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

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

    # ── Screener 路由 ────────────────────────────────────────

    @app.get("/screener")
    def screener_page() -> FileResponse:
        return build_spa_shell_response()

    @app.get("/api/screener/indicators")
    def api_screener_indicators():
        return screener.indicators_payload()

    @app.get("/api/screener/presets")
    def api_screener_presets(session: Session = Depends(get_db)):
        return screener.list_presets(session)

    @app.get("/api/screener/presets/{preset_id}")
    def api_screener_get_preset(preset_id: int, session: Session = Depends(get_db)):
        row = screener.get_preset(session, preset_id)
        if row is None:
            raise HTTPException(status_code=404, detail="preset not found")
        return row

    @app.post("/api/screener/presets")
    def api_screener_save_preset(payload: dict = Body(default={}), session: Session = Depends(get_db)):
        try:
            row = screener.save_preset(
                session,
                name=str(payload.get("name") or "").strip(),
                description=payload.get("description"),
                conditions=list(payload.get("conditions") or []),
                universe=dict(payload.get("universe") or {}),
                order_by=payload.get("order_by"),
                order=str(payload.get("order") or "desc"),
                category=str(payload.get("category") or "量价突破"),
                match_mode=str(payload.get("match_mode") or "all"),
                min_score=int(payload.get("min_score") or 0),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        if not row["name"]:
            raise HTTPException(status_code=400, detail="name is required")
        return row

    @app.delete("/api/screener/presets/{preset_id}")
    def api_screener_delete_preset(preset_id: int, session: Session = Depends(get_db)):
        try:
            ok = screener.delete_preset(session, preset_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        if not ok:
            raise HTTPException(status_code=404, detail="preset not found")
        return {"deleted": True}

    @app.post("/api/screener/run")
    def api_screener_run(payload: dict = Body(default={}), session: Session = Depends(get_db)):
        try:
            return screener.run(session, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/screener/strategies")
    def api_screener_strategies(session: Session = Depends(get_db)):
        """策略商城目录：preset 列表 + 近 5 日命中数 + T+N 胜率（P1-4）。"""
        catalog = screener.strategies_catalog(session)
        for c in catalog:
            c["win_rates"] = backtest.latest_win_rates(session, c["id"])
        return catalog

    @app.get("/api/screener/stocks/{code}")
    def api_screener_stock_detail(code: str, session: Session = Depends(get_db)):
        """个股抽屉详情：60 日 K 线 + 龙虎榜 + 关键指标 + 近期资金流。"""
        detail = screener.stock_detail(session, code)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"无 {code} 日线数据")
        return detail

    @app.get("/api/screener/status")
    def api_screener_status(session: Session = Depends(get_db)):
        coverage = daily_bars.coverage(session)
        # universe 规模仅在缓存存在时返回（不主动触发网络拉取，避免高频轮询拖慢状态接口）
        universe_size = 0
        if coverage.get("latest_date"):
            try:
                snapshot_universe = daily_bars.get_universe(
                    session, min_amount=50_000_000.0, realtime_amounts=None
                )
                universe_size = int(len(snapshot_universe))
            except Exception:
                universe_size = 0
        coverage = {
            **coverage,
            "universe_size": universe_size,
            "coverage_pct": round(
                min(coverage.get("stock_count", 0), coverage.get("flow_stock_count", 0))
                / universe_size
                * 100,
                1,
            ) if universe_size else 0.0,
        }
        # 缓存新鲜度
        now = now_cn()
        bar_max = coverage.get("latest_date")
        try:
            bar_max_dt = datetime.fromisoformat(bar_max) if bar_max else None
        except Exception:
            bar_max_dt = None
        # bar_max_dt 来自 DB（naive），now_cn 是 tz-aware → 统一为 naive 比较
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now
        cache_age_minutes = (
            int((now_naive - bar_max_dt).total_seconds() // 60) if bar_max_dt else None
        )
        is_stale = (
            cache_age_minutes is None
            or cache_age_minutes > 24 * 60
            or (bar_max_dt and bar_max_dt.date() < now_naive.date() and is_trading_day(now))
        )
        cache = {
            "bar_max_date": bar_max,
            "flow_max_date": coverage.get("flow_latest_date"),
            "cache_age_minutes": cache_age_minutes,
            "is_stale": is_stale,
            "is_trading_day": is_trading_day(now),
        }
        # 数据源标签（来自 akshare_client 最近的 snapshot）
        try:
            source = gateway.get_source_snapshot("stock_fund_flow_history")
        except Exception:
            source = {"source_label": "akshare"}
        # 持久化层各表新鲜度（2026-07-22 选股器重构）：直接暴露哪张表断了
        persistence = _persistence_freshness(session)
        return {
            "coverage": coverage,
            "cache": cache,
            "source": {
                "fund_flow": source.get("source_label"),
                "fallback_used": bool(source.get("fallback_used")),
            },
            "persistence": persistence,
            "progress": daily_bars._snapshot(),  # noqa: SLF001 (内部诊断)
        }

    @app.post("/api/screener/backfill")
    def api_screener_backfill(payload: dict = Body(default={})):
        code_limit = payload.get("code_limit")
        if code_limit is not None:
            try:
                code_limit = max(0, int(code_limit))
            except (TypeError, ValueError):
                code_limit = None
        # run_async=True: POST 立即返回 {started, job_id}，worker 在 daemon 线程中跑。
        # 避免 Cloudflare tunnel 100s 读超时切断仍在跑的同步请求（524 根因）。
        # worker 必须自建 Session — 不能复用 request 的 Depends session。
        result = daily_bars.backfill_all(
            session_or_factory=session_factory,
            min_amount=float(payload.get("min_amount", 50_000_000.0)),
            code_limit=code_limit,
            run_async=True,
        )
        if result.get("started"):
            screener.invalidate_cache()
        return result

    @app.post("/api/screener/backtest")
    def api_screener_backtest(payload: dict = Body(...)):
        """触发策略信号统计回测（P1-4）：对最近 N 日执行策略算 T+N 胜率。

        Body: {"preset_id": int, "days": int=30}。后台 daemon 线程跑（30日×run 慢），
        立即返回 {started, job_id}，避免 Cloudflare 100s 超时。完成后 GET /strategies 查 win_rates。
        """
        try:
            preset_id = int(payload.get("preset_id"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="preset_id 必填")
        days = int(payload.get("days") or 30)
        job_id = f"bt-{int(time.time())}"

        def _worker() -> None:
            try:
                with session_factory() as s:
                    backtest.run_backtest(s, preset_id, days=days)
            except Exception:  # noqa: BLE001
                logger.exception("backtest job %s crashed", job_id)

        t = threading.Thread(target=_worker, name=f"screener-backtest-{job_id}", daemon=True)
        t.start()
        return {"started": True, "job_id": job_id, "preset_id": preset_id, "days": days}

    # ===== 持久化层 (2026-07-21) =====
    # 手动回补 stock_realtime_eod / stock_indicators_daily / stock_limit_up_history
    @app.post("/api/screener/data-backfill")
    def api_screener_data_backfill(payload: dict = Body(...)):
        """手动触发持久化层回补。

        Body: {"task": "eod"|"indicators"|"limit_up"|"limit_up_indicators"|"lhb",
               "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        """
        from datetime import date as _date
        task = (payload.get("task") or "").strip()
        if task not in {"eod", "indicators", "limit_up", "limit_up_indicators", "lhb"}:
            raise HTTPException(
                status_code=400,
                detail=f"task 必须为 eod/indicators/limit_up/limit_up_indicators/lhb 之一, got {task!r}",
            )
        try:
            start = _date.fromisoformat(payload["start_date"])
            end = _date.fromisoformat(payload["end_date"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"start_date/end_date 格式错误: {exc}") from exc
        if start > end:
            start, end = end, start

        job_id = uuid.uuid4().hex[:12]

        def _worker() -> None:
            session = session_factory()
            try:
                if task == "eod":
                    from app.services.daily_eod import DailyEodService
                    DailyEodService().backfill_range(session, start, end)
                elif task == "indicators":
                    from app.services.indicators_daily import IndicatorsDailyService
                    IndicatorsDailyService().backfill_range(session, start, end)
                elif task == "limit_up":
                    from app.services.limit_up_history import LimitUpHistoryService
                    LimitUpHistoryService(gateway=gateway).backfill_range(session, start, end)
                elif task == "limit_up_indicators":
                    from app.services.limit_up_indicators import LimitUpIndicatorsService
                    LimitUpIndicatorsService().backfill_range(session, start, end)
                elif task == "lhb":
                    from app.services.lhb_history import LhbHistoryService
                    LhbHistoryService(gateway=gateway).backfill_range(session, start, end)
                screener.invalidate_cache()
            except Exception as exc:  # noqa: BLE001
                logger.exception("data-backfill worker failed: task=%s job_id=%s", task, job_id)
            finally:
                session.close()

        threading.Thread(target=_worker, name=f"data-backfill-{task}-{job_id}", daemon=True).start()
        return {"started": True, "job_id": job_id, "task": task,
                "start_date": start.isoformat(), "end_date": end.isoformat()}

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

            # Patch output files: ensure skill_name/job_name match DB skill name for import
            if result.output_files and skill.name:
                for fpath in result.output_files:
                    try:
                        from pathlib import Path as P
                        p = P(fpath)
                        payload = json.loads(p.read_text(encoding="utf-8"))
                        patched = False
                        if payload.get("skill_name") != skill.name:
                            payload["skill_name"] = skill.name
                            patched = True
                        if payload.get("job_name") != skill.name:
                            payload["job_name"] = skill.name
                            patched = True
                        if patched:
                            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                            logger.info("Patched %s: skill_name/job_name → %s", p.name, skill.name)
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
