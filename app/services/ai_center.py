from __future__ import annotations

from collections import defaultdict
from datetime import date
from datetime import datetime
from datetime import timedelta
import json
from pathlib import Path
import shutil
from typing import Any

from sqlalchemy import desc
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_center_registry import BUILTIN_AI_JOBS
from app.models import AiBacktestBatch
from app.models import AiJob
from app.models import AiPick
from app.models import AiPickOutcome
from app.models import AiExperienceRule
from app.models import AiExperienceRulepack
from app.models import AiReviewNote
from app.models import AiRun
from app.models import AiSkill
from app.models import AiSkillRevision
from app.models import AiTradingDayReview


PICK_REQUIRED_FIELDS = (
    "stock_code",
    "stock_name",
    "pick_level",
    "reason_summary",
    "sector_name",
    "theme_tags",
    "capital_profile",
    "signal_context",
    "risk_flags",
    "entry_hint",
)


class AiCenterService:
    def __init__(self, *, gateway: Any, now_provider: Any | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    def ensure_builtin_registry(self, session: Session) -> dict[str, int]:
        created_skills = 0
        created_revisions = 0
        created_jobs = 0
        skill_by_name = {skill.name: skill for skill in session.scalars(select(AiSkill))}
        job_by_name = {job.name: job for job in session.scalars(select(AiJob))}

        for item in BUILTIN_AI_JOBS:
            skill = skill_by_name.get(item["skill_name"])
            if skill is None:
                skill = AiSkill(
                    name=item["skill_name"],
                    category=item["skill_category"],
                    description=item["description"],
                    enabled=True,
                )
                session.add(skill)
                session.flush()
                skill_by_name[skill.name] = skill
                created_skills += 1

            revision = session.scalar(
                select(AiSkillRevision).where(
                    AiSkillRevision.skill_id == skill.id,
                    AiSkillRevision.title == item["revision_title"],
                )
            )
            if revision is None:
                revision = AiSkillRevision(
                    skill_id=skill.id,
                    revision_no=1,
                    title=item["revision_title"],
                    content_text=item["revision_content"],
                    config_json=json.dumps({"builtin": True}, ensure_ascii=False),
                    change_note=item["change_note"],
                    status="active",
                )
                self._demote_active_revisions(session, skill.id)
                session.add(revision)
                session.flush()
                created_revisions += 1

            job = job_by_name.get(item["job_name"])
            if job is None:
                job = AiJob(
                    name=item["job_name"],
                    schedule_label=item["schedule_label"],
                    schedule_rrule_or_cron=item["schedule_rrule_or_cron"],
                    skill_id=skill.id,
                    active_revision_id=revision.id,
                    job_type=item["job_type"],
                    result_schema_version=item["result_schema_version"],
                    display_group=item["display_group"],
                    enabled=True,
                )
                session.add(job)
                session.flush()
                job_by_name[job.name] = job
                created_jobs += 1
            else:
                updated = False
                for attr, value in (
                    ("skill_id", skill.id),
                    ("active_revision_id", revision.id),
                    ("schedule_label", item["schedule_label"]),
                    ("schedule_rrule_or_cron", item["schedule_rrule_or_cron"]),
                    ("job_type", item["job_type"]),
                    ("result_schema_version", item["result_schema_version"]),
                    ("display_group", item["display_group"]),
                    ("enabled", True),
                ):
                    if getattr(job, attr) != value:
                        setattr(job, attr, value)
                        updated = True
                if updated:
                    session.add(job)

        session.commit()
        return {
            "created_skills": created_skills,
            "created_revisions": created_revisions,
            "created_jobs": created_jobs,
        }

    def seed_demo_data(self, session: Session, *, trading_date: date) -> dict[str, Any]:
        self.ensure_builtin_registry(session)
        jobs = {job.name: job for job in session.scalars(select(AiJob))}
        skills = {skill.id: skill for skill in session.scalars(select(AiSkill))}
        revisions = {revision.id: revision for revision in session.scalars(select(AiSkillRevision))}
        payloads: list[dict[str, Any]] = []
        payloads.extend(
            self._demo_payloads_for_date(
                session,
                jobs=jobs,
                skills=skills,
                revisions=revisions,
                trading_date=trading_date - timedelta(days=1),
                include_reviews=False,
            )
        )
        payloads.extend(
            self._demo_payloads_for_date(
                session,
                jobs=jobs,
                skills=skills,
                revisions=revisions,
                trading_date=trading_date,
                include_reviews=True,
            )
        )

        seeded_runs = 0
        seeded_picks = 0
        for payload in payloads:
            result = self.import_run(session, payload)
            seeded_runs += 1
            seeded_picks += len(result.get("picks", []))

        return {
            "trading_date": trading_date.isoformat(),
            "seeded_runs": seeded_runs,
            "seeded_picks": seeded_picks,
            "skipped_runs": len(BUILTIN_AI_JOBS) - seeded_runs,
        }

    def clear_demo_data(self, session: Session, *, trading_date: date) -> dict[str, Any]:
        demo_runs = list(
            session.scalars(select(AiRun).where(AiRun.trading_date == trading_date, AiRun.run_type == "demo"))
        )
        run_ids = [run.id for run in demo_runs]
        if not run_ids:
            return {
                "trading_date": trading_date.isoformat(),
                "deleted_runs": 0,
                "deleted_picks": 0,
                "deleted_outcomes": 0,
                "deleted_reviews": 0,
                "deleted_trading_day_review": False,
            }

        demo_picks = list(session.scalars(select(AiPick).where(AiPick.run_id.in_(run_ids))))
        pick_ids = [pick.id for pick in demo_picks]

        deleted_outcomes = 0
        deleted_reviews = 0
        if pick_ids:
            deleted_outcomes = session.execute(delete(AiPickOutcome).where(AiPickOutcome.pick_id.in_(pick_ids))).rowcount or 0
            deleted_reviews = session.execute(delete(AiReviewNote).where(AiReviewNote.pick_id.in_(pick_ids))).rowcount or 0

        deleted_picks = session.execute(delete(AiPick).where(AiPick.run_id.in_(run_ids))).rowcount or 0
        deleted_runs = session.execute(delete(AiRun).where(AiRun.id.in_(run_ids))).rowcount or 0

        remaining_review_run = session.scalar(
            select(AiRun.id).where(
                AiRun.trading_date == trading_date,
                AiRun.run_type != "demo",
                AiRun.result_type.in_(("day_review", "position_review", "weekly_review")),
            )
        )
        deleted_trading_day_review = False
        if remaining_review_run is None:
            deleted_trading_day_review = bool(
                session.execute(delete(AiTradingDayReview).where(AiTradingDayReview.trading_date == trading_date)).rowcount
            )

        session.commit()
        return {
            "trading_date": trading_date.isoformat(),
            "deleted_runs": deleted_runs,
            "deleted_picks": deleted_picks,
            "deleted_outcomes": deleted_outcomes,
            "deleted_reviews": deleted_reviews,
            "deleted_trading_day_review": deleted_trading_day_review,
        }

    def _demo_payloads_for_date(
        self,
        session: Session,
        *,
        jobs: dict[str, AiJob],
        skills: dict[int, AiSkill],
        revisions: dict[int, AiSkillRevision],
        trading_date: date,
        include_reviews: bool,
    ) -> list[dict[str, Any]]:
        existing_demo_runs = {
            (run.job_id, run.trading_date, run.run_type)
            for run in session.scalars(select(AiRun).where(AiRun.trading_date == trading_date, AiRun.run_type == "demo"))
        }
        payloads: list[dict[str, Any]] = []
        for index, item in enumerate(BUILTIN_AI_JOBS, start=1):
            if not include_reviews and item["job_type"] not in {"stock_pick", "stock_confirm"}:
                continue
            job = jobs.get(item["job_name"])
            if job is None or job.active_revision_id is None:
                continue
            if (job.id, trading_date, "demo") in existing_demo_runs:
                continue
            skill = skills.get(job.skill_id)
            revision = revisions.get(job.active_revision_id)
            if skill is None or revision is None:
                continue
            payloads.append(
                self._demo_payload_for_job(
                    job=job,
                    skill=skill,
                    revision=revision,
                    trading_date=trading_date,
                    sequence=index,
                )
            )
        return payloads

    def list_jobs(self, session: Session) -> dict[str, Any]:
        jobs = list(session.scalars(select(AiJob).order_by(AiJob.schedule_label.asc(), AiJob.id.asc())))
        latest_run_map = self._latest_run_map(session)
        skill_names = self._skill_name_map(session)
        revision_titles = self._revision_title_map(session)
        rulepack_names = self._rulepack_name_map(session)
        return {
            "items": [
                {
                    "id": job.id,
                    "name": job.name,
                    "schedule_label": job.schedule_label,
                    "schedule_rrule_or_cron": job.schedule_rrule_or_cron,
                    "skill_id": job.skill_id,
                    "skill_name": skill_names.get(job.skill_id),
                    "active_revision_id": job.active_revision_id,
                    "active_revision_title": revision_titles.get(job.active_revision_id),
                    "active_rulepack_id": job.active_rulepack_id,
                    "active_rulepack_name": rulepack_names.get(job.active_rulepack_id),
                    "job_type": job.job_type,
                    "result_schema_version": job.result_schema_version,
                    "display_group": job.display_group,
                    "enabled": job.enabled,
                    "latest_run_summary": latest_run_map.get(job.id),
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                }
                for job in jobs
            ]
        }

    def list_runs(
        self,
        session: Session,
        *,
        run_type: str | None = None,
        trading_date: date | None = None,
        job_type: str | None = None,
        display_group: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(AiRun).order_by(desc(AiRun.started_at), desc(AiRun.id))
        if run_type:
            stmt = stmt.where(AiRun.run_type == run_type)
        if trading_date:
            stmt = stmt.where(AiRun.trading_date == trading_date)
        if status:
            stmt = stmt.where(AiRun.status == status)

        runs = list(session.scalars(stmt))
        jobs = {job.id: job for job in session.scalars(select(AiJob))}
        skills = self._skill_name_map(session)
        revisions = self._revision_title_map(session)

        items = []
        for run in runs:
            job = jobs.get(run.job_id) if run.job_id else None
            if job_type and (job is None or job.job_type != job_type):
                continue
            if display_group and (job is None or job.display_group != display_group):
                continue
            items.append(
                {
                    "id": run.id,
                    "job_id": run.job_id,
                    "job_name": job.name if job else None,
                    "job_type": job.job_type if job else None,
                    "display_group": job.display_group if job else None,
                    "skill_id": run.skill_id,
                    "skill_name": skills.get(run.skill_id),
                    "revision_id": run.revision_id,
                    "revision_title": revisions.get(run.revision_id),
                    "backtest_batch_id": run.backtest_batch_id,
                    "run_type": run.run_type,
                    "trading_date": run.trading_date.isoformat(),
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "status": run.status,
                    "source_input_ref": run.source_input_ref,
                    "result_type": run.result_type,
                    "result_payload": self._loads_json(run.result_payload_json, {}),
                    "push_payload": self._loads_json(run.push_payload_json, {}),
                    "raw_output_text": run.raw_output_text,
                    "structured_summary": self._loads_json(run.structured_summary_json, {}),
                    "error_stage": run.error_stage,
                    "duration_ms": run.duration_ms,
                    "error_text": run.error_text,
                }
            )
        return {"items": items}

    def get_run(self, session: Session, run_id: int) -> dict[str, Any] | None:
        payload = next((entry for entry in self.list_runs(session)["items"] if entry["id"] == run_id), None)
        if payload is None:
            return None
        picks = list(
            session.scalars(
                select(AiPick)
                .where(AiPick.run_id == run_id)
                .order_by(AiPick.priority_rank.asc().nullslast(), AiPick.id.asc())
            )
        )
        payload["picks"] = [self._pick_dict(session, pick) for pick in picks]
        return payload

    def import_run(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = self.now_provider()
        skill = self._find_skill(session, payload)
        if skill is None:
            raise ValueError("skill not found")
        revision = self._find_revision(session, skill_id=skill.id, payload=payload)
        if revision is None:
            raise ValueError("revision not found")
        job = self._find_job(session, payload, skill.id)

        trading_date = date.fromisoformat(str(payload.get("trading_date")))
        summary = payload.get("summary") or payload.get("metadata") or {}
        push_payload = payload.get("push") or {}
        result_payload = payload.get("result_payload") or {}
        if not isinstance(summary, dict):
            raise ValueError("summary must be an object")
        if not isinstance(push_payload, dict):
            raise ValueError("push must be an object")
        if not isinstance(result_payload, dict):
            raise ValueError("result_payload must be an object")

        resolved_job_type = str(payload.get("job_type") or (job.job_type if job else "stock_pick"))
        picks_input = self._extract_structured_picks(payload=payload, result_payload=result_payload, job_type=resolved_job_type)

        run = AiRun(
            job_id=job.id if job else None,
            skill_id=skill.id,
            revision_id=revision.id,
            run_type=str(payload.get("run_type") or "production"),
            trading_date=trading_date,
            started_at=started_at,
            finished_at=started_at,
            status="success",
            source_input_ref=payload.get("source_input_ref"),
            result_type=resolved_job_type,
            result_payload_json=json.dumps(result_payload, ensure_ascii=False),
            push_payload_json=json.dumps(push_payload, ensure_ascii=False),
            raw_output_text=payload.get("raw_output"),
            structured_summary_json=json.dumps(summary, ensure_ascii=False),
            duration_ms=int(payload.get("duration_ms") or 0) or None,
        )
        session.add(run)
        session.flush()

        created_picks: list[AiPick] = []
        if resolved_job_type in {"stock_pick", "stock_confirm"}:
            for index, item in enumerate(picks_input, start=1):
                self._validate_stock_pick(item)
                pick = AiPick(
                    run_id=run.id,
                    trading_date=trading_date,
                    stock_code=str(item["stock_code"]).strip(),
                    stock_name=str(item["stock_name"]).strip(),
                    sector_name=item.get("sector_name"),
                    pick_type=item.get("pick_level") or item.get("pick_type"),
                    confidence_score=self._to_float(item.get("confidence_score")),
                    reason_summary=item.get("reason_summary"),
                    tags_json=json.dumps(item.get("theme_tags") or item.get("tags") or [], ensure_ascii=False),
                    priority_rank=int(item.get("priority_rank") or index),
                )
                session.add(pick)
                session.flush()
                created_picks.append(pick)
                self.compute_pick_outcomes(session, pick)
        elif resolved_job_type in {"day_review", "position_review", "weekly_review"}:
            self._upsert_trading_day_review(session, trading_date=trading_date, result_payload=result_payload, job_type=resolved_job_type)

        session.commit()
        return {"run": self.get_run(session, run.id), "picks": [self._pick_dict(session, pick) for pick in created_picks]}

    def list_picks(self, session: Session, *, trading_date: date | None = None, run_type: str | None = None) -> dict[str, Any]:
        stmt = select(AiPick).order_by(desc(AiPick.trading_date), AiPick.stock_code.asc(), AiPick.id.asc())
        if trading_date:
            stmt = stmt.where(AiPick.trading_date == trading_date)
        picks = list(session.scalars(stmt))
        if run_type:
            allowed_run_ids = set(session.scalars(select(AiRun.id).where(AiRun.run_type == run_type)))
            picks = [pick for pick in picks if pick.run_id in allowed_run_ids]

        grouped: dict[tuple[date, str], list[AiPick]] = defaultdict(list)
        for pick in picks:
            grouped[(pick.trading_date, pick.stock_code)].append(pick)

        items = []
        for (_, _), bucket in grouped.items():
            representative = bucket[0]
            items.append(
                {
                    "trading_date": representative.trading_date.isoformat(),
                    "stock_code": representative.stock_code,
                    "stock_name": representative.stock_name,
                    "sector_name": representative.sector_name,
                    "source_count": len(bucket),
                    "sources": [self._pick_source_dict(session, pick) for pick in bucket],
                    "tags": sorted({tag for pick in bucket for tag in self._loads_json(pick.tags_json, [])}),
                    "outcomes": self._aggregate_outcomes(session, [pick.id for pick in bucket]),
                }
            )
        items.sort(key=lambda item: (item["trading_date"], item["source_count"], item["stock_code"]), reverse=True)
        return {"items": items}

    def list_skills(self, session: Session) -> dict[str, Any]:
        skills = list(session.scalars(select(AiSkill).order_by(AiSkill.name.asc())))
        revisions = list(session.scalars(select(AiSkillRevision).order_by(AiSkillRevision.skill_id.asc(), AiSkillRevision.revision_no.asc())))
        jobs = list(session.scalars(select(AiJob).order_by(AiJob.schedule_label.asc(), AiJob.id.asc())))
        rulepack_names = self._rulepack_name_map(session)
        revision_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for revision in revisions:
            revision_buckets[revision.skill_id].append(self._revision_dict(revision))
        return {
            "items": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "category": skill.category,
                    "enabled": skill.enabled,
                    "description": skill.description,
                    "created_at": skill.created_at.isoformat() if skill.created_at else None,
                    "revisions": revision_buckets.get(skill.id, []),
                }
                for skill in skills
            ],
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "skill_id": job.skill_id,
                    "active_revision_id": job.active_revision_id,
                    "active_rulepack_id": job.active_rulepack_id,
                    "active_rulepack_name": rulepack_names.get(job.active_rulepack_id),
                    "schedule_label": job.schedule_label,
                    "job_type": job.job_type,
                    "display_group": job.display_group,
                    "enabled": job.enabled,
                }
                for job in jobs
            ],
        }

    def create_revision(self, session: Session, skill_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        skill = session.get(AiSkill, skill_id)
        if skill is None:
            raise ValueError("skill not found")
        latest_no = session.scalar(select(AiSkillRevision.revision_no).where(AiSkillRevision.skill_id == skill_id).order_by(AiSkillRevision.revision_no.desc()))
        revision = AiSkillRevision(
            skill_id=skill_id,
            revision_no=(latest_no or 0) + 1,
            title=str(payload.get("title") or f"{skill.name} v{(latest_no or 0) + 1}"),
            content_text=str(payload.get("content_text") or ""),
            config_json=json.dumps(payload.get("config") or {}, ensure_ascii=False),
            change_note=payload.get("change_note"),
            status=str(payload.get("status") or "draft"),
        )
        if revision.status == "active":
            self._demote_active_revisions(session, skill_id)
        session.add(revision)
        session.commit()
        session.refresh(revision)
        return self._revision_dict(revision)

    def activate_revision(self, session: Session, job_id: int, revision_id: int) -> dict[str, Any]:
        job = session.get(AiJob, job_id)
        revision = session.get(AiSkillRevision, revision_id)
        if job is None or revision is None:
            raise ValueError("job or revision not found")
        if revision.skill_id != job.skill_id:
            raise ValueError("revision does not belong to job skill")
        self._demote_active_revisions(session, job.skill_id)
        revision.status = "active"
        job.active_revision_id = revision.id
        session.commit()
        session.refresh(job)
        return {"job": {"id": job.id, "name": job.name, "active_revision_id": job.active_revision_id}}

    def list_rulepacks(self, session: Session, *, job_id: int | None = None) -> dict[str, Any]:
        stmt = select(AiExperienceRulepack).order_by(desc(AiExperienceRulepack.created_at), desc(AiExperienceRulepack.id))
        items = list(session.scalars(stmt))
        jobs = {job.id: job for job in session.scalars(select(AiJob))}
        if job_id is not None:
            job = jobs.get(job_id)
            if job is None:
                raise ValueError("job not found")
            active_id = job.active_rulepack_id
            items = [item for item in items if item.id == active_id or item.scope == job.job_type]
        return {
            "items": [self._rulepack_dict(session, item, jobs=jobs) for item in items]
        }

    def promote_rulepack(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        trading_date = self._parse_date(payload.get("trading_date"))
        if trading_date is None:
            raise ValueError("trading_date is required")
        source_review = session.scalar(select(AiTradingDayReview).where(AiTradingDayReview.trading_date == trading_date))
        if source_review is None:
            raise ValueError("trading day review not found")
        lessons = self._loads_json(source_review.lesson_items_json, [])
        rules = self._build_rules_from_lessons(lessons)
        if not rules:
            raise ValueError("no promotable lesson items found")

        job = None
        if payload.get("job_id"):
            job = session.get(AiJob, int(payload["job_id"]))
            if job is None:
                raise ValueError("job not found")

        rulepack = AiExperienceRulepack(
            name=str(payload.get("name") or f"{trading_date.isoformat()} 经验规则包"),
            scope=str(payload.get("scope") or (job.job_type if job else "stock_pick")),
            status=str(payload.get("status") or "draft"),
            source_trading_date=trading_date,
            summary_json=json.dumps(
                {
                    "trading_date": trading_date.isoformat(),
                    "rule_count": len(rules),
                    "source_headline": self._loads_json(source_review.market_summary_json, {}).get("headline"),
                },
                ensure_ascii=False,
            ),
        )
        session.add(rulepack)
        session.flush()

        for item in rules:
            session.add(
                AiExperienceRule(
                    rulepack_id=rulepack.id,
                    title=item["title"],
                    tag=item["tag"],
                    direction=item["direction"],
                    weight=item["weight"],
                    match_json=json.dumps(item["match"], ensure_ascii=False),
                    evidence_json=json.dumps(item.get("evidence") or {}, ensure_ascii=False),
                )
            )

        if job is not None and rulepack.status == "active":
            job.active_rulepack_id = rulepack.id
            session.add(job)

        session.commit()
        session.refresh(rulepack)
        result: dict[str, Any] = {"rulepack": self._rulepack_dict(session, rulepack)}
        if job is not None:
            result["job"] = {
                "id": job.id,
                "name": job.name,
                "active_rulepack_id": job.active_rulepack_id,
            }
        return result

    def activate_rulepack(self, session: Session, job_id: int, rulepack_id: int) -> dict[str, Any]:
        job = session.get(AiJob, job_id)
        rulepack = session.get(AiExperienceRulepack, rulepack_id)
        if job is None or rulepack is None:
            raise ValueError("job or rulepack not found")
        job.active_rulepack_id = rulepack.id
        rulepack.status = "active"
        session.add(job)
        session.add(rulepack)
        session.commit()
        session.refresh(job)
        return {
            "job": {
                "id": job.id,
                "name": job.name,
                "active_rulepack_id": job.active_rulepack_id,
            },
            "rulepack": self._rulepack_dict(session, rulepack),
        }

    def add_review(self, session: Session, pick_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        pick = session.get(AiPick, pick_id)
        if pick is None:
            raise ValueError("pick not found")
        note = AiReviewNote(
            pick_id=pick_id,
            window=str(payload.get("window") or "T+1"),
            review_text=str(payload.get("review_text") or ""),
            review_tags_json=json.dumps(payload.get("review_tags") or [], ensure_ascii=False),
            is_expectation_met=payload.get("is_expectation_met"),
            failure_reason=payload.get("failure_reason"),
            improvement_hint=payload.get("improvement_hint"),
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return self._review_dict(note)

    def get_pick_review(self, session: Session, pick_id: int) -> dict[str, Any]:
        pick = session.get(AiPick, pick_id)
        if pick is None:
            raise ValueError("pick not found")
        notes = list(
            session.scalars(
                select(AiReviewNote)
                .where(AiReviewNote.pick_id == pick_id)
                .order_by(desc(AiReviewNote.created_at), desc(AiReviewNote.id))
            )
        )
        return {"pick": self._pick_dict(session, pick), "notes": [self._review_dict(note) for note in notes]}

    def create_backtest_batch(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = int(payload.get("skill_id"))
        revision_id = int(payload.get("revision_id"))
        date_from = date.fromisoformat(str(payload.get("date_from")))
        date_to = date.fromisoformat(str(payload.get("date_to")))
        batch = AiBacktestBatch(
            skill_id=skill_id,
            revision_id=revision_id,
            date_from=date_from,
            date_to=date_to,
            status="running",
            summary_json="{}",
        )
        session.add(batch)
        session.flush()

        source_runs = list(
            session.scalars(
                select(AiRun)
                .where(
                    AiRun.skill_id == skill_id,
                    AiRun.run_type == "production",
                    AiRun.trading_date >= date_from,
                    AiRun.trading_date <= date_to,
                )
                .order_by(AiRun.trading_date.asc(), AiRun.id.asc())
            )
        )

        created = 0
        for source_run in source_runs:
            cloned_run = AiRun(
                job_id=source_run.job_id,
                skill_id=source_run.skill_id,
                revision_id=revision_id,
                backtest_batch_id=batch.id,
                run_type="backtest",
                trading_date=source_run.trading_date,
                started_at=self.now_provider(),
                finished_at=self.now_provider(),
                status="success",
                source_input_ref=f"backtest:{source_run.id}",
                result_type=source_run.result_type,
                result_payload_json=source_run.result_payload_json,
                push_payload_json=source_run.push_payload_json,
                raw_output_text=source_run.raw_output_text,
                structured_summary_json=source_run.structured_summary_json,
                error_stage=source_run.error_stage,
                duration_ms=source_run.duration_ms,
            )
            session.add(cloned_run)
            session.flush()
            source_picks = list(session.scalars(select(AiPick).where(AiPick.run_id == source_run.id).order_by(AiPick.id.asc())))
            for source_pick in source_picks:
                cloned_pick = AiPick(
                    run_id=cloned_run.id,
                    trading_date=source_pick.trading_date,
                    stock_code=source_pick.stock_code,
                    stock_name=source_pick.stock_name,
                    sector_name=source_pick.sector_name,
                    pick_type=source_pick.pick_type,
                    confidence_score=source_pick.confidence_score,
                    reason_summary=source_pick.reason_summary,
                    tags_json=source_pick.tags_json,
                    priority_rank=source_pick.priority_rank,
                )
                session.add(cloned_pick)
                session.flush()
                self.compute_pick_outcomes(session, cloned_pick)
            created += 1

        batch.status = "completed"
        batch.summary_json = json.dumps({"runs_created": created}, ensure_ascii=False)
        session.commit()
        return {"batch_id": batch.id, "runs_created": created, "status": batch.status}

    def list_backtests(self, session: Session) -> dict[str, Any]:
        batches = list(session.scalars(select(AiBacktestBatch).order_by(desc(AiBacktestBatch.created_at), desc(AiBacktestBatch.id))))
        skill_names = self._skill_name_map(session)
        revision_titles = self._revision_title_map(session)
        return {
            "items": [
                {
                    "id": batch.id,
                    "skill_id": batch.skill_id,
                    "skill_name": skill_names.get(batch.skill_id),
                    "revision_id": batch.revision_id,
                    "revision_title": revision_titles.get(batch.revision_id),
                    "date_from": batch.date_from.isoformat(),
                    "date_to": batch.date_to.isoformat(),
                    "status": batch.status,
                    "summary": self._loads_json(batch.summary_json, {}),
                    "created_at": batch.created_at.isoformat() if batch.created_at else None,
                }
                for batch in batches
            ]
        }

    def get_insights_summary(self, session: Session, *, trading_date: date | None = None) -> dict[str, Any]:
        stmt = select(AiRun).order_by(AiRun.id.asc())
        if trading_date:
            stmt = stmt.where(AiRun.trading_date == trading_date)
        runs = list(session.scalars(stmt))
        grouped: dict[int, dict[str, Any]] = {}
        for run in runs:
            bucket = grouped.setdefault(
                run.skill_id,
                {"skill_id": run.skill_id, "skill_name": self._skill_name_map(session).get(run.skill_id), "run_count": 0, "pick_count": 0, "positive_outcomes": 0},
            )
            bucket["run_count"] += 1
            picks = list(session.scalars(select(AiPick).where(AiPick.run_id == run.id)))
            bucket["pick_count"] += len(picks)
            for pick in picks:
                outcomes = list(session.scalars(select(AiPickOutcome).where(AiPickOutcome.pick_id == pick.id)))
                bucket["positive_outcomes"] += sum(1 for outcome in outcomes if (outcome.close_change_pct or 0) > 0)
        items = sorted(grouped.values(), key=lambda item: (item["pick_count"], item["run_count"]), reverse=True)
        return {"skills": items}

    def get_daily_overview(
        self,
        session: Session,
        *,
        trading_date: date,
        run_type: str | None = None,
    ) -> dict[str, Any]:
        today_recommendations = self._daily_recommendations(session, trading_date=trading_date, run_type=run_type)
        yesterday_followups = self._yesterday_followups(session, trading_date=trading_date, run_type=run_type)
        daily_review = self.get_trading_day_review(session, trading_date)
        experience_cards = self._experience_cards(session, trading_date=trading_date)
        ops_summary = self._ops_summary(session, trading_date=trading_date, run_type=run_type)
        return {
            "summary": {
                "trading_date": trading_date.isoformat(),
                "today_pick_count": len(today_recommendations),
                "yesterday_followup_count": len(yesterday_followups),
                "experience_count": len(experience_cards),
                "ops_summary": ops_summary,
            },
            "today_recommendations": today_recommendations,
            "yesterday_followups": yesterday_followups,
            "daily_review": daily_review,
            "experience_cards": experience_cards,
        }

    def get_trading_day_review(self, session: Session, trading_date: date) -> dict[str, Any]:
        row = session.scalar(select(AiTradingDayReview).where(AiTradingDayReview.trading_date == trading_date))
        if row is None:
            return {
                "trading_date": trading_date.isoformat(),
                "market_summary": {},
                "market_breadth": {},
                "top_themes": [],
                "failed_patterns": [],
                "recommended_picks_review": [],
                "position_review": [],
                "lesson_items": [],
                "next_day_focus": [],
            }
        return {
            "trading_date": trading_date.isoformat(),
            "market_summary": self._loads_json(row.market_summary_json, {}),
            "market_breadth": self._loads_json(row.market_breadth_json, {}),
            "top_themes": self._loads_json(row.top_themes_json, []),
            "failed_patterns": self._loads_json(row.failed_patterns_json, []),
            "recommended_picks_review": self._loads_json(row.recommended_picks_review_json, []),
            "position_review": self._loads_json(row.position_review_json, []),
            "lesson_items": self._loads_json(row.lesson_items_json, []),
            "next_day_focus": self._loads_json(row.next_day_focus_json, []),
        }

    def get_job_history(self, session: Session, job_id: int) -> dict[str, Any]:
        job = session.get(AiJob, job_id)
        if job is None:
            raise ValueError("job not found")
        runs = list(session.scalars(select(AiRun).where(AiRun.job_id == job_id).order_by(desc(AiRun.started_at), desc(AiRun.id))))
        outcome_values = []
        for run in runs:
            for pick in session.scalars(select(AiPick).where(AiPick.run_id == run.id)):
                for outcome in session.scalars(select(AiPickOutcome).where(AiPickOutcome.pick_id == pick.id)):
                    if outcome.close_change_pct is not None:
                        outcome_values.append(outcome.close_change_pct)
        push_success = sum(1 for run in runs if self._loads_json(run.push_payload_json, {}).get("status") == "sent")
        return {
            "job": {
                "id": job.id,
                "name": job.name,
                "job_type": job.job_type,
                "display_group": job.display_group,
                "active_revision_id": job.active_revision_id,
            },
            "summary": {
                "run_count": len(runs),
                "success_count": sum(1 for run in runs if run.status == "success"),
                "push_success_count": push_success,
                "positive_outcome_count": sum(1 for value in outcome_values if value > 0),
            },
            "runs": [self.get_run(session, run.id) for run in runs],
        }

    def get_skill_performance(self, session: Session, skill_id: int) -> dict[str, Any]:
        skill = session.get(AiSkill, skill_id)
        if skill is None:
            raise ValueError("skill not found")
        revisions = list(session.scalars(select(AiSkillRevision).where(AiSkillRevision.skill_id == skill_id).order_by(AiSkillRevision.revision_no.asc())))
        items = []
        for revision in revisions:
            runs = list(session.scalars(select(AiRun).where(AiRun.skill_id == skill_id, AiRun.revision_id == revision.id)))
            close_changes = []
            pick_count = 0
            for run in runs:
                for pick in session.scalars(select(AiPick).where(AiPick.run_id == run.id)):
                    pick_count += 1
                    for outcome in session.scalars(select(AiPickOutcome).where(AiPickOutcome.pick_id == pick.id)):
                        if outcome.close_change_pct is not None:
                            close_changes.append(outcome.close_change_pct)
            items.append(
                {
                    "revision_id": revision.id,
                    "revision_no": revision.revision_no,
                    "title": revision.title,
                    "status": revision.status,
                    "run_count": len(runs),
                    "pick_count": pick_count,
                    "positive_count": sum(1 for value in close_changes if value > 0),
                    "average_close_change_pct": round(sum(close_changes) / len(close_changes), 4) if close_changes else None,
                }
            )
        return {"skill": {"id": skill.id, "name": skill.name}, "revisions": items}

    def compute_pending_outcomes(self, session: Session, *, trading_date: date | None = None) -> dict[str, int]:
        stmt = select(AiPick).order_by(AiPick.id.asc())
        if trading_date:
            stmt = stmt.where(AiPick.trading_date == trading_date)
        picks = list(session.scalars(stmt))
        updated = 0
        for pick in picks:
            updated += self.compute_pick_outcomes(session, pick)
        session.commit()
        return {"updated": updated}

    def scan_import_directory(self, session: Session, *, inbox_dir: Path, processed_dir: Path) -> dict[str, int]:
        inbox = Path(inbox_dir)
        processed = Path(processed_dir)
        processed.mkdir(parents=True, exist_ok=True)
        imported = 0
        failed = 0
        for file_path in sorted(inbox.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                self.import_run(session, payload)
                shutil.move(str(file_path), processed / file_path.name)
                imported += 1
            except Exception:
                session.rollback()
                failed += 1
        return {"imported": imported, "failed": failed}

    def compute_pick_outcomes(self, session: Session, pick: AiPick) -> int:
        history = self._stock_history(pick.stock_code)
        if len(history) < 2:
            return 0
        base_index = next((index for index, row in enumerate(history) if row["date"] == pick.trading_date), None)
        if base_index is None:
            return 0
        created = 0
        base_close = history[base_index]["close"]
        for window, offset in (("T+1", 1), ("T+3", 3)):
            if session.scalar(select(AiPickOutcome.id).where(AiPickOutcome.pick_id == pick.id, AiPickOutcome.window == window)):
                continue
            target_index = base_index + offset
            if target_index >= len(history):
                continue
            span = history[base_index + 1 : target_index + 1]
            target = history[target_index]
            benchmark_change = self._benchmark_change(pick.trading_date, target["date"])
            close_change = self._percent(target["close"], base_close)
            outcome = AiPickOutcome(
                pick_id=pick.id,
                window=window,
                open_change_pct=self._percent(target["open"], base_close),
                close_change_pct=close_change,
                max_gain_pct=max(self._percent(day["high"], base_close) for day in span),
                max_drawdown_pct=min(self._percent(day["low"], base_close) for day in span),
                hit_limit_up=any(self._percent(day["high"], day["open"]) >= 9.5 for day in span if day["open"]),
                beat_benchmark=close_change is not None and benchmark_change is not None and close_change > benchmark_change,
                outcome_label="positive" if close_change is not None and close_change > 0 else "negative",
                computed_at=self.now_provider(),
            )
            session.add(outcome)
            created += 1
        return created

    def _extract_structured_picks(self, *, payload: dict[str, Any], result_payload: dict[str, Any], job_type: str) -> list[dict[str, Any]]:
        if job_type not in {"stock_pick", "stock_confirm"}:
            return []
        picks = result_payload.get("structured_picks") or payload.get("structured_picks") or []
        if not isinstance(picks, list):
            raise ValueError("structured_picks must be a list")
        return picks

    def _validate_stock_pick(self, item: dict[str, Any]) -> None:
        missing = [field for field in PICK_REQUIRED_FIELDS if item.get(field) in (None, "", [])]
        if missing:
            raise ValueError(f"structured_picks missing required fields: {', '.join(missing)}")

    def _demo_payload_for_job(
        self,
        *,
        job: AiJob,
        skill: AiSkill,
        revision: AiSkillRevision,
        trading_date: date,
        sequence: int,
    ) -> dict[str, Any]:
        stock_cards = self._demo_stock_cards()
        push_status = "failed" if sequence in {1, 6} else "sent"
        common = {
            "job_id": job.id,
            "job_name": job.name,
            "job_type": job.job_type,
            "skill_id": skill.id,
            "skill_name": skill.name,
            "revision_id": revision.id,
            "trading_date": trading_date.isoformat(),
            "run_type": "demo",
            "duration_ms": 600 + sequence * 85,
            "push": {
                "status": push_status,
                "channel": "demo-dashboard",
                "target": "ai-center-preview",
                "message": "acceptance preview seed",
            },
        }
        if job.job_type == "news_scan":
            return {
                **common,
                "summary": {"text": "盘前消息面整理完成，聚焦金融、算力和风险提示"},
                "raw_output": "盘前消息面挖掘：金融权重、AI 硬件和高位分歧风险。",
                "result_payload": {
                    "headline_items": [
                        {"title": "券商与银行权重共振", "sentiment": "positive"},
                        {"title": "算力链景气延续", "sentiment": "positive"},
                        {"title": "高位情绪股分歧加大", "sentiment": "risk"},
                    ],
                    "market_implications": [
                        "权重方向适合承接低吸而非追高",
                        "AI 硬件仍是高弹性主线",
                    ],
                    "watch_themes": ["银行", "券商", "AI 硬件", "机器人"],
                },
            }
        if job.job_type in {"stock_pick", "stock_confirm"}:
            picks = self._demo_picks_for_job(job.name, stock_cards)
            return {
                **common,
                "summary": {"text": f"{job.name} 输出 {len(picks)} 只候选股"},
                "raw_output": f"{job.name} demo output",
                "result_payload": {"structured_picks": picks},
                "structured_picks": picks,
            }
        if job.job_type == "day_review":
            review = self._demo_day_review_payload(job.name)
            return {
                **common,
                "summary": {"text": review["summary_text"]},
                "raw_output": f"{job.name} demo review",
                "result_payload": review["payload"],
            }
        if job.job_type == "position_review":
            payload = {
                "position_review": [
                    {"stock_code": "300308", "stock_name": "中际旭创", "action": "减仓", "reason": "冲高回落后未能持续放量"},
                    {"stock_code": "000001", "stock_name": "平安银行", "action": "持有", "reason": "权重承接稳定，板块仍有轮动预期"},
                ],
                "lesson_items": [
                    {"title": "午后不能回封的强势股降低隔夜优先级", "tag": "execution"},
                    {"title": "权重放量日更适合低吸确认而非追高", "tag": "risk-control"},
                ],
                "next_day_focus": ["关注银行持续性", "处理高开过大的 AI 硬件股"],
            }
            return {
                **common,
                "summary": {"text": "持仓复盘完成，2 持仓、2 条经验沉淀"},
                "raw_output": f"{job.name} demo position review",
                "result_payload": payload,
            }
        payload = {
            "market_summary": {"headline": "周度主线围绕金融与 AI 硬件轮动", "risk_prompt": "高位接力成功率下降"},
            "lesson_items": [
                {"title": "多任务共振的票更值得留在观察池", "tag": "pattern"},
                {"title": "周五缩量修复的题材隔夜要降低仓位", "tag": "risk"},
            ],
            "next_day_focus": ["优先看多任务共振标的", "弱化单一消息刺激票"],
        }
        return {
            **common,
            "summary": {"text": "周度经验汇总完成，沉淀 2 条规则"},
            "raw_output": f"{job.name} demo weekly review",
            "result_payload": payload,
        }

    @staticmethod
    def _demo_stock_cards() -> dict[str, dict[str, Any]]:
        return {
            "000001": {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "sector_name": "银行",
                "theme_tags": ["权重修复", "金融"],
                "capital_profile": {"net_inflow": 12.8, "main_force_signal": "strong", "turnover_rate": 2.6, "volume_ratio": 1.5},
            },
            "300308": {
                "stock_code": "300308",
                "stock_name": "中际旭创",
                "sector_name": "AI 硬件",
                "theme_tags": ["算力", "机构趋势"],
                "capital_profile": {"net_inflow": 18.6, "main_force_signal": "strong", "turnover_rate": 6.4, "volume_ratio": 2.3},
            },
            "600036": {
                "stock_code": "600036",
                "stock_name": "招商银行",
                "sector_name": "银行",
                "theme_tags": ["权重共振", "低位承接"],
                "capital_profile": {"net_inflow": 9.2, "main_force_signal": "positive", "turnover_rate": 1.9, "volume_ratio": 1.3},
            },
            "600678": {
                "stock_code": "600678",
                "stock_name": "四川金顶",
                "sector_name": "ST/壳资源",
                "theme_tags": ["ST 修复", "情绪套利"],
                "capital_profile": {"net_inflow": 4.7, "main_force_signal": "neutral", "turnover_rate": 9.8, "volume_ratio": 2.6},
            },
        }

    def _demo_picks_for_job(self, job_name: str, stock_cards: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        job_cards = {
            "09:26 集合竞价分析": [
                self._build_demo_pick(stock_cards["300308"], "confirm", "集合竞价量能显著放大", "集合竞价转强", 0.93, 1),
                self._build_demo_pick(stock_cards["000001"], "watch", "金融权重竞价承接稳定", "权重竞价承接", 0.81, 2),
            ],
            "09:40 弱转强-候选筛选": [
                self._build_demo_pick(stock_cards["300308"], "candidate", "早盘分歧后重新放量", "弱转强候选", 0.86, 1),
                self._build_demo_pick(stock_cards["600036"], "candidate", "低位权重出现放量修复", "弱转强候选", 0.74, 2),
            ],
            "10:05 弱转强-转强确认": [
                self._build_demo_pick(stock_cards["300308"], "strong_recommend", "分时回封确认，主线地位强化", "弱转强确认", 0.96, 1),
            ],
            "14:50 尾盘选股": [
                self._build_demo_pick(stock_cards["000001"], "watch", "尾盘承接稳定，次日有修复预期", "尾盘承接", 0.79, 1),
                self._build_demo_pick(stock_cards["600036"], "watch", "权重尾盘放量回升", "尾盘承接", 0.76, 2),
            ],
            "20:00 超短线盘后选股(v3)": [
                self._build_demo_pick(stock_cards["300308"], "watch", "盘后主线热度仍集中在算力", "盘后候选池", 0.88, 1),
                self._build_demo_pick(stock_cards["000001"], "candidate", "金融权重作为次日防守方向", "盘后候选池", 0.73, 2),
            ],
            "20:05 大象起舞选股": [
                self._build_demo_pick(stock_cards["000001"], "confirm", "大票共振，资金偏好防守+修复", "大票异动", 0.84, 1),
                self._build_demo_pick(stock_cards["600036"], "watch", "银行双核共振增强板块辨识度", "大票异动", 0.78, 2),
            ],
            "20:30 ST股挖掘": [
                self._build_demo_pick(stock_cards["600678"], "candidate", "ST 情绪修复但持续性一般", "ST 修复", 0.66, 1),
            ],
        }
        return job_cards.get(job_name, [])

    def _build_demo_pick(
        self,
        card: dict[str, Any],
        pick_level: str,
        reason_summary: str,
        signal_context: str,
        confidence_score: float,
        priority_rank: int,
    ) -> dict[str, Any]:
        risk_flags = ["高开过多"] if confidence_score >= 0.9 else ["板块分歧"] if confidence_score < 0.75 else ["需确认次日承接"]
        return {
            "stock_code": card["stock_code"],
            "stock_name": card["stock_name"],
            "pick_level": pick_level,
            "reason_summary": reason_summary,
            "reason_detail": [
                f"{card['sector_name']} 板块热度靠前",
                f"主力净流入 {card['capital_profile']['net_inflow']}",
                f"量比 {card['capital_profile']['volume_ratio']}，成交活跃",
            ],
            "sector_name": card["sector_name"],
            "theme_tags": card["theme_tags"],
            "capital_profile": card["capital_profile"],
            "signal_context": signal_context,
            "confidence_score": confidence_score,
            "risk_flags": risk_flags,
            "entry_hint": "观察分时回踩后的承接强弱，不做无脑追高",
            "priority_rank": priority_rank,
        }

    @staticmethod
    def _demo_day_review_payload(job_name: str) -> dict[str, Any]:
        if job_name == "12:00 早盘复盘":
            return {
                "summary_text": "早盘复盘完成，金融修复、算力分歧并存",
                "payload": {
                    "market_summary": {"headline": "指数早盘温和修复", "risk_prompt": "高位题材午后仍可能分歧"},
                    "market_breadth": {"up_count": 2890, "down_count": 1830, "limit_up_count": 41},
                    "top_themes": ["银行", "券商", "AI 硬件"],
                    "failed_patterns": ["高开低走的抱团票"],
                    "recommended_picks_review": [
                        {"stock_code": "300308", "stock_name": "中际旭创", "review": "竞价转强后保持强势"},
                    ],
                    "lesson_items": [{"title": "上午最强方向仍是权重与算力共振", "tag": "midday"}],
                    "next_day_focus": ["观察午后资金是否回流银行"],
                },
            }
        return {
            "summary_text": "超短线复盘完成，已汇总大盘、推荐效果与失败模式",
            "payload": {
                "market_summary": {"headline": "指数尾盘修复，权重托底明显", "risk_prompt": "情绪高位票炸板率仍偏高"},
                "market_breadth": {"up_count": 3276, "down_count": 1712, "limit_up_count": 68, "broken_board_rate": "23%"},
                "top_themes": ["银行", "AI 硬件", "机器人"],
                "failed_patterns": ["午后缩量回封失败", "单一消息刺激无跟风"],
                "recommended_picks_review": [
                    {"stock_code": "300308", "stock_name": "中际旭创", "review": "多任务共振，收盘仍维持强势", "close_change_pct": 4.8},
                    {"stock_code": "000001", "stock_name": "平安银行", "review": "权重承接稳健，尾盘表现优于指数", "close_change_pct": 1.6},
                ],
                "lesson_items": [
                    {"title": "多任务共振标的优先级明显高于单源命中", "tag": "pattern"},
                    {"title": "高位缩量反包如果没有板块跟随，隔夜要降级", "tag": "risk"},
                ],
                "next_day_focus": ["继续跟踪 300308", "留意金融权重是否扩散到券商"],
            },
        }
        if not isinstance(item.get("reason_detail"), list) or not item["reason_detail"]:
            raise ValueError("structured_picks missing required fields: reason_detail")

    def _upsert_trading_day_review(self, session: Session, *, trading_date: date, result_payload: dict[str, Any], job_type: str) -> None:
        row = session.scalar(select(AiTradingDayReview).where(AiTradingDayReview.trading_date == trading_date))
        if row is None:
            row = AiTradingDayReview(trading_date=trading_date)
            session.add(row)
            session.flush()

        if job_type == "day_review":
            row.market_summary_json = json.dumps(result_payload.get("market_summary") or {}, ensure_ascii=False)
            row.market_breadth_json = json.dumps(result_payload.get("market_breadth") or {}, ensure_ascii=False)
            row.top_themes_json = json.dumps(result_payload.get("top_themes") or [], ensure_ascii=False)
            row.failed_patterns_json = json.dumps(result_payload.get("failed_patterns") or [], ensure_ascii=False)
            row.recommended_picks_review_json = json.dumps(result_payload.get("recommended_picks_review") or [], ensure_ascii=False)
            row.lesson_items_json = json.dumps(result_payload.get("lesson_items") or [], ensure_ascii=False)
            row.next_day_focus_json = json.dumps(result_payload.get("next_day_focus") or [], ensure_ascii=False)
        elif job_type == "position_review":
            row.position_review_json = json.dumps(result_payload.get("position_review") or [], ensure_ascii=False)
            row.lesson_items_json = json.dumps(self._loads_json(row.lesson_items_json, []) + (result_payload.get("lesson_items") or []), ensure_ascii=False)
            row.next_day_focus_json = json.dumps(self._loads_json(row.next_day_focus_json, []) + (result_payload.get("next_day_focus") or []), ensure_ascii=False)
        elif job_type == "weekly_review":
            row.lesson_items_json = json.dumps(self._loads_json(row.lesson_items_json, []) + (result_payload.get("lesson_items") or []), ensure_ascii=False)

    def _stock_history(self, stock_code: str) -> list[dict[str, Any]]:
        start = (self.now_provider().date() - timedelta(days=30)).strftime("%Y%m%d")
        end = (self.now_provider().date() + timedelta(days=1)).strftime("%Y%m%d")
        frame = self.gateway.fetch_stock_daily_history(stock_code, start, end)
        rows = []
        for item in frame.to_dict(orient="records"):
            row_date = self._parse_date(self._first_present(item, ["date", "日期"]))
            if row_date is None:
                continue
            rows.append(
                {
                    "date": row_date,
                    "open": self._to_float(self._first_present(item, ["open", "开盘"])),
                    "close": self._to_float(self._first_present(item, ["close", "收盘"])),
                    "high": self._to_float(self._first_present(item, ["high", "最高"])),
                    "low": self._to_float(self._first_present(item, ["low", "最低"])),
                }
            )
        rows.sort(key=lambda item: item["date"])
        return rows

    def _benchmark_change(self, start_date: date, end_date: date) -> float | None:
        frame = self.gateway.fetch_market_index_history("sh000001", days=60)
        rows = []
        for item in frame.to_dict(orient="records"):
            row_date = self._parse_date(self._first_present(item, ["date", "日期"]))
            close_value = self._to_float(self._first_present(item, ["close", "收盘"]))
            if row_date is None or close_value is None:
                continue
            rows.append((row_date, close_value))
        rows.sort(key=lambda item: item[0])
        start_close = next((close for row_date, close in rows if row_date >= start_date), None)
        end_close = next((close for row_date, close in rows if row_date >= end_date), None)
        if start_close is None or end_close is None:
            return None
        return self._percent(end_close, start_close)

    def _aggregate_outcomes(self, session: Session, pick_ids: list[int]) -> list[dict[str, Any]]:
        if not pick_ids:
            return []
        outcomes = list(
            session.scalars(
                select(AiPickOutcome)
                .where(AiPickOutcome.pick_id.in_(pick_ids))
                .order_by(AiPickOutcome.window.asc(), AiPickOutcome.id.asc())
            )
        )
        grouped: dict[str, list[AiPickOutcome]] = defaultdict(list)
        for outcome in outcomes:
            grouped[outcome.window].append(outcome)
        items = []
        for window, bucket in grouped.items():
            close_values = [item.close_change_pct for item in bucket if item.close_change_pct is not None]
            items.append(
                {
                    "window": window,
                    "average_close_change_pct": round(sum(close_values) / len(close_values), 4) if close_values else None,
                    "positive_count": sum(1 for item in bucket if (item.close_change_pct or 0) > 0),
                }
            )
        return items

    def _daily_recommendations(
        self,
        session: Session,
        *,
        trading_date: date,
        run_type: str | None,
    ) -> list[dict[str, Any]]:
        picks_payload = self.list_picks(session, trading_date=trading_date, run_type=run_type)["items"]
        items = []
        for item in picks_payload:
            sources = item.get("sources") or []
            primary = sorted(
                sources,
                key=lambda source: (
                    self._pick_level_rank(source.get("pick_level")),
                    source.get("confidence_score") or 0.0,
                ),
                reverse=True,
            )[0] if sources else {}
            min_priority = min(
                (
                    self._pick_priority_for_source(session, source)
                    for source in sources
                    if self._pick_priority_for_source(session, source) is not None
                ),
                default=None,
            )
            items.append(
                {
                    "stock_code": item["stock_code"],
                    "stock_name": item["stock_name"],
                    "sector_name": item.get("sector_name"),
                    "pick_level": primary.get("pick_level"),
                    "reason_summary": primary.get("reason_summary"),
                    "signal_context": primary.get("signal_context"),
                    "capital_profile": primary.get("capital_profile") or {},
                    "risk_flags": primary.get("risk_flags") or [],
                    "experience_feedback": primary.get("experience_feedback") or {},
                    "source_tasks": sources,
                    "source_count": item.get("source_count", 0),
                    "priority_rank": min_priority,
                    "outcomes": item.get("outcomes") or [],
                }
            )
        items.sort(
            key=lambda item: (
                item.get("priority_rank") if item.get("priority_rank") is not None else 9999,
                -int(item.get("source_count") or 0),
                -self._pick_level_rank(item.get("pick_level")),
                item.get("stock_code") or "",
            )
        )
        return items

    def _yesterday_followups(
        self,
        session: Session,
        *,
        trading_date: date,
        run_type: str | None,
    ) -> list[dict[str, Any]]:
        previous_date = self._previous_pick_date(session, trading_date=trading_date, run_type=run_type)
        if previous_date is None:
            return []
        previous_picks = self.list_picks(session, trading_date=previous_date, run_type=run_type)["items"]
        review_payload = self.get_trading_day_review(session, trading_date)
        review_by_stock = {
            str(item.get("stock_code")): item
            for item in review_payload.get("recommended_picks_review") or []
            if item.get("stock_code")
        }
        items = []
        for item in previous_picks:
            sources = item.get("sources") or []
            primary = sources[0] if sources else {}
            metrics = self._followup_metrics_from_sources(session, sources)
            review_note = review_by_stock.get(item["stock_code"], {})
            if not metrics and not review_note:
                continue
            close_change = metrics.get("close_change_pct")
            if close_change is None and review_note.get("close_change_pct") is not None:
                close_change = self._to_float(review_note.get("close_change_pct"))
                metrics = {
                    **metrics,
                    "close_change_pct": close_change,
                }
            expectation_label = "符合预期"
            if close_change is not None and close_change >= 3:
                expectation_label = "超预期"
            elif close_change is not None and close_change < 0:
                expectation_label = "低于预期"
            items.append(
                {
                    "stock_code": item["stock_code"],
                    "stock_name": item["stock_name"],
                    "yesterday_reason_summary": primary.get("reason_summary"),
                    "today_metrics": metrics,
                    "expectation_label": expectation_label,
                    "attribution_summary": self._followup_attribution(metrics=metrics, review_note=review_note),
                    "source_tasks": sources,
                }
            )
        items.sort(
            key=lambda item: (
                self._expectation_rank(item["expectation_label"]),
                -(item["today_metrics"].get("close_change_pct") or -999.0),
                item["stock_code"],
            ),
            reverse=True,
        )
        return items

    def _experience_cards(self, session: Session, *, trading_date: date) -> list[dict[str, Any]]:
        rows = list(
            session.scalars(
                select(AiTradingDayReview).where(AiTradingDayReview.trading_date <= trading_date).order_by(AiTradingDayReview.trading_date.asc())
            )
        )
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            date_value = row.trading_date.isoformat()
            related_stocks = {
                str(item.get("stock_code"))
                for item in self._loads_json(row.recommended_picks_review_json, [])
                if item.get("stock_code")
            }
            for lesson in self._loads_json(row.lesson_items_json, []):
                title = str(lesson.get("title") or "").strip()
                if not title:
                    continue
                tag = str(lesson.get("tag") or "general").strip()
                key = (title, tag)
                bucket = grouped.setdefault(
                    key,
                    {
                        "title": title,
                        "tag": tag,
                        "hit_count": 0,
                        "last_seen_date": date_value,
                        "related_dates": [],
                        "related_examples": [],
                    },
                )
                bucket["hit_count"] += 1
                bucket["last_seen_date"] = date_value
                if date_value not in bucket["related_dates"]:
                    bucket["related_dates"].append(date_value)
                example = lesson.get("example") or lesson.get("note") or title
                if example not in bucket["related_examples"]:
                    bucket["related_examples"].append(example)
                for stock_code in sorted(related_stocks):
                    if stock_code not in bucket["related_examples"]:
                        bucket["related_examples"].append(stock_code)
        items = list(grouped.values())
        items.sort(key=lambda item: (item["hit_count"], item["last_seen_date"], item["title"]), reverse=True)
        return items

    def _ops_summary(self, session: Session, *, trading_date: date, run_type: str | None) -> dict[str, Any]:
        jobs = list(session.scalars(select(AiJob)))
        runs_stmt = select(AiRun).where(AiRun.trading_date == trading_date)
        if run_type:
            runs_stmt = runs_stmt.where(AiRun.run_type == run_type)
        runs = list(session.scalars(runs_stmt))
        run_by_job: dict[int, AiRun] = {}
        for run in sorted(runs, key=lambda item: (item.started_at or datetime.min, item.id), reverse=True):
            if run.job_id is not None and run.job_id not in run_by_job:
                run_by_job[run.job_id] = run
        success_count = sum(1 for run in run_by_job.values() if run.status == "success")
        failed_count = sum(1 for run in run_by_job.values() if run.status == "failed")
        return {
            "total_jobs": len(jobs),
            "executed_jobs": len(run_by_job),
            "success_jobs": success_count,
            "failed_jobs": failed_count,
            "pending_jobs": max(len(jobs) - len(run_by_job), 0),
        }

    def _pick_source_dict(self, session: Session, pick: AiPick) -> dict[str, Any]:
        run = session.get(AiRun, pick.run_id)
        skill = session.get(AiSkill, run.skill_id) if run else None
        revision = session.get(AiSkillRevision, run.revision_id) if run else None
        payload = self._pick_payload_for_run(run, pick.stock_code) if run else {}
        return {
            "pick_id": pick.id,
            "run_id": pick.run_id,
            "run_type": run.run_type if run else None,
            "skill_name": skill.name if skill else None,
            "revision_id": revision.id if revision else None,
            "revision_title": revision.title if revision else None,
            "reason_summary": pick.reason_summary,
            "confidence_score": pick.confidence_score,
            "tags": self._loads_json(pick.tags_json, []),
            "pick_level": payload.get("pick_level"),
            "signal_context": payload.get("signal_context"),
            "risk_flags": payload.get("risk_flags") or [],
            "capital_profile": payload.get("capital_profile") or {},
            "experience_feedback": payload.get("experience_feedback") or {},
        }

    def _pick_priority_for_source(self, session: Session, source: dict[str, Any]) -> int | None:
        pick_id = source.get("pick_id")
        if not pick_id:
            return None
        pick = session.get(AiPick, int(pick_id))
        return pick.priority_rank if pick else None

    def _followup_metrics_from_sources(self, session: Session, sources: list[dict[str, Any]]) -> dict[str, Any]:
        rows = []
        for source in sources:
            pick_id = source.get("pick_id")
            if not pick_id:
                continue
            outcome = session.scalar(
                select(AiPickOutcome).where(AiPickOutcome.pick_id == int(pick_id), AiPickOutcome.window == "T+1")
            )
            if outcome is not None:
                rows.append(outcome)
        if not rows:
            return {}
        return {
            "open_change_pct": self._average([row.open_change_pct for row in rows]),
            "close_change_pct": self._average([row.close_change_pct for row in rows]),
            "max_gain_pct": self._average([row.max_gain_pct for row in rows]),
            "max_drawdown_pct": self._average([row.max_drawdown_pct for row in rows]),
            "beat_benchmark": any(row.beat_benchmark is True for row in rows),
        }

    def _followup_attribution(self, *, metrics: dict[str, Any], review_note: dict[str, Any]) -> str:
        review_text = str(review_note.get("review") or review_note.get("effect") or "").strip()
        if review_text:
            return review_text
        close_change = metrics.get("close_change_pct")
        max_gain = metrics.get("max_gain_pct")
        if close_change is None:
            return "暂无次日结果，等待行情与复盘数据补齐"
        if close_change >= 3:
            return f"次日延续强势，收盘涨幅 {close_change:.2f}% ，说明昨日逻辑被市场确认"
        if close_change >= 0:
            return f"次日基本符合预期，盘中最高 {max_gain:.2f}% ，但收盘强度一般"
        return f"次日低于预期，收盘涨幅 {close_change:.2f}% ，需要回看竞价与承接是否失效"

    def _previous_pick_date(self, session: Session, *, trading_date: date, run_type: str | None) -> date | None:
        pick_stmt = select(AiPick.trading_date).where(AiPick.trading_date < trading_date)
        dates = sorted({item for item in session.scalars(pick_stmt)})
        if not dates:
            return None
        if not run_type:
            return dates[-1]
        allowed_run_ids = set(session.scalars(select(AiRun.id).where(AiRun.run_type == run_type)))
        filtered_dates = sorted(
            {
                pick.trading_date
                for pick in session.scalars(select(AiPick).where(AiPick.trading_date < trading_date))
                if pick.run_id in allowed_run_ids
            }
        )
        return filtered_dates[-1] if filtered_dates else None

    def _pick_dict(self, session: Session, pick: AiPick) -> dict[str, Any]:
        run = session.get(AiRun, pick.run_id)
        skill = session.get(AiSkill, run.skill_id) if run else None
        revision = session.get(AiSkillRevision, run.revision_id) if run else None
        payload = self._pick_payload_for_run(run, pick.stock_code) if run else {}
        outcomes = list(session.scalars(select(AiPickOutcome).where(AiPickOutcome.pick_id == pick.id).order_by(AiPickOutcome.window.asc())))
        return {
            "id": pick.id,
            "run_id": pick.run_id,
            "stock_code": pick.stock_code,
            "stock_name": pick.stock_name,
            "sector_name": pick.sector_name,
            "pick_type": pick.pick_type,
            "pick_level": payload.get("pick_level"),
            "signal_context": payload.get("signal_context"),
            "capital_profile": payload.get("capital_profile") or {},
            "risk_flags": payload.get("risk_flags") or [],
            "entry_hint": payload.get("entry_hint"),
            "experience_feedback": payload.get("experience_feedback") or {},
            "confidence_score": pick.confidence_score,
            "reason_summary": pick.reason_summary,
            "tags": self._loads_json(pick.tags_json, []),
            "priority_rank": pick.priority_rank,
            "skill_name": skill.name if skill else None,
            "revision_id": revision.id if revision else None,
            "revision_title": revision.title if revision else None,
            "outcomes": [
                {
                    "window": outcome.window,
                    "open_change_pct": outcome.open_change_pct,
                    "close_change_pct": outcome.close_change_pct,
                    "max_gain_pct": outcome.max_gain_pct,
                    "max_drawdown_pct": outcome.max_drawdown_pct,
                    "hit_limit_up": outcome.hit_limit_up,
                    "beat_benchmark": outcome.beat_benchmark,
                    "outcome_label": outcome.outcome_label,
                }
                for outcome in outcomes
            ],
        }

    def _pick_payload_for_run(self, run: AiRun | None, stock_code: str) -> dict[str, Any]:
        if run is None:
            return {}
        payload = self._loads_json(run.result_payload_json, {})
        for item in payload.get("structured_picks") or []:
            if str(item.get("stock_code") or "").strip() == stock_code:
                return item
        return {}

    def _rulepack_dict(
        self,
        session: Session,
        rulepack: AiExperienceRulepack,
        *,
        jobs: dict[int, AiJob] | None = None,
    ) -> dict[str, Any]:
        rules = list(
            session.scalars(
                select(AiExperienceRule)
                .where(AiExperienceRule.rulepack_id == rulepack.id)
                .order_by(AiExperienceRule.id.asc())
            )
        )
        attached_jobs = jobs or {job.id: job for job in session.scalars(select(AiJob))}
        active_job_ids = [job.id for job in attached_jobs.values() if job.active_rulepack_id == rulepack.id]
        return {
            "id": rulepack.id,
            "name": rulepack.name,
            "scope": rulepack.scope,
            "status": rulepack.status,
            "source_trading_date": rulepack.source_trading_date.isoformat() if rulepack.source_trading_date else None,
            "summary": self._loads_json(rulepack.summary_json, {}),
            "rule_count": len(rules),
            "active_job_ids": active_job_ids,
            "rules": [
                {
                    "id": rule.id,
                    "title": rule.title,
                    "tag": rule.tag,
                    "direction": rule.direction,
                    "weight": rule.weight,
                    "match": self._loads_json(rule.match_json, {}),
                    "evidence": self._loads_json(rule.evidence_json, {}),
                }
                for rule in rules
            ],
            "created_at": rulepack.created_at.isoformat() if rulepack.created_at else None,
        }

    def _build_rules_from_lessons(self, lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for lesson in lessons:
            title = str(lesson.get("title") or "").strip()
            if not title:
                continue
            match = lesson.get("match") if isinstance(lesson.get("match"), dict) else {}
            if not match:
                continue
            direction = str(lesson.get("direction") or "boost")
            weight = self._to_float(lesson.get("weight")) or 1.0
            items.append(
                {
                    "title": title,
                    "tag": str(lesson.get("tag") or "general"),
                    "direction": direction,
                    "weight": weight,
                    "match": match,
                    "evidence": {
                        "note": lesson.get("note"),
                        "example": lesson.get("example"),
                    },
                }
            )
        return items

    @staticmethod
    def _review_dict(note: AiReviewNote) -> dict[str, Any]:
        return {
            "id": note.id,
            "pick_id": note.pick_id,
            "window": note.window,
            "review_text": note.review_text,
            "review_tags": AiCenterService._loads_json(note.review_tags_json, []),
            "is_expectation_met": note.is_expectation_met,
            "failure_reason": note.failure_reason,
            "improvement_hint": note.improvement_hint,
            "created_at": note.created_at.isoformat() if note.created_at else None,
        }

    @staticmethod
    def _revision_dict(revision: AiSkillRevision) -> dict[str, Any]:
        return {
            "id": revision.id,
            "skill_id": revision.skill_id,
            "revision_no": revision.revision_no,
            "title": revision.title,
            "content_text": revision.content_text,
            "config": AiCenterService._loads_json(revision.config_json, {}),
            "change_note": revision.change_note,
            "status": revision.status,
            "created_at": revision.created_at.isoformat() if revision.created_at else None,
        }

    @staticmethod
    def _loads_json(value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _first_present(item: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if item.get(key) not in (None, ""):
                return item.get(key)
        return None

    def _find_skill(self, session: Session, payload: dict[str, Any]) -> AiSkill | None:
        if payload.get("skill_id"):
            return session.get(AiSkill, int(payload["skill_id"]))
        if payload.get("skill_name"):
            return session.scalar(select(AiSkill).where(AiSkill.name == str(payload["skill_name"])))
        return None

    def _find_revision(self, session: Session, *, skill_id: int, payload: dict[str, Any]) -> AiSkillRevision | None:
        if payload.get("revision_id"):
            revision = session.get(AiSkillRevision, int(payload["revision_id"]))
            if revision and revision.skill_id == skill_id:
                return revision
            return None
        if payload.get("revision_no"):
            return session.scalar(
                select(AiSkillRevision).where(AiSkillRevision.skill_id == skill_id, AiSkillRevision.revision_no == int(payload["revision_no"]))
            )
        if payload.get("job_name"):
            job = session.scalar(select(AiJob).where(AiJob.name == str(payload["job_name"])))
            if job and job.active_revision_id:
                return session.get(AiSkillRevision, job.active_revision_id)
        return None

    def _find_job(self, session: Session, payload: dict[str, Any], skill_id: int) -> AiJob | None:
        if payload.get("job_id"):
            job = session.get(AiJob, int(payload["job_id"]))
            return job if job and job.skill_id == skill_id else None
        if payload.get("job_name"):
            return session.scalar(select(AiJob).where(AiJob.name == str(payload["job_name"]), AiJob.skill_id == skill_id))
        return None

    def _demote_active_revisions(self, session: Session, skill_id: int) -> None:
        revisions = list(session.scalars(select(AiSkillRevision).where(AiSkillRevision.skill_id == skill_id, AiSkillRevision.status == "active")))
        for revision in revisions:
            revision.status = "archived"

    def _latest_run_map(self, session: Session) -> dict[int, dict[str, Any]]:
        runs = list(session.scalars(select(AiRun).order_by(desc(AiRun.started_at), desc(AiRun.id))))
        latest: dict[int, dict[str, Any]] = {}
        for run in runs:
            if run.job_id is None or run.job_id in latest:
                continue
            latest[run.job_id] = {
                "run_id": run.id,
                "status": run.status,
                "trading_date": run.trading_date.isoformat(),
                "headline": self._loads_json(run.structured_summary_json, {}).get("headline"),
                "push_status": self._loads_json(run.push_payload_json, {}).get("status"),
            }
        return latest

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        text = str(value).strip().replace("/", "-")
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _percent(value: float | None, base: float | None) -> float | None:
        if value is None or base in (None, 0):
            return None
        return round(((value - base) / base) * 100, 4)

    @staticmethod
    def _average(values: list[float | None]) -> float | None:
        items = [value for value in values if value is not None]
        if not items:
            return None
        return round(sum(items) / len(items), 4)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("%", "").replace(",", "").strip())
        except ValueError:
            return None

    def _skill_name_map(self, session: Session) -> dict[int, str]:
        return {item.id: item.name for item in session.scalars(select(AiSkill))}

    def _revision_title_map(self, session: Session) -> dict[int, str]:
        return {item.id: item.title for item in session.scalars(select(AiSkillRevision))}

    def _rulepack_name_map(self, session: Session) -> dict[int, str]:
        return {item.id: item.name for item in session.scalars(select(AiExperienceRulepack))}

    @staticmethod
    def _pick_level_rank(value: Any) -> int:
        mapping = {
            "candidate": 1,
            "watch": 2,
            "confirm": 3,
            "strong_recommend": 4,
        }
        return mapping.get(str(value or ""), 0)

    @staticmethod
    def _expectation_rank(value: str) -> int:
        mapping = {
            "超预期": 3,
            "符合预期": 2,
            "低于预期": 1,
        }
        return mapping.get(value, 0)
