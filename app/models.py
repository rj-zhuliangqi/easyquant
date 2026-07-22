from datetime import date
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FundFlowSnapshot(Base):
    __tablename__ = "fund_flow_snapshots"
    __table_args__ = (
        Index("ix_fund_flow_type_captured", "sector_type", "captured_at"),
        Index("ix_fund_flow_type_name_captured", "sector_type", "sector_name", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    sector_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    inflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    outflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leading_stock: Mapped[str | None] = mapped_column(String(120), nullable=True)
    leading_stock_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    leading_stock_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class FundFlowDailyHistory(Base):
    __tablename__ = "fund_flow_daily_history"
    __table_args__ = (
        UniqueConstraint("sector_type", "sector_name", "trading_date", name="uq_sector_day"),
        Index("ix_daily_history_type_name_date", "sector_type", "sector_name", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    main_net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)


class SectorStockSnapshot(Base):
    __tablename__ = "sector_stock_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "sector_type",
            "sector_name",
            "trading_date",
            "captured_at",
            "stock_code",
            name="uq_sector_stock_snapshot",
        ),
        Index("ix_sector_stock_type_name_date_time", "sector_type", "sector_name", "trading_date", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class IndividualStockSnapshot(Base):
    __tablename__ = "individual_stock_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trading_date",
            "captured_at",
            "stock_code",
            name="uq_individual_stock_snapshot",
        ),
        Index("ix_individual_stock_date_time", "trading_date", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class WatchedSector(Base):
    __tablename__ = "watched_sectors"
    __table_args__ = (UniqueConstraint("sector_type", "sector_name", name="uq_watched_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class WatchedStock(Base):
    __tablename__ = "watched_stocks"
    __table_args__ = (UniqueConstraint("stock_code", name="uq_watched_stock_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    sector_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    watch_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class WorkspaceNote(Base):
    __tablename__ = "workspace_notes"
    __table_args__ = (
        Index("ix_workspace_note_subject", "subject_type", "subject_key", "created_at"),
        Index("ix_workspace_note_trading_date", "trading_date", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    subject_type: Mapped[str] = mapped_column(String(20), index=True)
    subject_key: Mapped[str] = mapped_column(String(80), index=True)
    content: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class AiStockResearchRun(Base):
    __tablename__ = "ai_stock_research_runs"
    __table_args__ = (
        Index("ix_ai_stock_research_runs_date_status", "trading_date", "status"),
        Index("ix_ai_stock_research_runs_skill_started", "skill_name", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(120), index=True)
    revision_title: Mapped[str] = mapped_column(String(200))
    job_name: Mapped[str] = mapped_column(String(120))
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(40), default="flow-momentum")
    status: Mapped[str] = mapped_column(String(40), default="running")
    candidate_limit: Mapped[int] = mapped_column(Integer, default=5)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_run_id: Mapped[int | None] = mapped_column(ForeignKey("ai_runs.id"), nullable=True, index=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AiStockResearchItem(Base):
    __tablename__ = "ai_stock_research_items"
    __table_args__ = (
        UniqueConstraint("run_id", "stock_code", name="uq_ai_stock_research_item_run_stock"),
        Index("ix_ai_stock_research_items_run_rank", "run_id", "priority_rank"),
        Index("ix_ai_stock_research_items_date_stock", "trading_date", "stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ai_stock_research_runs.id"), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    sector_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiSkill(Base):
    __tablename__ = "ai_skills"
    __table_args__ = (UniqueConstraint("name", name="uq_ai_skill_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40), default="general")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiSkillRevision(Base):
    __tablename__ = "ai_skill_revisions"
    __table_args__ = (
        UniqueConstraint("skill_id", "revision_no", name="uq_ai_skill_revision_no"),
        Index("ix_ai_skill_revision_skill_status", "skill_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    content_text: Mapped[str] = mapped_column(Text)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiJob(Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (UniqueConstraint("name", name="uq_ai_job_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    schedule_label: Mapped[str] = mapped_column(String(40))
    schedule_rrule_or_cron: Mapped[str | None] = mapped_column(String(120), nullable=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), index=True)
    active_revision_id: Mapped[int | None] = mapped_column(ForeignKey("ai_skill_revisions.id"), nullable=True)
    active_rulepack_id: Mapped[int | None] = mapped_column(ForeignKey("ai_experience_rulepacks.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(40), default="stock_pick")
    result_schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    display_group: Mapped[str] = mapped_column(String(20), default="盘中")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    engine_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    engine_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiSkillTemplate(Base):
    """Skill 执行模板 — 不同引擎（claude-code/goose/custom）的 prompt 模板和配置"""
    __tablename__ = "ai_skill_templates"
    __table_args__ = (
        Index("ix_ai_skill_templates_skill_active", "skill_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), index=True)
    template_type: Mapped[str] = mapped_column(String(40))
    prompt_template: Mapped[str] = mapped_column(Text)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiBacktestBatch(Base):
    __tablename__ = "ai_backtest_batches"
    __table_args__ = (Index("ix_ai_backtest_batches_skill_created", "skill_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("ai_skill_revisions.id"), index=True)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_trading_date_type", "trading_date", "run_type"),
        Index("ix_ai_runs_skill_revision_date", "skill_id", "revision_id", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("ai_jobs.id"), nullable=True, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("ai_skills.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("ai_skill_revisions.id"), index=True)
    backtest_batch_id: Mapped[int | None] = mapped_column(ForeignKey("ai_backtest_batches.id"), nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String(20), default="production")
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success")
    source_input_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    push_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    engine_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiRunArtifact(Base):
    """Run 的中间产物存储 — 数据快照、图表、分析日志等"""
    __tablename__ = "ai_run_artifacts"
    __table_args__ = (
        Index("ix_ai_run_artifacts_run_type", "run_id", "artifact_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ai_runs.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiTradingDayReview(Base):
    __tablename__ = "ai_trading_day_reviews"
    __table_args__ = (UniqueConstraint("trading_date", name="uq_ai_trading_day_review_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    market_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_breadth_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_themes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_patterns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_picks_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_day_focus_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class AiExperienceRulepack(Base):
    __tablename__ = "ai_experience_rulepacks"
    __table_args__ = (
        Index("ix_ai_experience_rulepacks_scope_status", "scope", "status"),
        Index("ix_ai_experience_rulepacks_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    scope: Mapped[str] = mapped_column(String(40), default="stock_pick")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    source_trading_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiExperienceRule(Base):
    __tablename__ = "ai_experience_rules"
    __table_args__ = (
        Index("ix_ai_experience_rules_rulepack", "rulepack_id", "tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rulepack_id: Mapped[int] = mapped_column(ForeignKey("ai_experience_rulepacks.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    tag: Mapped[str] = mapped_column(String(60), default="general")
    direction: Mapped[str] = mapped_column(String(20), default="boost")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    match_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiPick(Base):
    __tablename__ = "ai_picks"
    __table_args__ = (
        Index("ix_ai_picks_trading_stock", "trading_date", "stock_code"),
        Index("ix_ai_picks_run_priority", "run_id", "priority_rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ai_runs.id"), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    sector_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pick_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pick_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    capital_profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    risk_flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    theme_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AiPickOutcome(Base):
    __tablename__ = "ai_pick_outcomes"
    __table_args__ = (
        UniqueConstraint("pick_id", "window", name="uq_ai_pick_outcome_window"),
        Index("ix_ai_pick_outcomes_window", "window", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pick_id: Mapped[int] = mapped_column(ForeignKey("ai_picks.id"), index=True)
    window: Mapped[str] = mapped_column(String(10))
    open_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_gain_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_limit_up: Mapped[bool] = mapped_column(Boolean, default=False)
    beat_benchmark: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AiReviewNote(Base):
    __tablename__ = "ai_review_notes"
    __table_args__ = (Index("ix_ai_review_notes_pick_window", "pick_id", "window", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pick_id: Mapped[int] = mapped_column(ForeignKey("ai_picks.id"), index=True)
    window: Mapped[str] = mapped_column(String(10))
    review_text: Mapped[str] = mapped_column(Text)
    review_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_expectation_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    improvement_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class NewsItem(Base):
    """实时资讯条目 — 由 news_service 每 5 分钟从东财/同花顺/新浪轮询入库。

    去重策略两层：
    1. `(source, source_id)` 联合唯一约束 — 同源硬去重；
    2. `title_hash` (sha1(normalize(title))[:40]) — 跨源软去重，30 分钟内同
       title 视为同一新闻，由 NewsService 在入库前判断。
    """

    __tablename__ = "news_items"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_news_item_source"),
        Index("ix_news_items_published", "published_at"),
        Index("ix_news_items_importance_published", "importance_level", "published_at"),
        Index("ix_news_items_title_hash", "title_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 数据源标识：eastmoney_724 / ths_live / sina_roll
    source: Mapped[str] = mapped_column(String(20))
    # 源侧唯一 ID（东财 code、同花顺 seq、新浪 docurl 的 sha1[:16]）
    source_id: Mapped[str] = mapped_column(String(80))
    # 标题归一化后的 sha1[:40]，跨源去重用
    title_hash: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(String(800), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # 0=普通 1=单命中（行为或行业） 2=双命中（行为+行业，置顶）
    importance_level: Mapped[int] = mapped_column(Integer, default=0)
    # 命中关键词，JSON 序列化的字符串数组，前端 hover 展示
    matched_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 受影响个股 — v1 留口，仅当源给了股票代码时才填
    affected_stocks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    # 原始单条响应，便于排错；可后续归档
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class StockDailyBar(Base):
    """个股日线 OHLCV（选股器本地库）。

    价格为**前复权**口径（amount/volume/turnover_rate 为原始值）。数据时点为本地
    交易日；``ensure_recent_bars`` 串行从 akshare 拉取并按 (code, date) 唯一 upsert。
    """

    __tablename__ = "stock_daily_bars"
    __table_args__ = (
        UniqueConstraint("stock_code", "trading_date", name="uq_stock_daily_bars_code_date"),
        Index("ix_stock_daily_bars_code_date", "stock_code", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class StockFundFlowDaily(Base):
    """个股每日主力资金流向（东财口径）。

    与 ``stock_daily_bars`` 通过 ``(stock_code, trading_date)`` 关联；用于筛选器
    资金类条件。数据完整度可低于日线表，缺失时按 v2 文档降级处理。
    """

    __tablename__ = "stock_fund_flow_daily"
    __table_args__ = (
        UniqueConstraint("stock_code", "trading_date", name="uq_stock_flow_code_date"),
        Index("ix_stock_flow_code_date", "stock_code", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    main_net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    super_large_net: Mapped[float | None] = mapped_column(Float, nullable=True)
    large_net: Mapped[float | None] = mapped_column(Float, nullable=True)


class ScreenerPreset(Base):
    """选股器预设（6 套内置 + 用户自定义）。"""

    __tablename__ = "screener_presets"
    __table_args__ = (
        UniqueConstraint("name", name="uq_screener_preset_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conditions_json: Mapped[str] = mapped_column(Text)
    universe_json: Mapped[str] = mapped_column(Text, default="{}")
    order_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    order: Mapped[str] = mapped_column(String(10), default="desc")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # 2026-07-22 选股器重构：策略分类 + 评分模式（match_mode: all/any/score）
    category: Mapped[str] = mapped_column(String(40), default="量价突破")
    match_mode: Mapped[str] = mapped_column(String(10), default="all")
    min_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


# ====================================================================
# 持久化层 v1：拉取数据 → 落库 → 派生指标 (2026-07-21)
# 4 张新表：
#   - stock_realtime_eod        : 每只股票每个交易日的 EOD 聚合（替代实时 merge）
#   - stock_indicators_daily    : 预计算的 43 个技术指标（避免每次现场算）
#   - stock_limit_up_history    : 东财涨停/炸板/强势/昨涨停 4 池入库
#   - stock_limit_up_indicators : 涨停类指标的扁平视图（用于筛选器）
# ====================================================================


class StockRealtimeEod(Base):
    """个股每日 EOD 聚合（由 individual_stock_snapshots 当日所有 tick 聚合）。

    用于：(a) 基础组指标（pe/pb/total_mv/float_mv/turnover_rate/latest_price）历史回放；
    (b) 按 as_of_date 过滤历史 universe（成交额门槛）。
    """

    __tablename__ = "stock_realtime_eod"
    __table_args__ = (
        UniqueConstraint("stock_code", "trading_date", name="uq_realtime_eod_code_date"),
        Index("ix_realtime_eod_code_date", "stock_code", "trading_date"),
        Index("ix_realtime_eod_trading_date", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_dynamic: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockIndicatorDaily(Base):
    """个股每日预计算指标（bars + fundflow 派生，43 列浮点数）。

    基础组（pe/pb/总市值/流通市值/换手率/latest_price）**不在此表**，它们从
    StockRealtimeEod 读取。本表只装 bars/fundflow 派生指标。
    """

    __tablename__ = "stock_indicators_daily"
    __table_args__ = (
        UniqueConstraint("stock_code", "trading_date", name="uq_indicators_daily_code_date"),
        Index("ix_indicators_daily_code_date", "stock_code", "trading_date"),
        Index("ix_indicators_daily_trading_date", "trading_date"),
        Index("ix_indicators_daily_hash", "data_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    compute_version: Mapped[str] = mapped_column(String(20), default="bars.v2.indicators.v1")
    data_hash: Mapped[str] = mapped_column(String(40))
    bar_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 趋势 MA（8）
    ma5: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma60: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_vs_ma5: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_vs_ma10: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_vs_ma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_vs_ma60: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 形态（6）
    ma_bullish: Mapped[int | None] = mapped_column(Integer, nullable=True)
    golden_cross_recent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    death_cross_recent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_20d_break: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_60d_break: Mapped[int | None] = mapped_column(Integer, nullable=True)
    low_20d_break: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 动量（13）
    change_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_10d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_up_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consecutive_down_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rsi6: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi14: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dif: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_dea: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_hist: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_golden_recent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bias20: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 量能（4）
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_ma5: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_ma5: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_up_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 涨停/形态（5）
    limit_up_today: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_up_count_5d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    platform_breakout: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gap_up_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_shadow_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 资金流（7）
    main_net_inflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_inflow_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_inflow_10d: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_inflow_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    main_net_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    super_large_net: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_inflow_5d_pct_mv: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockLimitUpHistory(Base):
    """东财涨停池历史（4 池：limit_up / broken / strong / previous）。

    用于复算连板天数、封单金额、强势股等指标。
    """

    __tablename__ = "stock_limit_up_history"
    __table_args__ = (
        UniqueConstraint(
            "trading_date", "stock_code", "pool_type", name="uq_limit_up_history_date_code_pool"
        ),
        Index("ix_limit_up_history_code_date", "stock_code", "trading_date"),
        Index("ix_limit_up_history_date_pool", "trading_date", "pool_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    stock_code: Mapped[str] = mapped_column(String(20))
    stock_name: Mapped[str] = mapped_column(String(120), default="")
    pool_type: Mapped[str] = mapped_column(String(20))
    board_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_limit_up_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_limit_up_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    limit_up_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sealed_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    amplitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_market_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_market_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_inflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    broken_board_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class StockLimitUpIndicator(Base):
    """涨停指标扁平视图（每日每只一行）。

    由 StockLimitUpHistory GROUP BY (trading_date, stock_code) 聚合生成，
    提供给筛选器快速读取：是否涨停、连板数、封单金额、是否炸板、是否强势股。
    """

    __tablename__ = "stock_limit_up_indicators"
    __table_args__ = (
        UniqueConstraint("stock_code", "trading_date", name="uq_limit_up_indicators_code_date"),
        Index("ix_limit_up_indicators_date", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    limit_up_today: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consecutive_limit_up_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sealed_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    broken_today: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strong_pool: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockLhbDetail(Base):
    """龙虎榜明细（东财 stock_lhb_detail_em，每日 ~100 行）。

    一只股票一日可因多个上榜原因多行；唯一约束 (trading_date, stock_code, reason)。
    机构席位数从「解读」文本解析（"N家机构买入/卖出"），inst_net_count = 买-卖。
    选股器 lhb_today/lhb_net_buy/lhb_inst_net_buy 实时从此表聚合（表小，不预计算）。
    """

    __tablename__ = "stock_lhb_detail"
    __table_args__ = (
        UniqueConstraint(
            "trading_date", "stock_code", "reason", name="uq_lhb_detail_date_code_reason"
        ),
        Index("ix_lhb_detail_code_date", "stock_code", "trading_date"),
        Index("ix_lhb_detail_date", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120), default="")
    reason: Mapped[str] = mapped_column(String(200), default="")
    interpretation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_buy: Mapped[float | None] = mapped_column(Float, nullable=True)
    buy_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    trading_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_buy_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True)
    inst_buy_count: Mapped[int] = mapped_column(Integer, default=0)
    inst_sell_count: Mapped[int] = mapped_column(Integer, default=0)
    inst_net_count: Mapped[int] = mapped_column(Integer, default=0)
    source_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
