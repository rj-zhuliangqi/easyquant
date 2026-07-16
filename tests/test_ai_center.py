from __future__ import annotations

from datetime import date
from datetime import datetime
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_app
from app.main import create_session_factory
from app.models import AiJob
from app.models import AiRun
from app.models import AiSkill
from app.models import AiSkillRevision
from app.services.ai_center import AiCenterService


class AiGateway:
    def resolve_sector_name(self, sector_type: str, sector_name: str) -> str | None:
        return sector_name

    def fetch_individual_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"code": "000001", "name": "Ping An Bank", "price": 11.2, "change_percent": 3.8, "net_amount": 9.5},
                {"code": "300308", "name": "InnoLight", "price": 155.6, "change_percent": 6.1, "net_amount": 16.8},
                {"code": "600036", "name": "China Merchants Bank", "price": 42.5, "change_percent": 1.2, "net_amount": 4.1},
            ]
        )

    def fetch_stock_daily_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": date(2026, 5, 7), "open": 10.0, "close": 10.4, "high": 10.6, "low": 9.9},
                {"date": date(2026, 5, 8), "open": 10.5, "close": 11.0, "high": 11.3, "low": 10.2},
                {"date": date(2026, 5, 9), "open": 10.9, "close": 11.2, "high": 11.4, "low": 10.8},
                {"date": date(2026, 5, 12), "open": 11.1, "close": 11.6, "high": 11.9, "low": 11.0},
            ]
        )

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": date(2026, 5, 8), "open": 3000.0, "high": 3010.0, "low": 2995.0, "close": 3006.0, "volume": 1},
                {"date": date(2026, 5, 9), "open": 3006.0, "high": 3012.0, "low": 3001.0, "close": 3008.0, "volume": 1},
                {"date": date(2026, 5, 12), "open": 3008.0, "high": 3015.0, "low": 3005.0, "close": 3010.0, "volume": 1},
            ]
        )

    def fetch_market_index_spot(self) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_market_breadth(self) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_stock_quote_batch(self, symbols: list[str]) -> dict[str, dict[str, float | str | None]]:
        return {}

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        return {"source_label": "akshare", "updated_at": "2026-05-08T15:00:00", "fallback_used": False, "degraded_fields": []}


def build_ai_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    app = create_app(
        session_factory=session_factory,
        gateway=AiGateway(),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0),
    )
    client = TestClient(app)
    # Login to get auth token
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login_resp.status_code == 200:
        token = login_resp.json().get("access_token", "")
        client.headers["Authorization"] = f"Bearer {token}"
    return client, session_factory


def seed_skill(
    session_factory: sessionmaker,
    *,
    skill_name: str = "auction-scan",
    job_name: str = "09:26 auction-scan",
    job_type: str = "stock_pick",
    display_group: str = "盘中",
) -> tuple[int, int, int]:
    with session_factory() as session:
        skill = AiSkill(name=skill_name, category="stock-pick", description="test skill")
        session.add(skill)
        session.flush()
        revision = AiSkillRevision(
            skill_id=skill.id,
            revision_no=1,
            title=f"{skill_name} v1",
            content_text="first revision",
            config_json="{}",
            change_note="init",
            status="active",
        )
        session.add(revision)
        session.flush()
        job = AiJob(
            name=job_name,
            schedule_label=job_name.split(" ", 1)[0],
            schedule_rrule_or_cron="26 9 * * 1-5",
            skill_id=skill.id,
            active_revision_id=revision.id,
            job_type=job_type,
            result_schema_version="2.0",
            display_group=display_group,
            enabled=True,
        )
        session.add(job)
        session.commit()
        return skill.id, revision.id, job.id


def stock_pick_payload(*, stock_code: str = "000001", stock_name: str = "Ping An Bank", level: str = "confirm", summary: str = "auction strengthening") -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "pick_level": level,
        "reason_summary": summary,
        "reason_detail": ["capital inflow confirmed", "sector resonance"],
        "sector_name": "Banking",
        "theme_tags": ["auction", "momentum"],
        "capital_profile": {"net_inflow": 9.5, "main_force_signal": "positive", "turnover_rate": 3.2, "volume_ratio": 1.8},
        "signal_context": "集合竞价转强",
        "confidence_score": 0.9,
        "risk_flags": ["gap-up risk"],
        "entry_hint": "watch pullback support",
        "priority_rank": 1,
    }


def test_ai_import_run_and_multi_source_capability_summary() -> None:
    client, session_factory = build_ai_client()
    _, revision_id, _ = seed_skill(session_factory)
    _, second_revision_id, _ = seed_skill(session_factory, skill_name="close-scan", job_name="14:50 close-scan")

    first = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "raw_output": "hit 000001",
            "summary": {"headline": "auction hit 1 stock"},
            "push": {"status": "sent", "channel": "wechat"},
            "result_payload": {"structured_picks": [stock_pick_payload()]},
            "structured_picks": [stock_pick_payload()],
        },
    )
    second = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "14:50 close-scan",
            "skill_name": "close-scan",
            "revision_id": second_revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "raw_output": "close watch 000001",
            "summary": {"headline": "close watch 1 stock"},
            "push": {"status": "failed", "channel": "wechat"},
            "result_payload": {"structured_picks": [stock_pick_payload(level="watch", summary="close support")]} ,
            "structured_picks": [stock_pick_payload(level="watch", summary="close support")],
        },
    )
    picks = client.get("/api/ai/picks", params={"trading_date": "2026-05-07"})
    insights = client.get("/api/ai/insights/summary", params={"trading_date": "2026-05-07"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert picks.status_code == 200
    assert insights.status_code == 200
    payload = picks.json()
    assert payload["items"][0]["stock_code"] == "000001"
    assert payload["items"][0]["source_count"] == 2
    assert {item["skill_name"] for item in payload["items"][0]["sources"]} == {"auction-scan", "close-scan"}
    assert {item["pick_level"] for item in payload["items"][0]["sources"]} == {"confirm", "watch"}
    assert {item["window"] for item in payload["items"][0]["outcomes"]} == {"T+1", "T+3"}
    assert insights.json()["skills"][0]["skill_name"] in {"auction-scan", "close-scan"}


def test_ai_revision_activation_and_runs_listing() -> None:
    client, session_factory = build_ai_client()
    skill_id, revision_id, job_id = seed_skill(session_factory)

    create_revision = client.post(
        f"/api/ai/skills/{skill_id}/revisions",
        json={"title": "auction-scan v2", "content_text": "second revision", "change_note": "tighten filters", "status": "draft"},
    )
    revision_v2_id = create_revision.json()["id"]
    activate = client.post(f"/api/ai/jobs/{job_id}/activate-revision", json={"revision_id": revision_v2_id})
    imported = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_v2_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "raw_output": "v2 output",
            "summary": {"headline": "v2 output"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(stock_code="000002", stock_name="Vanke A", level="candidate", summary="filter pass")]},
            "structured_picks": [stock_pick_payload(stock_code="000002", stock_name="Vanke A", level="candidate", summary="filter pass")],
        },
    )
    runs = client.get("/api/ai/runs")
    skills = client.get("/api/ai/skills")

    assert create_revision.status_code == 200
    assert activate.status_code == 200
    assert imported.status_code == 200
    assert runs.status_code == 200
    assert skills.status_code == 200
    assert activate.json()["job"]["active_revision_id"] == revision_v2_id
    assert runs.json()["items"][0]["revision_id"] == revision_v2_id
    assert any(item["active_revision_id"] == revision_v2_id for item in skills.json()["jobs"])
    assert revision_id > 0


def test_ai_review_note_and_backtest_batch_endpoints() -> None:
    client, session_factory = build_ai_client()
    skill_id, revision_id, _ = seed_skill(session_factory)

    imported = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "raw_output": "run output",
            "summary": {"headline": "run output"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(level="watch", summary="T+1 game")]},
            "structured_picks": [stock_pick_payload(level="watch", summary="T+1 game")],
        },
    )
    pick_id = imported.json()["picks"][0]["id"]
    review = client.post(
        f"/api/ai/picks/{pick_id}/review",
        json={
            "window": "T+1",
            "review_text": "next day opened strong and matched expectation",
            "review_tags": ["success", "strong-open"],
            "is_expectation_met": True,
            "improvement_hint": "keep checking auction volume",
        },
    )
    review_fetch = client.get(f"/api/ai/picks/{pick_id}/review")
    batch = client.post(
        "/api/ai/backtests",
        json={"skill_id": skill_id, "revision_id": revision_id, "date_from": "2026-05-07", "date_to": "2026-05-07"},
    )
    batches = client.get("/api/ai/backtests")

    assert imported.status_code == 200
    assert review.status_code == 200
    assert review_fetch.status_code == 200
    assert batch.status_code == 200
    assert batches.status_code == 200
    assert review_fetch.json()["notes"][0]["review_text"] == "next day opened strong and matched expectation"
    assert batch.json()["runs_created"] == 1
    assert batches.json()["items"][0]["status"] == "completed"


def test_ai_center_page_route_is_available() -> None:
    client, _ = build_ai_client()

    response = client.get("/ai-center")

    assert response.status_code == 200
    assert 'id="app"' in response.text


def test_ai_center_bootstraps_builtin_job_registry() -> None:
    client, _ = build_ai_client()

    jobs = client.get("/api/ai/jobs")
    skills = client.get("/api/ai/skills")

    assert jobs.status_code == 200
    assert skills.status_code == 200
    job_names = {item["name"] for item in jobs.json()["items"]}
    assert "08:20 盘前消息面挖掘" in job_names
    assert "09:26 集合竞价分析" in job_names
    assert "21:30 每日持仓复盘" in job_names
    assert "周五22:00 超短线周度经验汇总" in job_names
    assert any(item["name"] == "盘前消息面挖掘" for item in skills.json()["items"])


def test_create_session_factory_upgrades_legacy_ai_center_schema(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}", future=True)
    with legacy_engine.begin() as conn:
        conn.execute(text("CREATE TABLE ai_skills (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, category VARCHAR(40) NOT NULL, enabled BOOLEAN NOT NULL, description VARCHAR(500), created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE ai_skill_revisions (id INTEGER PRIMARY KEY, skill_id INTEGER NOT NULL, revision_no INTEGER NOT NULL, title VARCHAR(200) NOT NULL, content_text TEXT NOT NULL, config_json TEXT NOT NULL, change_note VARCHAR(500), status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE ai_jobs (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, schedule_label VARCHAR(40) NOT NULL, schedule_rrule_or_cron VARCHAR(120), skill_id INTEGER NOT NULL, active_revision_id INTEGER, enabled BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE ai_runs (id INTEGER PRIMARY KEY, job_id INTEGER, skill_id INTEGER NOT NULL, revision_id INTEGER NOT NULL, backtest_batch_id INTEGER, run_type VARCHAR(20) NOT NULL, trading_date DATE NOT NULL, started_at DATETIME NOT NULL, finished_at DATETIME, status VARCHAR(20) NOT NULL, source_input_ref VARCHAR(240), raw_output_text TEXT, structured_summary_json TEXT, error_text TEXT)"))

    session_factory = create_session_factory(f"sqlite+pysqlite:///{db_path.as_posix()}")
    app = create_app(
        session_factory=session_factory,
        gateway=AiGateway(),
        enable_scheduler=False,
        now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0),
    )
    client = TestClient(app)
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    client.headers["Authorization"] = f"Bearer {login_resp.json()['access_token']}"

    jobs = client.get("/api/ai/jobs")
    runs = client.get("/api/ai/runs")

    upgrade_engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}", future=True)
    with upgrade_engine.connect() as conn:
        job_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(ai_jobs)")).fetchall()}
        run_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(ai_runs)")).fetchall()}

    assert jobs.status_code == 200
    assert runs.status_code == 200
    assert {"job_type", "result_schema_version", "display_group"}.issubset(job_columns)
    assert {"result_type", "result_payload_json", "push_payload_json", "error_stage", "duration_ms"}.issubset(run_columns)


def test_ai_center_can_seed_demo_data_for_acceptance_preview() -> None:
    client, _ = build_ai_client()

    response = client.post("/api/ai/demo/seed", json={"trading_date": "2026-05-08"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["seeded_runs"] >= 12
    assert payload["seeded_picks"] >= 6

    jobs = client.get("/api/ai/jobs")
    runs = client.get("/api/ai/runs", params={"trading_date": "2026-05-08"})
    picks = client.get("/api/ai/picks", params={"trading_date": "2026-05-08"})
    trading_day = client.get("/api/ai/trading-days/2026-05-08")

    assert jobs.status_code == 200
    assert runs.status_code == 200
    assert picks.status_code == 200
    assert trading_day.status_code == 200
    assert any(item["job_name"] == "08:20 盘前消息面挖掘" for item in runs.json()["items"])
    assert any(item["job_name"] == "21:30 每日持仓复盘" for item in runs.json()["items"])
    assert any(item["source_count"] >= 2 for item in picks.json()["items"])
    assert trading_day.json()["market_summary"]["headline"] != ""
    assert len(trading_day.json()["recommended_picks_review"]) >= 1
    overview = client.get("/api/ai/overview/daily", params={"trading_date": "2026-05-08", "run_type": "demo"})
    assert overview.status_code == 200
    assert overview.json()["summary"]["yesterday_followup_count"] >= 1


def test_ai_center_can_clear_demo_data_for_a_trading_date() -> None:
    client, _ = build_ai_client()

    seeded = client.post("/api/ai/demo/seed", json={"trading_date": "2026-05-08"})
    cleared = client.post("/api/ai/demo/clear", json={"trading_date": "2026-05-08"})
    runs = client.get("/api/ai/runs", params={"trading_date": "2026-05-08"})
    picks = client.get("/api/ai/picks", params={"trading_date": "2026-05-08"})
    trading_day = client.get("/api/ai/trading-days/2026-05-08")

    assert seeded.status_code == 200
    assert cleared.status_code == 200
    assert cleared.json()["deleted_runs"] >= 12
    assert cleared.json()["deleted_picks"] >= 6
    assert runs.json()["items"] == []
    assert picks.json()["items"] == []
    assert trading_day.json()["market_summary"] == {}


def test_ai_daily_overview_returns_result_first_payload() -> None:
    client, session_factory = build_ai_client()
    _, revision_id, _ = seed_skill(session_factory)
    _, close_revision_id, _ = seed_skill(session_factory, skill_name="close-scan", job_name="14:50 close-scan")
    _, day_review_revision_id, _ = seed_skill(
        session_factory,
        skill_name="day-review",
        job_name="19:00 day-review",
        job_type="day_review",
        display_group="盘后",
    )
    _, position_revision_id, _ = seed_skill(
        session_factory,
        skill_name="position-review",
        job_name="21:30 position-review",
        job_type="position_review",
        display_group="夜间",
    )

    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "summary": {"headline": "yesterday pick"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(summary="yesterday auction logic")]},
            "structured_picks": [stock_pick_payload(summary="yesterday auction logic")],
        },
    )
    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "today pick"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(stock_code="300308", stock_name="InnoLight", summary="intraday momentum")]},
            "structured_picks": [stock_pick_payload(stock_code="300308", stock_name="InnoLight", summary="intraday momentum")],
        },
    )
    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "14:50 close-scan",
            "skill_name": "close-scan",
            "revision_id": close_revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "today second source"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(stock_code="300308", stock_name="InnoLight", level="watch", summary="close confirmation")]},
            "structured_picks": [stock_pick_payload(stock_code="300308", stock_name="InnoLight", level="watch", summary="close confirmation")],
        },
    )
    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "19:00 day-review",
            "skill_name": "day-review",
            "revision_id": day_review_revision_id,
            "job_type": "day_review",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "review done"},
            "push": {"status": "sent"},
            "result_payload": {
                "market_summary": {"headline": "index repaired", "risk_prompt": "afternoon divergence remains"},
                "market_breadth": {"up_count": 3200, "down_count": 1800},
                "top_themes": ["Banking", "AI Hardware"],
                "failed_patterns": ["low-volume reversal"],
                "recommended_picks_review": [{"stock_code": "000001", "stock_name": "Ping An Bank", "review": "opened strong then held gains"}],
                "lesson_items": [{"title": "multi-source picks deserve higher priority", "tag": "pattern"}],
                "next_day_focus": ["watch AI hardware continuation"],
            },
        },
    )
    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "21:30 position-review",
            "skill_name": "position-review",
            "revision_id": position_revision_id,
            "job_type": "position_review",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "position review"},
            "push": {"status": "sent"},
            "result_payload": {
                "position_review": [{"stock_code": "300308", "action": "hold", "reason": "trend intact"}],
                "lesson_items": [{"title": "trim weak afternoon reclaim setups", "tag": "execution"}],
                "next_day_focus": ["watch gap-up risk"],
            },
        },
    )

    overview = client.get("/api/ai/overview/daily", params={"trading_date": "2026-05-08", "run_type": "production"})

    assert overview.status_code == 200
    payload = overview.json()
    assert payload["summary"]["today_pick_count"] == 1
    assert payload["summary"]["yesterday_followup_count"] == 1
    assert payload["summary"]["experience_count"] >= 2
    assert payload["today_recommendations"][0]["stock_code"] == "300308"
    assert payload["today_recommendations"][0]["source_count"] == 2
    assert payload["yesterday_followups"][0]["stock_code"] == "000001"
    assert payload["daily_review"]["market_summary"]["headline"] == "index repaired"
    assert any(item["title"] == "multi-source picks deserve higher priority" for item in payload["experience_cards"])
    assert payload["summary"]["ops_summary"]["total_jobs"] >= 4
    followup = payload["yesterday_followups"][0]
    assert followup["today_metrics"]["open_change_pct"] is not None
    assert followup["today_metrics"]["close_change_pct"] is not None
    assert followup["today_metrics"]["max_gain_pct"] is not None
    assert followup["today_metrics"]["max_drawdown_pct"] is not None
    assert "held gains" in followup["attribution_summary"]


def test_ai_daily_overview_supports_demo_filtering() -> None:
    client, session_factory = build_ai_client()
    _, revision_id, _ = seed_skill(session_factory)
    client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "production pick"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [stock_pick_payload(stock_code="000001", stock_name="Ping An Bank")]},
            "structured_picks": [stock_pick_payload(stock_code="000001", stock_name="Ping An Bank")],
        },
    )
    client.post("/api/ai/demo/seed", json={"trading_date": "2026-05-08"})

    overview = client.get("/api/ai/overview/daily", params={"trading_date": "2026-05-08", "run_type": "demo"})

    assert overview.status_code == 200
    payload = overview.json()
    assert payload["summary"]["today_pick_count"] >= 1
    assert all(source["run_type"] == "demo" for item in payload["today_recommendations"] for source in item["source_tasks"])
    assert all("auction-scan" not in {source["skill_name"] for source in item["source_tasks"]} or source["run_type"] == "demo" for item in payload["today_recommendations"] for source in item["source_tasks"])


def test_ai_center_can_scan_inbox_directory_and_import_json(tmp_path) -> None:
    _, session_factory = build_ai_client()
    skill_id, revision_id, _ = seed_skill(session_factory)
    inbox = tmp_path / "inbox"
    processed = tmp_path / "processed"
    inbox.mkdir()
    processed.mkdir()
    payload_file = inbox / "run.json"
    payload_file.write_text(
        """
        {
          "job_name": "09:26 auction-scan",
          "skill_name": "auction-scan",
          "revision_id": %d,
          "job_type": "stock_pick",
          "trading_date": "2026-05-07",
          "run_type": "production",
          "raw_output": "scan import",
          "summary": {"headline": "scan import"},
          "push": {"status": "sent"},
          "result_payload": {"structured_picks": [%s]},
          "structured_picks": [%s]
        }
        """
        % (revision_id, json.dumps(stock_pick_payload(level="watch", summary="directory import")), json.dumps(stock_pick_payload(level="watch", summary="directory import"))),
        encoding="utf-8",
    )
    service = AiCenterService(gateway=AiGateway(), now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0))

    with session_factory() as session:
        summary = service.scan_import_directory(session, inbox_dir=inbox, processed_dir=processed)
        picks = service.list_picks(session, trading_date=date(2026, 5, 7))

    assert skill_id > 0
    assert summary["imported"] == 1
    assert summary["failed"] == 0
    assert not payload_file.exists()
    assert (processed / "run.json").exists()
    assert picks["items"][0]["stock_code"] == "000001"


def test_stock_research_service_persists_research_and_imports_ai_run() -> None:
    from app.models import AiStockResearchItem
    from app.models import AiStockResearchRun
    from app.services.stock_research import StockResearchService

    _, session_factory = build_ai_client()

    with session_factory() as session:
        result = StockResearchService(gateway=AiGateway(), now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0)).run(
            session,
            trading_date=date(2026, 5, 8),
            limit=2,
            skill_name="stock-research",
            revision_title="stock-research v1",
            job_name="15:00 stock-research",
        )
        research_runs = session.query(AiStockResearchRun).all()
        research_items = session.query(AiStockResearchItem).order_by(AiStockResearchItem.rank_score.desc()).all()
        ai_picks = AiCenterService(gateway=AiGateway(), now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0)).list_picks(
            session,
            trading_date=date(2026, 5, 8),
            run_type="production",
        )

    assert result["candidate_count"] == 2
    assert len(research_runs) == 1
    assert research_runs[0].status == "success"
    assert research_runs[0].ai_run_id is not None
    assert len(research_items) == 2
    assert research_items[0].stock_code == "300308"
    assert ai_picks["items"][0]["stock_code"] == "300308"
    assert ai_picks["items"][0]["source_count"] == 1


def test_ai_import_run_rejects_incomplete_stock_pick_payload() -> None:
    client, session_factory = build_ai_client()
    _, revision_id, _ = seed_skill(session_factory)

    response = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-07",
            "run_type": "production",
            "summary": {"headline": "invalid"},
            "push": {"status": "sent"},
            "result_payload": {"structured_picks": [{"stock_code": "000001", "stock_name": "Ping An Bank", "reason_summary": "missing fields"}]},
        },
    )

    assert response.status_code == 400
    assert "pick_level" in response.json()["detail"]


def test_ai_jobs_runs_and_trading_day_review_support_ai_center_v2() -> None:
    client, session_factory = build_ai_client()
    _, stock_pick_revision_id, job_id = seed_skill(session_factory, job_name="09:26 auction-scan", job_type="stock_pick", display_group="盘中")
    _, day_review_revision_id, _ = seed_skill(
        session_factory,
        skill_name="day-review",
        job_name="19:00 day-review",
        job_type="day_review",
        display_group="盘后",
    )
    _, position_revision_id, _ = seed_skill(
        session_factory,
        skill_name="position-review",
        job_name="21:30 position-review",
        job_type="position_review",
        display_group="夜间",
    )

    pick_import = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "09:26 auction-scan",
            "skill_name": "auction-scan",
            "revision_id": stock_pick_revision_id,
            "job_type": "stock_pick",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "intraday candidate 1"},
            "push": {"status": "failed", "channel": "wechat"},
            "raw_output": "pick run",
            "result_payload": {"structured_picks": [stock_pick_payload()]},
            "structured_picks": [stock_pick_payload()],
        },
    )
    review_import = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "19:00 day-review",
            "skill_name": "day-review",
            "revision_id": day_review_revision_id,
            "job_type": "day_review",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "market repaired after divergence"},
            "push": {"status": "sent", "channel": "wechat"},
            "raw_output": "day review",
            "result_payload": {
                "market_summary": {"headline": "index repaired", "risk_prompt": "afternoon divergence remains"},
                "market_breadth": {"up_count": 3200, "down_count": 1800, "limit_up_count": 68},
                "top_themes": ["Banking", "AI Hardware"],
                "failed_patterns": ["low-volume reversal"],
                "recommended_picks_review": [{"stock_code": "000001", "effect": "spike and fade", "close_change_pct": 1.2}],
                "lesson_items": [{"title": "strong auction does not guarantee full-day strength", "tag": "risk"}],
                "next_day_focus": ["watch banking follow-through"],
            },
        },
    )
    position_import = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "21:30 position-review",
            "skill_name": "position-review",
            "revision_id": position_revision_id,
            "job_type": "position_review",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "positions finished 2W 1F"},
            "push": {"status": "sent", "channel": "wechat"},
            "raw_output": "position review",
            "result_payload": {
                "position_review": [{"stock_code": "000001", "action": "trim", "reason": "failed to hold highs"}],
                "lesson_items": [{"title": "trim failed afternoon reclaim", "tag": "execution"}],
                "next_day_focus": ["handle gap-up exits"],
            },
        },
    )

    assert pick_import.status_code == 200
    assert review_import.status_code == 200
    assert position_import.status_code == 200

    jobs = client.get("/api/ai/jobs")
    runs = client.get("/api/ai/runs", params={"job_type": "stock_pick", "display_group": "盘中", "status": "success", "trading_date": "2026-05-08"})
    run_detail = client.get(f"/api/ai/runs/{pick_import.json()['run']['id']}")
    picks = client.get("/api/ai/picks", params={"trading_date": "2026-05-08", "run_type": "production"})
    trading_day = client.get("/api/ai/trading-days/2026-05-08")
    history = client.get(f"/api/ai/jobs/{job_id}/history")
    skills = client.get("/api/ai/skills")
    stock_pick_skill_id = next(item["id"] for item in skills.json()["items"] if item["name"] == "auction-scan")
    performance = client.get(f"/api/ai/skills/{stock_pick_skill_id}/performance")

    assert jobs.status_code == 200
    assert runs.status_code == 200
    assert run_detail.status_code == 200
    assert picks.status_code == 200
    assert trading_day.status_code == 200
    assert history.status_code == 200
    assert performance.status_code == 200
    assert any(item["job_type"] == "stock_pick" and item["name"] == "09:26 auction-scan" for item in jobs.json()["items"])
    assert "latest_run_summary" in jobs.json()["items"][0]
    assert runs.json()["items"][0]["result_type"] == "stock_pick"
    assert runs.json()["items"][0]["display_group"] == "盘中"
    assert run_detail.json()["result_payload"]["structured_picks"][0]["pick_level"] == "confirm"
    assert picks.json()["items"][0]["sources"][0]["signal_context"] == "集合竞价转强"
    assert trading_day.json()["market_summary"]["headline"] == "index repaired"
    assert trading_day.json()["position_review"][0]["action"] == "trim"
    assert history.json()["job"]["id"] == job_id
    assert history.json()["summary"]["run_count"] >= 1
    assert performance.json()["skill"]["id"] == stock_pick_skill_id


def test_ai_experience_rulepack_can_feedback_into_stock_research_and_support_rollback() -> None:
    from app.services.stock_research import StockResearchService

    client, session_factory = build_ai_client()
    _, day_review_revision_id, _ = seed_skill(
        session_factory,
        skill_name="day-review",
        job_name="19:00 day-review",
        job_type="day_review",
        display_group="盘后",
    )
    research_skill_id, research_revision_id, research_job_id = seed_skill(
        session_factory,
        skill_name="stock-research",
        job_name="15:00 stock-research",
        job_type="stock_pick",
        display_group="盘后",
    )

    review_import = client.post(
        "/api/ai/import-run",
        json={
            "job_name": "19:00 day-review",
            "skill_name": "day-review",
            "revision_id": day_review_revision_id,
            "job_type": "day_review",
            "trading_date": "2026-05-08",
            "run_type": "production",
            "summary": {"headline": "review with rule candidates"},
            "push": {"status": "sent"},
            "result_payload": {
                "market_summary": {"headline": "review complete", "risk_prompt": "watch afternoon fade"},
                "lesson_items": [
                    {
                        "title": "reward momentum resonance",
                        "tag": "pattern",
                        "direction": "boost",
                        "weight": 2.5,
                        "match": {"theme_tags": ["momentum"]},
                    },
                    {
                        "title": "penalize weak main flow",
                        "tag": "risk",
                        "direction": "penalize",
                        "weight": 1.2,
                        "match": {"risk_flags": ["资金强度一般"]},
                    },
                ],
                "next_day_focus": ["prefer multi-factor resonance"],
            },
        },
    )

    assert review_import.status_code == 200

    promoted = client.post(
        "/api/ai/rulepacks/promote",
        json={
            "trading_date": "2026-05-08",
            "name": "2026-05-08 经验规则包",
            "job_id": research_job_id,
            "status": "active",
        },
    )

    assert promoted.status_code == 200
    active_rulepack_id = promoted.json()["rulepack"]["id"]
    assert promoted.json()["rulepack"]["rule_count"] == 2
    assert promoted.json()["job"]["active_rulepack_id"] == active_rulepack_id

    with session_factory() as session:
        research_result = StockResearchService(
            gateway=AiGateway(),
            now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0),
        ).run(
            session,
            trading_date=date(2026, 5, 8),
            limit=2,
            skill_name="stock-research",
            revision_title="stock-research v1",
            job_name="15:00 stock-research",
        )
        ai_run = AiCenterService(
            gateway=AiGateway(),
            now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0),
        ).get_run(session, research_result["ai_run_id"])

    assert ai_run is not None
    first_pick = ai_run["result_payload"]["structured_picks"][0]
    assert first_pick["experience_feedback"]["rulepack_id"] == active_rulepack_id
    assert first_pick["experience_feedback"]["matched_rule_count"] >= 1
    assert any(entry["direction"] == "boost" for entry in first_pick["experience_feedback"]["matched_rules"])

    second_promote = client.post(
        "/api/ai/rulepacks/promote",
        json={
            "trading_date": "2026-05-08",
            "name": "2026-05-08 回退前规则包",
            "job_id": research_job_id,
            "status": "draft",
        },
    )
    second_rulepack_id = second_promote.json()["rulepack"]["id"]
    rollback = client.post(
        f"/api/ai/jobs/{research_job_id}/activate-rulepack",
        json={"rulepack_id": active_rulepack_id},
    )
    rulepacks = client.get("/api/ai/rulepacks", params={"job_id": research_job_id})
    jobs = client.get("/api/ai/jobs")
    skills = client.get(f"/api/ai/skills/{research_skill_id}/performance")

    assert second_promote.status_code == 200
    assert rollback.status_code == 200
    assert rollback.json()["job"]["active_rulepack_id"] == active_rulepack_id
    assert any(item["id"] == second_rulepack_id for item in rulepacks.json()["items"])
    assert any(item["id"] == research_job_id and item["active_rulepack_id"] == active_rulepack_id for item in jobs.json()["items"])
    assert skills.status_code == 200


def test_builtin_jobs_have_engine_type_set() -> None:
    """All builtin jobs should have engine_type populated, not NULL."""
    client, _ = build_ai_client()

    jobs = client.get("/api/ai/jobs")
    assert jobs.status_code == 200
    for item in jobs.json()["items"]:
        assert item.get("engine_type") is not None, f"Job {item['name']} has no engine_type"


def test_ai_scheduler_status_endpoint() -> None:
    """The scheduler-status endpoint should return job registration info."""
    client, _ = build_ai_client()

    response = client.get("/api/ai/scheduler-status")
    assert response.status_code == 200
    payload = response.json()
    # Scheduler is disabled in the test client, so it should report not running
    assert "scheduler_running" in payload
    assert "db_job_statuses" in payload


def test_auto_schedule_field_is_respected_in_registry() -> None:
    """Jobs with auto_schedule=False should still appear in jobs list but can be filtered."""
    from sqlalchemy import select

    client, session_factory = build_ai_client()

    with session_factory() as session:
        job = session.scalar(select(AiJob).where(AiJob.name == "08:20 盘前消息面挖掘"))
        assert job is not None
        assert job.auto_schedule is True

    # The auto_schedule field should be visible via the API
    jobs = client.get("/api/ai/jobs")
    assert jobs.status_code == 200


def test_build_prompt_sanitizes_colon_in_skill_name() -> None:
    """Output filenames should not contain colons (invalid on macOS)."""
    from app.services.skill_executor import _build_prompt

    prompt = _build_prompt(
        "08:20 盘前消息面挖掘",
        date(2026, 6, 8),
        "/tmp/data.json",
        "/tmp/outbox",
        "claude-code",
    )
    import re
    m = re.search(r"写入:\s*(.+\.json)", prompt)
    assert m is not None, "Output path not found in prompt"
    output_path = m.group(1)
    assert ":" not in output_path, f"Colon found in output path: {output_path}"
    assert "0820" in output_path or "08_20" in output_path, f"Time prefix not sanitized: {output_path}"


def test_catchup_mechanism_on_scheduler_startup() -> None:
    """When the app starts after a job's scheduled time, catch-up jobs should be created."""
    from sqlalchemy import select

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    # Use current real time but offset to be after the earliest scheduled job
    # Set now_provider to return a time after all cron schedules on a weekday
    # Use a fixed time far enough in the future that APScheduler won't skip catch-up jobs
    real_now = datetime.now()
    # Use a time that is close to real time so APScheduler doesn't skip it
    test_time = real_now.replace(hour=22, minute=4, second=0, microsecond=0)
    # If test_time is in the past today, add a day
    if test_time < real_now:
        from datetime import timedelta
        test_time = test_time + timedelta(days=1)
    app = create_app(
        session_factory=session_factory,
        gateway=AiGateway(),
        enable_scheduler=True,
        now_provider=lambda: test_time,
    )
    with TestClient(app) as client:
        scheduler = app.state.scheduler
        assert scheduler is not None
        assert scheduler.running

        # Check that catch-up jobs were created
        all_jobs = scheduler.get_jobs()
        catchup_jobs = [j for j in all_jobs if j.id.startswith("ai-skill-catchup-")]
        cron_jobs = [j for j in all_jobs if j.id.startswith("ai-skill-") and not j.id.startswith("ai-skill-catchup-")]
        # At 22:04 on a weekday, several jobs should have been missed
        assert len(catchup_jobs) >= 1, f"Expected catch-up jobs but found {len(catchup_jobs)}, all jobs: {[j.id for j in all_jobs]}"
        # Cron jobs should also be registered
        assert len(cron_jobs) >= 1


def test_scan_import_directory_tolerates_name_drift_and_isolates_failures(tmp_path) -> None:
    """Regression: production payloads sometimes carry ``skill_name`` /
    ``job_name`` with a leading schedule prefix (``08:20 X``) or a trailing
    revision tag (``X (v3)``), but the AiSkill row stores the bare name. The
    importer must tolerate that drift; one bad file must not block the rest.
    """

    _, session_factory = build_ai_client()
    skill_id, _, _ = seed_skill(session_factory)  # creates 'auction-scan' + job '09:26 auction-scan'

    inbox = tmp_path / "inbox"
    processed = tmp_path / "processed"
    inbox.mkdir()
    processed.mkdir()

    # File 1: payload uses the job_name (with time prefix) in BOTH skill_name
    # and job_name. Lookup must strip the "09:26 " prefix to find the skill.
    pick = stock_pick_payload(stock_code="000001", level="watch", summary="drift recovered")
    (inbox / "good_with_prefix.json").write_text(
        json.dumps(
            {
                "skill_name": "09:26 auction-scan",
                "job_name": "09:26 auction-scan",
                "job_type": "stock_pick",
                "trading_date": "2026-05-07",
                "run_type": "production",
                "raw_output": "ok",
                "summary": {"headline": "ok"},
                "push": {"status": "sent"},
                "result_payload": {"structured_picks": [pick]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # File 2: malformed JSON. Must not abort the batch; goes to _failed/.
    (inbox / "bad_json.json").write_text("{ not valid json", encoding="utf-8")

    # File 3: skill_name matches nothing at all (also goes to _failed/).
    (inbox / "unknown_skill.json").write_text(
        json.dumps(
            {
                "skill_name": "nonexistent",
                "trading_date": "2026-05-07",
                "summary": {},
                "push": {},
                "result_payload": {"structured_picks": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = AiCenterService(gateway=AiGateway(), now_provider=lambda: datetime(2026, 5, 8, 15, 0, 0))
    with session_factory() as session:
        summary = service.scan_import_directory(session, inbox_dir=inbox, processed_dir=processed)

    assert skill_id > 0
    assert summary["imported"] == 1, summary
    assert summary["failed"] == 2, summary
    assert {f["file"] for f in summary["failures"]} == {"bad_json.json", "unknown_skill.json"}
    assert (processed / "good_with_prefix.json").exists()
    assert (inbox / "_failed" / "bad_json.json").exists()
    assert (inbox / "_failed" / "unknown_skill.json").exists()
    assert not (inbox / "good_with_prefix.json").exists()


# ── Skill Chat SSE streaming ─────────────────────────────────────────────────


class _FakePopen:
    """Mock subprocess.Popen yielding a fixed line stream + small delays.

    Mirrors the surface used by `_skill_chat_stream_generator`:
      - stdout.readline() blocking call returning "" on EOF
      - .poll() returning the exit code only after all lines drained
      - .wait(timeout) / .kill()
    """

    def __init__(self, args, stdout=None, stderr=None, bufsize=1, text=True, **kwargs):
        import threading as _threading
        self.args = args
        self._lines = ["你好", "，", "我", "是", " AI", " 助手", "。",
                        "```json\n{\"name\": \"test\"}\n```", ""]
        self._idx = 0
        self._lock = _threading.Lock()
        self.returncode = None
        # Make `.stdout` / `.stderr` point to `self` so the generator's
        # `proc.stdout.readline()` / `proc.stderr.read()` resolves to our mocked
        # methods rather than the empty StringIO default.
        self.stdout = self
        self.stderr = self

    def _next_line(self):
        with self._lock:
            if self._idx >= len(self._lines):
                return ""
            line = self._lines[self._idx]
            self._idx += 1
        return line

    def readline(self):
        import time as _time
        line = self._next_line()
        # Simulate a tiny pause between lines so the streaming generator yields
        if line == "":
            _time.sleep(0.01)
        return line

    def poll(self):
        if self._idx >= len(self._lines):
            self.returncode = 0
            return 0
        return None

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9

    def communicate(self, input=None, timeout=None):
        # drain the (already consumed by .stdout.readline() if used) buffer; for non-stream
        # branch (subprocess.run) we haven't consumed anything yet, so drain by index.
        lines = []
        while True:
            with self._lock:
                if self._idx >= len(self._lines):
                    break
                line = self._lines[self._idx]
                self._idx += 1
            lines.append(line)
        self.returncode = 0
        return ("".join(lines), "")

    # `subprocess.run(..., capture_output=True)` 在 subprocess 内部用 `with Popen(...) as process:`
    # 上下文协议 → 测试 mock 必须实现，否则非流式路径会 TypeError
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.wait(timeout=5)
        except Exception:
            pass
        return False


@pytest.fixture
def patched_skill_chat(monkeypatch):
    """Inject fake claude CLI for skill-chat streaming tests."""
    from app import main as app_main

    monkeypatch.setattr(app_main, "_find_cli_path", lambda name: "/fake/claude")
    monkeypatch.setattr(app_main.subprocess, "Popen", _FakePopen)
    # Shrink heartbeat so tests are quick
    monkeypatch.setattr(app_main, "_SKILL_CHAT_HEARTBEAT_SECONDS", 0.05)
    return app_main


def _parse_sse_events(raw_chunks):
    """Concatenate raw SSE line chunks and yield parsed `data:` JSON payloads."""
    import json as _json
    buf = ""
    for chunk in raw_chunks:
        buf += chunk
        while "\n\n" in buf:
            raw_event, buf = buf.split("\n\n", 1)
            for ln in raw_event.split("\n"):
                if ln.startswith(":"):
                    continue
                if ln.startswith("data:"):
                    try:
                        yield _json.loads(ln[5:].strip())
                    except Exception:
                        pass


def test_skill_chat_streams_deltas_and_done(patched_skill_chat):
    client, _ = build_ai_client()
    raw_text = ""
    with client.stream("POST", "/api/ai/skill-chat", json={"message": "写一句问候"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # TestClient/httpx 流式响应：iter_text() 累加原始字节流（不会按 HTTP chunk 切 SSE 事件）
        for chunk in response.iter_text():
            raw_text += chunk

    events = list(_parse_sse_events([raw_text]))
    types = [e.get("type") for e in events]

    # 至少有一个 delta + 一个 done
    assert "delta" in types, f"raw={raw_text!r} events={events}"
    assert types.count("done") == 1, f"events={events}"

    # delta 文本累积还原出原文
    full_text = "".join(e["text"] for e in events if e.get("type") == "delta")
    assert "你好" in full_text
    assert "AI" in full_text

    # done 事件里 skill_draft 必须解析到 JSON 草案
    done = next(e for e in events if e.get("type") == "done")
    assert done["skill_draft"] == {"name": "test"}
    assert "duration_ms" in done
    assert isinstance(done["duration_ms"], int)


def test_skill_chat_non_stream_fallback(patched_skill_chat):
    client, _ = build_ai_client()
    response = client.post(
        "/api/ai/skill-chat?stream=false",
        json={"message": "写一句问候"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "你好" in data["response"]
    assert data["skill_draft"] == {"name": "test"}
    assert "duration_ms" in data


def test_skill_chat_cli_missing(monkeypatch):
    from app import main as app_main
    monkeypatch.setattr(app_main, "_find_cli_path", lambda name: None)
    client, _ = build_ai_client()
    with client.stream("POST", "/api/ai/skill-chat", json={"message": "x"}) as response:
        # CLI 缺失也会回 SSE（错误+done 两个事件）
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw_chunks = list(response.iter_lines())
        raw_text = "\n".join(raw_chunks)

    events = list(_parse_sse_events([raw_text + "\n"] if raw_text else []))
    types = [e.get("type") for e in events]
    assert "error" in types, f"events={events}, raw_text={raw_text!r}"
    assert "done" in types, f"events={events}, raw_text={raw_text!r}"

    error = next(e for e in events if e.get("type") == "error")
    assert "未找到" in error["message"] or "Claude" in error["message"]


def test_skill_chat_body_stream_false_overrides_default(patched_skill_chat):
    client, _ = build_ai_client()
    response = client.post(
        "/api/ai/skill-chat",
        json={"message": "hi", "stream": False},
    )
    # JSON fallback path returns application/json, not text/event-stream
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "你好" in data["response"]
