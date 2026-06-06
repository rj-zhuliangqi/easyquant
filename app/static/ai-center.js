const state = {
  selectedDate: "",
  selectedRunType: "",
  selectedRecommendationCode: null,
  selectedExperienceKey: null,
  selectedJobId: null,
  selectedSkillId: null,
  selectedRulepackId: null,
  overviewPayload: null,
  jobsPayload: { items: [] },
  runsPayload: { items: [] },
  skillsPayload: { items: [], jobs: [] },
  rulepacksPayload: { items: [] },
  backtestsPayload: { items: [] },
  jobHistoryCache: new Map(),
  skillPerformanceCache: new Map(),
};

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      if (payload?.detail) detail = `: ${payload.detail}`;
    } catch {}
    throw new Error(`Request failed ${response.status}${detail}`);
  }
  return response.json();
}

function setStatus(text) {
  document.getElementById("ai-status").textContent = text;
}

function getToday() {
  return new Date().toISOString().slice(0, 10);
}

function currentFilters() {
  return {
    tradingDate: document.getElementById("trading-date").value || getToday(),
    runType: document.getElementById("run-type-filter").value,
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return `${Number(value).toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
}

function renderEmpty(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function updateSummary() {
  const overview = state.overviewPayload;
  const summary = overview?.summary || {};
  const opsSummary = summary.ops_summary || {};
  const activeRulepacks = (state.rulepacksPayload.items || []).filter((item) => (item.active_job_ids || []).length > 0);
  document.getElementById("summary-picks").textContent = String(summary.today_pick_count ?? 0);
  document.getElementById("summary-picks-meta").textContent = `${state.selectedDate} 当日推荐股票`;
  document.getElementById("summary-followups").textContent = String(summary.yesterday_followup_count ?? 0);
  document.getElementById("summary-followups-meta").textContent = "昨日推荐今日表现";
  document.getElementById("summary-experience").textContent = String(summary.experience_count ?? 0);
  document.getElementById("summary-experience-meta").textContent = "自动沉淀出的经验条目";
  document.getElementById("summary-ops").textContent = `${opsSummary.success_jobs ?? 0}/${opsSummary.total_jobs ?? 0}`;
  document.getElementById("summary-ops-meta").textContent = `成功 ${opsSummary.success_jobs ?? 0} · 未执行 ${opsSummary.pending_jobs ?? 0}`;
  document.getElementById("summary-rulepack").textContent = String(activeRulepacks.length);
  document.getElementById("summary-rulepack-meta").textContent = activeRulepacks.length
    ? activeRulepacks.map((item) => item.name).slice(0, 2).join(" · ")
    : "当前没有激活的经验规则包";

  const reviewHeadline = overview?.daily_review?.market_summary?.headline;
  document.getElementById("ai-hero-copy").textContent =
    reviewHeadline || `${state.selectedDate} 聚焦今日推荐、昨日跟踪、复盘与经验沉淀。`;
}

function sourceTasksMarkup(sourceTasks) {
  const items = sourceTasks || [];
  if (!items.length) return '<span class="chip">暂无任务来源</span>';
  return items
    .map(
      (source) => `
        <span class="chip">
          ${escapeHtml(source.skill_name || "--")} · ${escapeHtml(source.pick_level || "--")}
        </span>
      `
    )
    .join("");
}

function outcomeChips(outcomes) {
  const items = outcomes || [];
  if (!items.length) return '<span class="chip">等待 outcome</span>';
  return items
    .map(
      (outcome) => `
        <span class="chip">
          ${escapeHtml(outcome.window)} ${formatPercent(outcome.average_close_change_pct ?? outcome.close_change_pct)}
        </span>
      `
    )
    .join("");
}

function recommendationCardMarkup(item, compact = false) {
  const feedback = item.experience_feedback || {};
  return `
    <article class="stock-card ${state.selectedRecommendationCode === item.stock_code ? "selected" : ""}" data-recommendation="${escapeHtml(item.stock_code)}">
      <div class="card-top">
        <div>
          <strong>${escapeHtml(item.stock_name)} (${escapeHtml(item.stock_code)})</strong>
          <div class="meta-line">
            ${escapeHtml(item.pick_level || "--")} · ${escapeHtml(item.sector_name || "未分类")} · ${escapeHtml(item.signal_context || "--")}
          </div>
        </div>
        <span class="status-chip">${item.source_count} 源</span>
      </div>
      <p>${escapeHtml(item.reason_summary || "暂无推荐理由")}</p>
      <div class="chip-row">
        <span class="chip">净流入 ${formatNumber(item.capital_profile?.net_inflow)}</span>
        <span class="chip">主力 ${escapeHtml(item.capital_profile?.main_force_signal || "--")}</span>
        <span class="chip">量比 ${formatNumber(item.capital_profile?.volume_ratio)}</span>
      </div>
      <div class="chip-row">${sourceTasksMarkup(item.source_tasks)}</div>
      <div class="chip-row">${(item.risk_flags || []).map((risk) => `<span class="chip warn">${escapeHtml(risk)}</span>`).join("")}</div>
      ${
        feedback.matched_rule_count
          ? `<div class="chip-row"><span class="chip success">经验规则 ${feedback.matched_rule_count} 条</span><span class="chip">分数调整 ${formatNumber(feedback.score_delta || 0)}</span></div>`
          : ""
      }
      ${compact ? "" : `<div class="chip-row">${outcomeChips(item.outcomes)}</div>`}
    </article>
  `;
}

function followupCardMarkup(item) {
  const metrics = item.today_metrics || {};
  return `
    <article class="followup-card">
      <div class="card-top">
        <div>
          <strong>${escapeHtml(item.stock_name)} (${escapeHtml(item.stock_code)})</strong>
          <div class="meta-line">${escapeHtml(item.expectation_label)} · 昨日逻辑：${escapeHtml(item.yesterday_reason_summary || "--")}</div>
        </div>
        <span class="status-chip">${escapeHtml(item.expectation_label)}</span>
      </div>
      <div class="info-grid">
        <div><span>开盘</span><strong>${formatPercent(metrics.open_change_pct)}</strong></div>
        <div><span>收盘</span><strong>${formatPercent(metrics.close_change_pct)}</strong></div>
        <div><span>最高</span><strong>${formatPercent(metrics.max_gain_pct)}</strong></div>
        <div><span>最大回撤</span><strong>${formatPercent(metrics.max_drawdown_pct)}</strong></div>
      </div>
      <div class="chip-row">
        <span class="chip">${metrics.beat_benchmark ? "跑赢指数" : "未跑赢指数/待确认"}</span>
      </div>
      <p>${escapeHtml(item.attribution_summary || "暂无归因")}</p>
      <div class="chip-row">${sourceTasksMarkup(item.source_tasks)}</div>
    </article>
  `;
}

function reviewPanelMarkup(review) {
  if (!review) return renderEmpty("当前交易日没有复盘数据。");
  const marketSummary = review.market_summary || {};
  const marketBreadth = review.market_breadth || {};
  return `
    <div class="review-summary-card">
      <div class="panel-sentence">
        <strong>${escapeHtml(marketSummary.headline || "暂无一句话总结")}</strong>
        <span>${escapeHtml(marketSummary.risk_prompt || "暂无风险提示")}</span>
      </div>
      <div class="review-columns">
        <section class="embedded-card">
          <h4>大盘 / 情绪</h4>
          <div class="info-grid">
            ${Object.entries(marketBreadth)
              .map(([key, value]) => `<div><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`)
              .join("") || "<div><span>暂无</span><strong>--</strong></div>"}
          </div>
        </section>
        <section class="embedded-card">
          <h4>主线 / 失败模式</h4>
          <div class="chip-row">
            ${(review.top_themes || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("") || '<span class="chip">暂无主线</span>'}
          </div>
          <div class="list-block">
            ${(review.failed_patterns || []).map((item) => `<div>${escapeHtml(item)}</div>`).join("") || "<div>暂无失败模式</div>"}
          </div>
        </section>
        <section class="embedded-card">
          <h4>次日关注</h4>
          <div class="chip-row">
            ${(review.next_day_focus || []).map((item) => `<span class="chip">${escapeHtml(typeof item === "string" ? item : JSON.stringify(item))}</span>`).join("") || '<span class="chip">暂无次日关注</span>'}
          </div>
        </section>
      </div>
      <div class="review-columns bottom">
        <section class="embedded-card">
          <h4>推荐股反馈</h4>
          <div class="list-block">
            ${(review.recommended_picks_review || [])
              .map(
                (item) => `
                  <div>
                    ${escapeHtml(item.stock_code || "--")} ${escapeHtml(item.stock_name || "--")} ·
                    ${escapeHtml(item.review || item.effect || JSON.stringify(item))}
                  </div>
                `
              )
              .join("") || "<div>暂无推荐股反馈</div>"}
          </div>
        </section>
        <section class="embedded-card">
          <h4>持仓复盘</h4>
          <div class="list-block">
            ${(review.position_review || [])
              .map((item) => `<div>${escapeHtml(typeof item === "string" ? item : JSON.stringify(item))}</div>`)
              .join("") || "<div>暂无持仓复盘</div>"}
          </div>
        </section>
      </div>
    </div>
  `;
}

function experienceCardMarkup(item) {
  const experienceKey = `${item.title}::${item.tag}`;
  return `
    <article class="experience-card ${state.selectedExperienceKey === experienceKey ? "selected" : ""}" data-experience="${escapeHtml(experienceKey)}">
      <div class="card-top">
        <div>
          <strong>${escapeHtml(item.title)}</strong>
          <div class="meta-line">${escapeHtml(item.tag || "general")} · 最近 ${escapeHtml(item.last_seen_date || "--")}</div>
        </div>
        <span class="status-chip">${item.hit_count} 次</span>
      </div>
      <div class="chip-row">
        ${(item.related_dates || []).slice(0, 4).map((day) => `<span class="chip">${escapeHtml(day)}</span>`).join("")}
      </div>
    </article>
  `;
}

function renderOverview() {
  const overview = state.overviewPayload || {};
  const today = overview.today_recommendations || [];
  const followups = overview.yesterday_followups || [];
  const experience = overview.experience_cards || [];

  document.getElementById("overview-today").innerHTML = today.length
    ? today.slice(0, 4).map((item) => recommendationCardMarkup(item, true)).join("")
    : renderEmpty("今天还没有推荐股票。");
  document.getElementById("overview-followups").innerHTML = followups.length
    ? followups.slice(0, 4).map(followupCardMarkup).join("")
    : renderEmpty("昨天推荐的股票今天还没有可用结果。");
  document.getElementById("overview-review").innerHTML = reviewPanelMarkup(overview.daily_review);
  document.getElementById("overview-experience").innerHTML = experience.length
    ? experience.slice(0, 6).map(experienceCardMarkup).join("")
    : renderEmpty("当前还没有经验沉淀。");
}

function renderRecommendations() {
  const items = state.overviewPayload?.today_recommendations || [];
  const container = document.getElementById("recommendation-list");
  if (!items.length) {
    container.innerHTML = renderEmpty("当前交易日没有推荐股票。");
    document.getElementById("recommendation-detail").innerHTML = renderEmpty("选择一只股票查看详情。");
    return;
  }
  container.innerHTML = items.map((item) => recommendationCardMarkup(item)).join("");
  if (!state.selectedRecommendationCode || !items.some((item) => item.stock_code === state.selectedRecommendationCode)) {
    state.selectedRecommendationCode = items[0].stock_code;
  }
  document.querySelectorAll("[data-recommendation]").forEach((node) => {
    node.addEventListener("click", () => {
      state.selectedRecommendationCode = node.dataset.recommendation;
      renderRecommendations();
      renderRecommendationDetail();
    });
  });
  renderRecommendationDetail();
}

function renderRecommendationDetail() {
  const item = (state.overviewPayload?.today_recommendations || []).find(
    (entry) => entry.stock_code === state.selectedRecommendationCode
  );
  const container = document.getElementById("recommendation-detail");
  if (!item) {
    container.innerHTML = renderEmpty("选择一只股票查看详情。");
    return;
  }
  container.innerHTML = `
    <div class="detail-card">
      <div class="detail-section">
        <h4>${escapeHtml(item.stock_name)} (${escapeHtml(item.stock_code)})</h4>
        <div class="chip-row">
          <span class="chip">${escapeHtml(item.pick_level || "--")}</span>
          <span class="chip">${escapeHtml(item.sector_name || "未分类")}</span>
          <span class="chip">${item.source_count} 个任务命中</span>
        </div>
      </div>
      <div class="detail-section">
        <p>${escapeHtml(item.reason_summary || "暂无推荐理由")}</p>
        <div class="chip-row">
          <span class="chip">净流入 ${formatNumber(item.capital_profile?.net_inflow)}</span>
          <span class="chip">主力 ${escapeHtml(item.capital_profile?.main_force_signal || "--")}</span>
          <span class="chip">量比 ${formatNumber(item.capital_profile?.volume_ratio)}</span>
        </div>
        <div class="chip-row">${(item.risk_flags || []).map((risk) => `<span class="chip warn">${escapeHtml(risk)}</span>`).join("")}</div>
        ${
          item.experience_feedback?.matched_rule_count
            ? `
              <div class="chip-row">
                <span class="chip success">${escapeHtml(item.experience_feedback.rulepack_name || "经验规则包")}</span>
                <span class="chip">命中 ${item.experience_feedback.matched_rule_count} 条</span>
                <span class="chip">加权 ${formatNumber(item.experience_feedback.score_delta || 0)}</span>
              </div>
            `
            : '<div class="chip-row"><span class="chip">当前未命中经验规则</span></div>'
        }
      </div>
      <div class="detail-section">
        <h4>任务来源</h4>
        <div class="list-block">
          ${(item.source_tasks || [])
            .map(
              (source) => `
                <article class="embedded-card">
                  <div class="card-top">
                    <strong>${escapeHtml(source.skill_name || "--")}</strong>
                    <span class="status-chip">${escapeHtml(source.pick_level || "--")}</span>
                  </div>
                  <div class="meta-line">${escapeHtml(source.signal_context || "--")} · ${escapeHtml(source.revision_title || "--")}</div>
                  <p>${escapeHtml(source.reason_summary || "暂无理由")}</p>
                  <div class="chip-row">
                    ${(source.risk_flags || []).map((risk) => `<span class="chip warn">${escapeHtml(risk)}</span>`).join("") || '<span class="chip">无显式风险</span>'}
                  </div>
                </article>
              `
            )
            .join("")}
        </div>
      </div>
      <div class="detail-section">
        <h4>T+1 / T+3</h4>
        <div class="chip-row">${outcomeChips(item.outcomes)}</div>
      </div>
      ${
        item.experience_feedback?.matched_rule_count
          ? `
            <div class="detail-section">
              <h4>经验反馈明细</h4>
              <div class="list-block">
                ${(item.experience_feedback.matched_rules || [])
                  .map(
                    (rule) => `
                      <div>${escapeHtml(rule.title)} · ${escapeHtml(rule.direction)} · 权重 ${formatNumber(rule.weight || 0)}</div>
                    `
                  )
                  .join("")}
              </div>
            </div>
          `
          : ""
      }
    </div>
  `;
}

function reviewableSources() {
  const rows = [];
  for (const item of state.overviewPayload?.today_recommendations || []) {
    for (const source of item.source_tasks || []) {
      rows.push({
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        ...source,
      });
    }
  }
  return rows;
}

function renderReviewTab() {
  document.getElementById("review-daily").innerHTML = reviewPanelMarkup(state.overviewPayload?.daily_review);
  const followups = state.overviewPayload?.yesterday_followups || [];
  document.getElementById("review-followups").innerHTML = followups.length
    ? followups.map(followupCardMarkup).join("")
    : renderEmpty("昨天推荐的股票今天还没有可用归因。");

  const rows = reviewableSources();
  const container = document.getElementById("review-picks");
  container.innerHTML = rows.length
    ? rows.slice(0, 12).map(
        (row) => `
          <button class="review-pick-button" data-pick-id="${row.pick_id}">
            <span>${escapeHtml(row.stock_name)} (${escapeHtml(row.stock_code)})</span>
            <strong>${escapeHtml(row.skill_name || "--")} · ${escapeHtml(row.pick_level || "--")}</strong>
          </button>
        `
      ).join("")
    : renderEmpty("当前没有可补充复盘的推荐。");
  document.querySelectorAll("[data-pick-id]").forEach((node) => {
    node.addEventListener("click", () => {
      document.getElementById("review-pick-id").value = node.dataset.pickId;
    });
  });
}

function fillExperienceFilter() {
  const items = state.overviewPayload?.experience_cards || [];
  const tags = ["全部", ...new Set(items.map((item) => item.tag || "general"))];
  const current = document.getElementById("experience-tag-filter").value || "全部";
  document.getElementById("experience-tag-filter").innerHTML = tags
    .map((tag) => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`)
    .join("");
  document.getElementById("experience-tag-filter").value = tags.includes(current) ? current : "全部";
}

function renderExperience() {
  fillExperienceFilter();
  const selectedTag = document.getElementById("experience-tag-filter").value || "全部";
  const items = (state.overviewPayload?.experience_cards || []).filter((item) => selectedTag === "全部" || item.tag === selectedTag);
  const container = document.getElementById("experience-list");
  if (!items.length) {
    container.innerHTML = renderEmpty("当前筛选条件下没有经验条目。");
    document.getElementById("experience-detail").innerHTML = renderEmpty("选择一条经验查看详情。");
    return;
  }
  container.innerHTML = items.map(experienceCardMarkup).join("");
  if (!state.selectedExperienceKey || !items.some((item) => `${item.title}::${item.tag}` === state.selectedExperienceKey)) {
    state.selectedExperienceKey = `${items[0].title}::${items[0].tag}`;
  }
  document.querySelectorAll("[data-experience]").forEach((node) => {
    node.addEventListener("click", () => {
      state.selectedExperienceKey = node.dataset.experience;
      renderExperience();
      renderExperienceDetail();
    });
  });
  renderExperienceDetail();
}

function renderExperienceDetail() {
  const item = (state.overviewPayload?.experience_cards || []).find(
    (entry) => `${entry.title}::${entry.tag}` === state.selectedExperienceKey
  );
  const container = document.getElementById("experience-detail");
  if (!item) {
    container.innerHTML = renderEmpty("选择一条经验查看详情。");
    return;
  }
  container.innerHTML = `
    <div class="detail-card">
      <div class="detail-section">
        <h4>${escapeHtml(item.title)}</h4>
        <div class="chip-row">
          <span class="chip">${escapeHtml(item.tag || "general")}</span>
          <span class="chip">命中 ${item.hit_count} 次</span>
          <span class="chip">最近 ${escapeHtml(item.last_seen_date || "--")}</span>
        </div>
      </div>
      <div class="detail-section">
        <h4>关联日期</h4>
        <div class="chip-row">${(item.related_dates || []).map((day) => `<span class="chip">${escapeHtml(day)}</span>`).join("")}</div>
      </div>
      <div class="detail-section">
        <h4>关联案例</h4>
        <div class="list-block">
          ${(item.related_examples || []).map((example) => `<div>${escapeHtml(example)}</div>`).join("") || "<div>暂无关联案例</div>"}
        </div>
      </div>
    </div>
  `;
}

async function loadJobHistory(jobId) {
  if (!jobId) return;
  if (!state.jobHistoryCache.has(jobId)) {
    state.jobHistoryCache.set(jobId, await fetchJson(`/api/ai/jobs/${jobId}/history`));
  }
}

function runForJob(jobId) {
  return (state.runsPayload.items || []).find((run) => run.job_id === jobId) || null;
}

function renderOps() {
  const jobs = state.jobsPayload.items || [];
  const container = document.getElementById("ops-job-list");
  if (!jobs.length) {
    container.innerHTML = renderEmpty("当前没有任务目录。");
    document.getElementById("ops-job-detail").innerHTML = renderEmpty("选择一个任务查看运行详情。");
    return;
  }
  container.innerHTML = jobs
    .map((job) => {
      const run = runForJob(job.id);
      const status = run?.status || "pending";
      const latestTime = run?.started_at || job.latest_run_summary?.trading_date || "--";
      return `
        <article class="timeline-card ${state.selectedJobId === job.id ? "selected" : ""}" data-job-card="${job.id}">
          <div class="timeline-top">
            <div>
              <div class="timeline-time">${escapeHtml(job.schedule_label || "--")}</div>
              <strong>${escapeHtml(job.name)}</strong>
              <div class="meta-line">${escapeHtml(job.job_type || "--")} · ${escapeHtml(job.display_group || "--")}</div>
            </div>
            <span class="status-chip ${status === "failed" ? "danger" : status === "success" ? "success" : ""}">${escapeHtml(status)}</span>
          </div>
          <div class="chip-row">
            <span class="chip">最近执行 ${escapeHtml(latestTime)}</span>
            <span class="chip">${run ? "已执行" : "未执行"}</span>
          </div>
        </article>
      `;
    })
    .join("");
  if (!state.selectedJobId || !jobs.some((job) => job.id === state.selectedJobId)) {
    state.selectedJobId = jobs[0].id;
  }
  document.querySelectorAll("[data-job-card]").forEach((node) => {
    node.addEventListener("click", async () => {
      state.selectedJobId = Number(node.dataset.jobCard);
      await loadJobHistory(state.selectedJobId);
      renderOps();
      renderOpsDetail();
    });
  });
  renderOpsDetail();
}

function renderOpsDetail() {
  const payload = state.jobHistoryCache.get(state.selectedJobId);
  const container = document.getElementById("ops-job-detail");
  if (!payload) {
    container.innerHTML = renderEmpty("选择一个任务查看运行详情。");
    return;
  }
  container.innerHTML = `
    <div class="detail-card">
      <div class="detail-section">
        <h4>${escapeHtml(payload.job.name)}</h4>
        <div class="chip-row">
          <span class="chip">${escapeHtml(payload.job.job_type || "--")}</span>
          <span class="chip">${escapeHtml(payload.job.display_group || "--")}</span>
          <span class="chip">激活 revision ${escapeHtml(payload.job.active_revision_id || "--")}</span>
        </div>
      </div>
      <div class="detail-section">
        <div class="info-grid">
          <div><span>运行次数</span><strong>${payload.summary.run_count}</strong></div>
          <div><span>成功次数</span><strong>${payload.summary.success_count}</strong></div>
          <div><span>推送成功</span><strong>${payload.summary.push_success_count}</strong></div>
          <div><span>正收益 outcome</span><strong>${payload.summary.positive_outcome_count}</strong></div>
        </div>
      </div>
      <div class="detail-section">
        <h4>历史执行</h4>
        <div class="list-block">
          ${(payload.runs || [])
            .map(
              (run) => `
                <div>
                  ${escapeHtml(run.trading_date)} · ${escapeHtml(run.status)} · ${escapeHtml(run.revision_title || "--")}
                </div>
              `
            )
            .join("") || "<div>暂无历史运行</div>"}
        </div>
      </div>
    </div>
  `;
}

async function loadSkillPerformance(skillId) {
  if (!skillId) return;
  if (!state.skillPerformanceCache.has(skillId)) {
    state.skillPerformanceCache.set(skillId, await fetchJson(`/api/ai/skills/${skillId}/performance`));
  }
}

function fillRulepackSelectors() {
  const stockPickJobs = (state.jobsPayload.items || []).filter((item) => item.job_type === "stock_pick");
  const jobOptions = stockPickJobs.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
  document.getElementById("rulepack-job-id").innerHTML = jobOptions;
  document.getElementById("rulepack-activate-job-id").innerHTML = jobOptions;
  refreshRulepackSelector();
}

function refreshRulepackSelector() {
  const jobId = Number(document.getElementById("rulepack-activate-job-id").value || 0);
  const rulepacks = state.rulepacksPayload.items || [];
  const options = rulepacks
    .filter((item) => !jobId || (item.active_job_ids || []).includes(jobId) || item.scope === "stock_pick")
    .map((item) => `<option value="${item.id}">${escapeHtml(item.name)} (${item.rule_count} rules)</option>`)
    .join("");
  document.getElementById("rulepack-activate-id").innerHTML = options;
}

function renderSkillList() {
  const container = document.getElementById("skill-list");
  const skills = state.skillsPayload.items || [];
  if (!skills.length) {
    container.innerHTML = renderEmpty("当前没有纳入治理的 skill。");
    document.getElementById("skill-detail").innerHTML = renderEmpty("选择一个 skill 查看版本表现。");
    return;
  }
  container.innerHTML = skills
    .map(
      (skill) => `
        <article class="timeline-card ${state.selectedSkillId === skill.id ? "selected" : ""}" data-skill-card="${skill.id}">
          <div class="timeline-top">
            <div>
              <strong>${escapeHtml(skill.name)}</strong>
              <div class="meta-line">${escapeHtml(skill.category || "--")} · ${escapeHtml(skill.description || "暂无描述")}</div>
            </div>
            <span class="status-chip">${skill.revisions.length} revisions</span>
          </div>
          <div class="chip-row">
            ${(skill.revisions || []).map((revision) => `<span class="chip">v${revision.revision_no} ${escapeHtml(revision.status)}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("");
  if (!state.selectedSkillId || !skills.some((skill) => skill.id === state.selectedSkillId)) {
    state.selectedSkillId = skills[0].id;
  }
  document.querySelectorAll("[data-skill-card]").forEach((node) => {
    node.addEventListener("click", async () => {
      state.selectedSkillId = Number(node.dataset.skillCard);
      await loadSkillPerformance(state.selectedSkillId);
      renderSkillList();
      renderSkillDetail();
    });
  });
  renderSkillDetail();
}

function renderSkillDetail() {
  const payload = state.skillPerformanceCache.get(state.selectedSkillId);
  const container = document.getElementById("skill-detail");
  if (!payload) {
    container.innerHTML = renderEmpty("选择一个 skill 查看版本表现。");
    return;
  }
  container.innerHTML = `
    <div class="detail-card">
      <div class="detail-section">
        <h4>${escapeHtml(payload.skill.name)}</h4>
        <div class="meta-line">保留工程治理视角，不参与首页结果阅读。</div>
      </div>
      <div class="detail-section">
        <div class="list-block">
          ${(payload.revisions || [])
            .map(
              (revision) => `
                <article class="embedded-card">
                  <div class="card-top">
                    <strong>v${revision.revision_no} · ${escapeHtml(revision.title)}</strong>
                    <span class="status-chip">${escapeHtml(revision.status)}</span>
                  </div>
                  <div class="info-grid">
                    <div><span>Run</span><strong>${revision.run_count}</strong></div>
                    <div><span>Pick</span><strong>${revision.pick_count}</strong></div>
                    <div><span>正收益</span><strong>${revision.positive_count}</strong></div>
                    <div><span>平均涨跌</span><strong>${formatPercent(revision.average_close_change_pct)}</strong></div>
                  </div>
                </article>
              `
            )
            .join("") || "<div>暂无 revision 表现数据</div>"}
        </div>
      </div>
    </div>
  `;
}

function renderRulepackDetail() {
  const container = document.getElementById("rulepack-detail");
  const items = state.rulepacksPayload.items || [];
  if (!items.length) {
    container.innerHTML = renderEmpty("当前还没有经验规则包。先在复盘归因沉淀经验，再从当日复盘生成。");
    return;
  }
  if (!state.selectedRulepackId || !items.some((item) => item.id === state.selectedRulepackId)) {
    state.selectedRulepackId = items[0].id;
  }
  const item = items.find((entry) => entry.id === state.selectedRulepackId);
  if (!item) {
    container.innerHTML = renderEmpty("选择经验规则包查看详情。");
    return;
  }
  container.innerHTML = `
    <div class="detail-card">
      <div class="detail-section">
        <h4>${escapeHtml(item.name)}</h4>
        <div class="chip-row">
          <span class="chip">${escapeHtml(item.status)}</span>
          <span class="chip">${escapeHtml(item.scope)}</span>
          <span class="chip">规则 ${item.rule_count} 条</span>
          <span class="chip">来源 ${escapeHtml(item.source_trading_date || "--")}</span>
        </div>
      </div>
      <div class="detail-section">
        <div class="list-block">
          ${(item.rules || [])
            .map(
              (rule) => `
                <div>${escapeHtml(rule.title)} · ${escapeHtml(rule.direction)} · 权重 ${formatNumber(rule.weight || 0)} · ${escapeHtml(rule.tag || "general")}</div>
              `
            )
            .join("") || "<div>暂无规则</div>"}
        </div>
      </div>
      <div class="detail-section">
        <div class="chip-row">
          ${(item.active_job_ids || []).length
            ? item.active_job_ids.map((jobId) => `<span class="chip success">已挂载 Job ${jobId}</span>`).join("")
            : '<span class="chip">当前未挂载到任务</span>'}
        </div>
      </div>
    </div>
  `;
}

function fillSkillSelectors() {
  const skills = state.skillsPayload.items || [];
  const options = skills.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
  document.getElementById("revision-skill-id").innerHTML = options;
  document.getElementById("backtest-skill-id").innerHTML = options;
  refreshRevisionSelector();
}

function refreshRevisionSelector() {
  const skillId = Number(document.getElementById("backtest-skill-id").value || 0);
  const skill = (state.skillsPayload.items || []).find((item) => item.id === skillId);
  const revisions = skill?.revisions || [];
  document.getElementById("backtest-revision-id").innerHTML = revisions
    .map((revision) => `<option value="${revision.id}">v${revision.revision_no} · ${escapeHtml(revision.title)}</option>`)
    .join("");
}

async function submitReview(event) {
  event.preventDefault();
  const pickId = Number(document.getElementById("review-pick-id").value || 0);
  if (!pickId) return;
  await fetchJson(`/api/ai/picks/${pickId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      window: document.getElementById("review-window").value,
      review_text: document.getElementById("review-text").value,
      review_tags: document
        .getElementById("review-tags")
        .value.split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      is_expectation_met: document.getElementById("review-expected").checked,
      improvement_hint: document.getElementById("review-improvement").value,
    }),
  });
  document.getElementById("review-form").reset();
  await refreshAll();
}

async function submitRevision(event) {
  event.preventDefault();
  const skillId = Number(document.getElementById("revision-skill-id").value || 0);
  if (!skillId) return;
  await fetchJson(`/api/ai/skills/${skillId}/revisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: document.getElementById("revision-title").value,
      content_text: document.getElementById("revision-content").value,
      change_note: document.getElementById("revision-note").value,
      status: "draft",
    }),
  });
  document.getElementById("revision-form").reset();
  await refreshAll();
}

async function submitBacktest(event) {
  event.preventDefault();
  await fetchJson("/api/ai/backtests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      skill_id: Number(document.getElementById("backtest-skill-id").value || 0),
      revision_id: Number(document.getElementById("backtest-revision-id").value || 0),
      date_from: document.getElementById("backtest-date-from").value,
      date_to: document.getElementById("backtest-date-to").value,
    }),
  });
  await refreshAll();
}

async function submitRulepackPromotion(event) {
  event.preventDefault();
  await fetchJson("/api/ai/rulepacks/promote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trading_date: document.getElementById("trading-date").value || getToday(),
      name: document.getElementById("rulepack-name").value || `${document.getElementById("trading-date").value || getToday()} 经验规则包`,
      job_id: Number(document.getElementById("rulepack-job-id").value || 0),
      status: document.getElementById("rulepack-status").value,
    }),
  });
  document.getElementById("rulepack-form").reset();
  await refreshAll();
}

async function submitRulepackActivation(event) {
  event.preventDefault();
  const jobId = Number(document.getElementById("rulepack-activate-job-id").value || 0);
  const rulepackId = Number(document.getElementById("rulepack-activate-id").value || 0);
  if (!jobId || !rulepackId) return;
  await fetchJson(`/api/ai/jobs/${jobId}/activate-rulepack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rulepack_id: rulepackId }),
  });
  await refreshAll();
}

async function seedDemoData() {
  const tradingDate = document.getElementById("trading-date").value || getToday();
  setStatus("正在注入演示数据");
  const payload = await fetchJson("/api/ai/demo/seed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trading_date: tradingDate }),
  });
  document.getElementById("run-type-filter").value = "demo";
  setStatus(`已注入 ${payload.seeded_runs} 个演示 run / ${payload.seeded_picks} 条 pick`);
  await refreshAll();
}

async function clearDemoData() {
  const tradingDate = document.getElementById("trading-date").value || getToday();
  setStatus("正在清空演示数据");
  const payload = await fetchJson("/api/ai/demo/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trading_date: tradingDate }),
  });
  document.getElementById("run-type-filter").value = "demo";
  setStatus(`已清空 ${payload.deleted_runs} 个演示 run / ${payload.deleted_picks} 条 pick`);
  await refreshAll();
}

function bindTabs() {
  const activateTab = (tabName) => {
    document.querySelectorAll(".tab-button").forEach((node) => node.classList.toggle("active", node.dataset.tab === tabName));
    document.querySelectorAll(".tab-panel").forEach((node) => node.classList.toggle("active", node.id === `tab-${tabName}`));
  };
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      const tabName = button.dataset.tab;
      activateTab(tabName);
      const url = new URL(window.location.href);
      url.searchParams.set("tab", tabName);
      window.history.replaceState({}, "", url);
    });
  });
  const requested = new URLSearchParams(window.location.search).get("tab");
  activateTab(document.querySelector(`.tab-button[data-tab="${requested}"]`) ? requested : "overview");
}

function bindActions() {
  document.getElementById("refresh-button").addEventListener("click", refreshAll);
  document.getElementById("seed-demo-button").addEventListener("click", seedDemoData);
  document.getElementById("clear-demo-button").addEventListener("click", clearDemoData);
  document.getElementById("trading-date").addEventListener("change", refreshAll);
  document.getElementById("run-type-filter").addEventListener("change", refreshAll);
  document.getElementById("experience-tag-filter").addEventListener("change", renderExperience);
  document.getElementById("review-form").addEventListener("submit", submitReview);
  document.getElementById("rulepack-form").addEventListener("submit", submitRulepackPromotion);
  document.getElementById("rulepack-activate-form").addEventListener("submit", submitRulepackActivation);
  document.getElementById("rulepack-activate-job-id").addEventListener("change", refreshRulepackSelector);
  document.getElementById("revision-form").addEventListener("submit", submitRevision);
  document.getElementById("backtest-form").addEventListener("submit", submitBacktest);
  document.getElementById("backtest-skill-id").addEventListener("change", refreshRevisionSelector);
}

async function refreshAll() {
  const filters = currentFilters();
  state.selectedDate = filters.tradingDate;
  state.selectedRunType = filters.runType;
  setStatus("加载 AI 中台数据中");

  const overviewQuery = new URLSearchParams({ trading_date: state.selectedDate });
  const runsQuery = new URLSearchParams({ trading_date: state.selectedDate });
  if (state.selectedRunType) {
    overviewQuery.set("run_type", state.selectedRunType);
    runsQuery.set("run_type", state.selectedRunType);
  }

  const [overview, jobs, runs, skills, rulepacks, backtests] = await Promise.all([
    fetchJson(`/api/ai/overview/daily?${overviewQuery.toString()}`),
    fetchJson("/api/ai/jobs"),
    fetchJson(`/api/ai/runs?${runsQuery.toString()}`),
    fetchJson("/api/ai/skills"),
    fetchJson("/api/ai/rulepacks"),
    fetchJson("/api/ai/backtests"),
  ]);

  state.overviewPayload = overview;
  state.jobsPayload = jobs;
  state.runsPayload = runs;
  state.skillsPayload = skills;
  state.rulepacksPayload = rulepacks;
  state.backtestsPayload = backtests;
  state.jobHistoryCache.clear();
  state.skillPerformanceCache.clear();

  if ((state.jobsPayload.items || []).length) {
    state.selectedJobId = state.jobsPayload.items[0].id;
    await loadJobHistory(state.selectedJobId);
  }
  if ((state.skillsPayload.items || []).length) {
    state.selectedSkillId = state.skillsPayload.items[0].id;
    await loadSkillPerformance(state.selectedSkillId);
  }

  updateSummary();
  renderOverview();
  renderRecommendations();
  renderReviewTab();
  renderExperience();
  renderOps();
  renderSkillList();
  fillSkillSelectors();
  fillRulepackSelectors();
  renderRulepackDetail();
  setStatus(`已加载 ${overview.summary.today_pick_count} 只推荐 / ${overview.summary.yesterday_followup_count} 条昨日跟踪`);
}

function initDate() {
  const params = new URLSearchParams(window.location.search);
  document.getElementById("trading-date").value = params.get("trading_date") || getToday();
  document.getElementById("run-type-filter").value = params.get("run_type") || "";
  state.selectedDate = document.getElementById("trading-date").value;
}

async function boot() {
  initDate();
  bindTabs();
  bindActions();
  await refreshAll();
}

boot().catch((error) => {
  console.error(error);
  setStatus("AI 中台加载失败");
});
