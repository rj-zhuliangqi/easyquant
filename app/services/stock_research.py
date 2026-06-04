from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
import json
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiJob
from app.models import AiExperienceRule
from app.models import AiExperienceRulepack
from app.models import AiSkill
from app.models import AiSkillRevision
from app.models import AiStockResearchItem
from app.models import AiStockResearchRun
from app.services.ai_center import AiCenterService


@dataclass
class ResearchCandidate:
    stock_code: str
    stock_name: str
    sector_name: str | None
    latest_price: float | None
    change_percent: float | None
    net_amount: float | None
    rank_score: float
    confidence_score: float
    reason_summary: str
    reason_detail: list[str]
    theme_tags: list[str]
    signal_context: str
    risk_flags: list[str]
    entry_hint: str
    capital_profile: dict[str, Any]
    experience_feedback: dict[str, Any] | None = None


class StockResearchService:
    def __init__(self, *, gateway: Any, now_provider: Any | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now
        self.ai_center = AiCenterService(gateway=gateway, now_provider=self.now_provider)

    def run(
        self,
        session: Session,
        *,
        trading_date: date,
        limit: int = 5,
        mode: str = "flow-momentum",
        skill_name: str = "stock-research",
        revision_title: str = "stock-research v1",
        job_name: str = "15:00 stock-research",
    ) -> dict[str, Any]:
        started_at = self.now_provider()
        research_run = AiStockResearchRun(
            skill_name=skill_name,
            revision_title=revision_title,
            job_name=job_name,
            trading_date=trading_date,
            mode=mode,
            status="running",
            candidate_limit=limit,
            config_json=json.dumps({"mode": mode, "limit": limit}, ensure_ascii=False),
            started_at=started_at,
        )
        session.add(research_run)
        session.flush()

        try:
            candidates = self._build_candidates(limit=limit)
            summary = self._persist_candidates(
                session,
                research_run_id=research_run.id,
                trading_date=trading_date,
                candidates=candidates,
            )
            skill, revision, job = self._ensure_ai_metadata(
                session,
                skill_name=skill_name,
                revision_title=revision_title,
                job_name=job_name,
            )
            candidates = self._apply_experience_rulepack(session, candidates=candidates, job=job)
            imported = self.ai_center.import_run(
                session,
                self._build_import_payload(
                    trading_date=trading_date,
                    candidates=candidates,
                    skill=skill,
                    revision=revision,
                    job=job,
                    summary=summary,
                    started_at=started_at,
                ),
            )
            research_run.status = "success"
            research_run.finished_at = self.now_provider()
            research_run.summary_json = json.dumps(summary, ensure_ascii=False)
            research_run.raw_output_text = self._render_raw_output(candidates)
            research_run.ai_run_id = imported["run"]["id"]
            session.add(research_run)
            session.commit()
            return {
                "research_run_id": research_run.id,
                "ai_run_id": research_run.ai_run_id,
                "candidate_count": len(candidates),
                "top_stock_codes": [item.stock_code for item in candidates],
                "summary": summary,
            }
        except Exception as exc:
            session.rollback()
            with session.begin():
                failed_run = session.get(AiStockResearchRun, research_run.id)
                if failed_run is not None:
                    failed_run.status = "failed"
                    failed_run.finished_at = self.now_provider()
                    failed_run.error_text = str(exc)
            raise

    def _build_candidates(self, *, limit: int) -> list[ResearchCandidate]:
        frame = self.gateway.fetch_individual_realtime().fillna("")
        snapshot = self.gateway.get_source_snapshot("individual_realtime") if hasattr(self.gateway, "get_source_snapshot") else {}
        source_label = snapshot.get("source_label")
        candidates: list[ResearchCandidate] = []
        seen_codes: set[str] = set()

        for row in frame.to_dict(orient="records"):
            stock_code = self._normalize_stock_code(self._first_present(row, ["stock_code", "code", "股票代码"]))
            stock_name = self._clean_text(self._first_present(row, ["stock_name", "name", "股票简称"]))
            if not stock_code or not stock_name or stock_code in seen_codes:
                continue
            seen_codes.add(stock_code)

            latest_price = self._to_float(self._first_present(row, ["latest_price", "price", "最新价"]))
            change_percent = self._to_float(self._first_present(row, ["change_percent", "涨跌幅"]))
            net_amount = self._to_float(self._first_present(row, ["net_amount", "净额"]))
            sector_name = self._clean_text(self._first_present(row, ["sector_name", "所属板块"])) or None

            rank_score = round((net_amount or 0.0) * 0.7 + (change_percent or 0.0) * 0.3, 4)
            confidence_score = round(min(max(rank_score / 20.0, 0.1), 0.99), 4)
            theme_tags = self._build_theme_tags(change_percent=change_percent, net_amount=net_amount, source_label=source_label)
            reason_summary = self._build_reason_summary(change_percent=change_percent, net_amount=net_amount)
            reason_detail = self._build_reason_detail(
                latest_price=latest_price,
                change_percent=change_percent,
                net_amount=net_amount,
                sector_name=sector_name,
            )
            signal_context = self._build_signal_context(change_percent=change_percent, net_amount=net_amount)
            risk_flags = self._build_risk_flags(change_percent=change_percent, net_amount=net_amount)
            entry_hint = self._build_entry_hint(latest_price=latest_price, change_percent=change_percent)
            capital_profile = self._build_capital_profile(change_percent=change_percent, net_amount=net_amount)

            candidates.append(
                ResearchCandidate(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    sector_name=sector_name,
                    latest_price=latest_price,
                    change_percent=change_percent,
                    net_amount=net_amount,
                    rank_score=rank_score,
                    confidence_score=confidence_score,
                    reason_summary=reason_summary,
                    reason_detail=reason_detail,
                    theme_tags=theme_tags,
                    signal_context=signal_context,
                    risk_flags=risk_flags,
                    entry_hint=entry_hint,
                    capital_profile=capital_profile,
                )
            )

        candidates.sort(key=lambda item: (item.rank_score, item.net_amount or 0.0, item.change_percent or 0.0), reverse=True)
        return candidates[: max(limit, 0)]

    def _persist_candidates(
        self,
        session: Session,
        *,
        research_run_id: int,
        trading_date: date,
        candidates: list[ResearchCandidate],
    ) -> dict[str, Any]:
        snapshot = self.gateway.get_source_snapshot("individual_realtime") if hasattr(self.gateway, "get_source_snapshot") else {}
        for index, candidate in enumerate(candidates, start=1):
            session.add(
                AiStockResearchItem(
                    run_id=research_run_id,
                    trading_date=trading_date,
                    stock_code=candidate.stock_code,
                    stock_name=candidate.stock_name,
                    sector_name=candidate.sector_name,
                    latest_price=candidate.latest_price,
                    change_percent=candidate.change_percent,
                    net_amount=candidate.net_amount,
                    rank_score=candidate.rank_score,
                    confidence_score=candidate.confidence_score,
                    reason_summary=candidate.reason_summary,
                    tags_json=json.dumps(candidate.theme_tags, ensure_ascii=False),
                    source_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                    priority_rank=index,
                )
            )
        return {
            "candidate_count": len(candidates),
            "average_score": round(sum(item.rank_score for item in candidates) / len(candidates), 4) if candidates else None,
            "source_label": snapshot.get("source_label"),
        }

    def _ensure_ai_metadata(
        self,
        session: Session,
        *,
        skill_name: str,
        revision_title: str,
        job_name: str,
    ) -> tuple[AiSkill, AiSkillRevision, AiJob]:
        skill = session.scalar(select(AiSkill).where(AiSkill.name == skill_name))
        if skill is None:
            skill = AiSkill(name=skill_name, category="stock-pick", description="stock research pipeline")
            session.add(skill)
            session.flush()

        revision = session.scalar(
            select(AiSkillRevision).where(AiSkillRevision.skill_id == skill.id, AiSkillRevision.title == revision_title)
        )
        if revision is None:
            latest_no = session.scalar(select(func.max(AiSkillRevision.revision_no)).where(AiSkillRevision.skill_id == skill.id))
            revision = AiSkillRevision(
                skill_id=skill.id,
                revision_no=int(latest_no or 0) + 1,
                title=revision_title,
                content_text="Auto-generated stock research revision",
                config_json=json.dumps({"source": "stock_research_service"}, ensure_ascii=False),
                change_note="bootstrap stock research pipeline",
                status="active",
            )
            self._archive_revisions(session, skill.id)
            session.add(revision)
            session.flush()

        job = session.scalar(select(AiJob).where(AiJob.name == job_name, AiJob.skill_id == skill.id))
        if job is None:
            job = AiJob(
                name=job_name,
                schedule_label=job_name.split(" ", 1)[0] if " " in job_name else job_name,
                schedule_rrule_or_cron=None,
                skill_id=skill.id,
                active_revision_id=revision.id,
                job_type="stock_pick",
                result_schema_version="2.0",
                display_group="盘后",
                enabled=True,
            )
            session.add(job)
        else:
            job.active_revision_id = revision.id
            job.job_type = "stock_pick"
            job.result_schema_version = "2.0"
            job.display_group = "盘后"
        session.flush()
        return skill, revision, job

    def _build_import_payload(
        self,
        *,
        trading_date: date,
        candidates: list[ResearchCandidate],
        skill: AiSkill,
        revision: AiSkillRevision,
        job: AiJob,
        summary: dict[str, Any],
        started_at: datetime,
    ) -> dict[str, Any]:
        finished_at = self.now_provider()
        duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
        structured_picks: list[dict[str, Any]] = []
        for index, item in enumerate(candidates, start=1):
            structured_picks.append(
                {
                    "stock_code": item.stock_code,
                    "stock_name": item.stock_name,
                    "pick_level": "watch" if index > 1 else "strong_recommend",
                    "sector_name": item.sector_name or "未分类",
                    "reason_summary": item.reason_summary,
                    "reason_detail": item.reason_detail,
                    "theme_tags": item.theme_tags,
                    "capital_profile": item.capital_profile,
                    "signal_context": item.signal_context,
                    "confidence_score": item.confidence_score,
                    "risk_flags": item.risk_flags,
                    "entry_hint": item.entry_hint,
                    "priority_rank": index,
                    "pick_type": "stock-research",
                    "experience_feedback": item.experience_feedback or {},
                }
            )

        return {
            "job_id": job.id,
            "job_name": job.name,
            "job_type": "stock_pick",
            "skill_id": skill.id,
            "skill_name": skill.name,
            "revision_id": revision.id,
            "trading_date": trading_date.isoformat(),
            "run_type": "production",
            "summary": {
                "text": f"Generated {len(structured_picks)} stock research picks",
                "candidate_count": len(structured_picks),
                **summary,
            },
            "push": {
                "status": "not_sent",
                "target": "ai-center",
                "message": "research-only import",
            },
            "duration_ms": duration_ms,
            "raw_output": self._render_raw_output(candidates),
            "metadata": summary,
            "result_payload": {
                "structured_picks": structured_picks,
                "source_summary": summary,
            },
            "structured_picks": structured_picks,
        }

    @staticmethod
    def _archive_revisions(session: Session, skill_id: int) -> None:
        revisions = list(session.scalars(select(AiSkillRevision).where(AiSkillRevision.skill_id == skill_id)))
        for revision in revisions:
            if revision.status == "active":
                revision.status = "archived"

    @staticmethod
    def _build_theme_tags(*, change_percent: float | None, net_amount: float | None, source_label: str | None) -> list[str]:
        tags = ["stock-research"]
        if (change_percent or 0) >= 5:
            tags.append("momentum")
        if (net_amount or 0) >= 8:
            tags.append("main-flow")
        if source_label:
            tags.append(source_label)
        return tags

    @staticmethod
    def _build_reason_summary(*, change_percent: float | None, net_amount: float | None) -> str:
        change_text = f"涨幅 {change_percent:.2f}%" if change_percent is not None else "涨幅待补"
        net_text = f"净额 {net_amount:.2f}" if net_amount is not None else "净额待补"
        return f"{change_text}，{net_text}，资金与动量共振"

    @staticmethod
    def _build_reason_detail(
        *,
        latest_price: float | None,
        change_percent: float | None,
        net_amount: float | None,
        sector_name: str | None,
    ) -> list[str]:
        details = [
            f"最新价 {latest_price:.2f}" if latest_price is not None else "最新价待确认",
            f"当日涨幅 {change_percent:.2f}%" if change_percent is not None else "涨跌幅待确认",
            f"资金净额 {net_amount:.2f}" if net_amount is not None else "资金净额待确认",
        ]
        if sector_name:
            details.append(f"所属板块 {sector_name}")
        return details[:4]

    @staticmethod
    def _build_signal_context(*, change_percent: float | None, net_amount: float | None) -> str:
        if (change_percent or 0) >= 5 and (net_amount or 0) >= 8:
            return "资金放量共振"
        if (change_percent or 0) >= 3:
            return "价格动量走强"
        return "盘后候选观察"

    @staticmethod
    def _build_risk_flags(*, change_percent: float | None, net_amount: float | None) -> list[str]:
        risks: list[str] = []
        if (change_percent or 0) >= 8:
            risks.append("涨幅偏大")
        if (net_amount or 0) < 3:
            risks.append("资金强度一般")
        if not risks:
            risks.append("需结合次日承接确认")
        return risks

    @staticmethod
    def _build_entry_hint(*, latest_price: float | None, change_percent: float | None) -> str:
        if latest_price is None:
            return "优先观察次日竞价强弱与量能变化"
        if (change_percent or 0) >= 5:
            return f"关注 {latest_price:.2f} 附近承接，避免高开过度追涨"
        return f"观察 {latest_price:.2f} 上方放量突破后的持续性"

    @staticmethod
    def _build_capital_profile(*, change_percent: float | None, net_amount: float | None) -> dict[str, Any]:
        return {
            "net_inflow": net_amount,
            "main_force_signal": "strong" if (net_amount or 0) >= 8 else "neutral",
            "turnover_rate": None,
            "volume_ratio": round(max((change_percent or 0) / 2.0, 0.5), 2),
        }

    @staticmethod
    def _render_raw_output(candidates: list[ResearchCandidate]) -> str:
        if not candidates:
            return "No candidates generated."
        return "\n".join(
            f"{index}. {item.stock_code} {item.stock_name} score={item.rank_score:.4f} reason={item.reason_summary}"
            for index, item in enumerate(candidates, start=1)
        )

    def _apply_experience_rulepack(
        self,
        session: Session,
        *,
        candidates: list[ResearchCandidate],
        job: AiJob,
    ) -> list[ResearchCandidate]:
        if not job.active_rulepack_id:
            return candidates
        rulepack = session.get(AiExperienceRulepack, job.active_rulepack_id)
        if rulepack is None:
            return candidates
        rules = list(
            session.scalars(
                select(AiExperienceRule)
                .where(AiExperienceRule.rulepack_id == rulepack.id)
                .order_by(AiExperienceRule.id.asc())
            )
        )
        adjusted: list[ResearchCandidate] = []
        for candidate in candidates:
            total_delta = 0.0
            matched_rules: list[dict[str, Any]] = []
            for rule in rules:
                match = self.ai_center._loads_json(rule.match_json, {})
                if not self._rule_matches_candidate(match, candidate):
                    continue
                delta = abs(float(rule.weight or 0.0))
                if rule.direction == "penalize":
                    total_delta -= delta
                else:
                    total_delta += delta
                matched_rules.append(
                    {
                        "rule_id": rule.id,
                        "title": rule.title,
                        "tag": rule.tag,
                        "direction": rule.direction,
                        "weight": rule.weight,
                    }
                )
            feedback = {
                "rulepack_id": rulepack.id,
                "rulepack_name": rulepack.name,
                "matched_rule_count": len(matched_rules),
                "score_delta": round(total_delta, 4),
                "matched_rules": matched_rules,
            }
            adjusted.append(
                ResearchCandidate(
                    stock_code=candidate.stock_code,
                    stock_name=candidate.stock_name,
                    sector_name=candidate.sector_name,
                    latest_price=candidate.latest_price,
                    change_percent=candidate.change_percent,
                    net_amount=candidate.net_amount,
                    rank_score=round(candidate.rank_score + total_delta, 4),
                    confidence_score=candidate.confidence_score,
                    reason_summary=candidate.reason_summary,
                    reason_detail=candidate.reason_detail,
                    theme_tags=candidate.theme_tags,
                    signal_context=candidate.signal_context,
                    risk_flags=candidate.risk_flags,
                    entry_hint=candidate.entry_hint,
                    capital_profile=candidate.capital_profile,
                    experience_feedback=feedback,
                )
            )
        adjusted.sort(key=lambda item: (item.rank_score, item.net_amount or 0.0, item.change_percent or 0.0), reverse=True)
        return adjusted

    @staticmethod
    def _rule_matches_candidate(match: dict[str, Any], candidate: ResearchCandidate) -> bool:
        for key, expected in match.items():
            expected_values = expected if isinstance(expected, list) else [expected]
            expected_text = {str(item).strip() for item in expected_values if str(item).strip()}
            if not expected_text:
                continue
            if key == "theme_tags":
                if not expected_text.intersection({str(item).strip() for item in candidate.theme_tags}):
                    return False
            elif key == "risk_flags":
                if not expected_text.intersection({str(item).strip() for item in candidate.risk_flags}):
                    return False
            elif key == "signal_context":
                if str(candidate.signal_context).strip() not in expected_text:
                    return False
            elif key == "sector_name":
                if str(candidate.sector_name or "").strip() not in expected_text:
                    return False
        return True

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_stock_code(value: Any) -> str:
        text = str(value or "").strip()
        return text.zfill(6) if text.isdigit() else text

    @staticmethod
    def _first_present(row: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, "", "--"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").replace("%", "").strip())
        except ValueError:
            return None
