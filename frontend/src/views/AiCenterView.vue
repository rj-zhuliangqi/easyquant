<script setup>
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "ai-center" });

// ── Tab state ──
const activeTab = ref("overview");
const tabs = [
  { key: "overview", label: "今日概览", icon: "📊" },
  { key: "jobs", label: "任务运行", icon: "⚙️" },
  { key: "picks", label: "选股池", icon: "🎯" },
  { key: "review", label: "复盘经验", icon: "📝" },
  { key: "config", label: "配置", icon: "🔧" },
];

// ── Data queries ──
const pageQuery = useQuery({
  queryKey: pageQueryKey("ai-center"),
  queryFn: () => fetchJson("/api/page/ai-center"),
  staleTime: 30_000,
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const summary = computed(() => payload.value.overview?.summary || {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);

// ── Helpers ──
const DISPLAY_GROUPS = ["盘前", "盘中", "盘后", "夜间", "周报"];

const jobsByGroup = computed(() => {
  const groups = {};
  for (const g of DISPLAY_GROUPS) groups[g] = [];
  for (const job of payload.value.jobs?.items || []) {
    const g = job.display_group || "盘中";
    (groups[g] = groups[g] || []).push(job);
  }
  return groups;
});

const todayPicks = computed(() => payload.value.overview?.today_recommendations || []);
const yesterdayFollowups = computed(() => payload.value.overview?.yesterday_followups || []);
const experienceCards = computed(() => payload.value.overview?.experience_cards || []);
const dailyReview = computed(() => payload.value.overview?.daily_review || {});

function pickLevelLabel(level) {
  const map = { strong_recommend: "强烈推荐", confirm: "确认", candidate: "候选", watch: "观察" };
  return map[level] || level;
}

function statusClass(status) {
  if (status === "success") return "status-success";
  if (status === "failed") return "status-danger";
  return "status-neutral";
}

// ── Engine config state ──
const enginesQuery = useQuery({
  queryKey: ["ai-engines"],
  queryFn: () => fetchJson("/api/ai/engines"),
  enabled: computed(() => activeTab.value === "config"),
  staleTime: 60_000,
});
const engines = computed(() => enginesQuery.data.value?.engines || []);
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">策略与运行</p>
        <h2>AI 中台</h2>
        <p class="hero-copy">选股策略执行、结果展示与经验沉淀</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" />
    </header>

    <!-- Tab Navigation -->
    <nav class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </nav>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 今日概览                               -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'overview'">
      <section class="card-grid">
        <article class="metric-card">
          <span>当日推荐</span>
          <strong>{{ summary.today_pick_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>昨日跟踪</span>
          <strong>{{ summary.yesterday_followup_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>经验条目</span>
          <strong>{{ summary.experience_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>成功任务</span>
          <strong>{{ summary.ops_summary?.success_jobs ?? 0 }}/{{ summary.ops_summary?.total_jobs ?? 0 }}</strong>
        </article>
      </section>

      <!-- Today's Picks -->
      <section class="panel mt-lg">
        <div class="panel-head"><h3>今日推荐</h3></div>
        <div class="pick-grid">
          <div v-for="rec in todayPicks" :key="rec.stock_code" class="pick-card">
            <div class="pick-header">
              <span class="pick-code">{{ rec.stock_code }}</span>
              <span class="pick-name">{{ rec.stock_name }}</span>
              <span v-if="rec.primary_pick_level" class="pick-badge" :class="rec.primary_pick_level">
                {{ pickLevelLabel(rec.primary_pick_level) }}
              </span>
            </div>
            <div class="pick-meta">
              <span v-if="rec.sector_name" class="pick-sector">{{ rec.sector_name }}</span>
              <span>{{ rec.source_count || 1 }} 个信号源</span>
            </div>
            <div v-if="rec.tags?.length" class="pick-tags">
              <span v-for="tag in rec.tags.slice(0, 4)" :key="tag" class="tag-chip">{{ tag }}</span>
            </div>
            <p v-if="rec.reason_summary" class="pick-reason">{{ rec.reason_summary }}</p>
          </div>
          <div v-if="!todayPicks.length && !queryLoading" class="empty-state">
            <p>暂无今日推荐</p>
            <span>今日尚未产生选股结果</span>
          </div>
        </div>
      </section>

      <!-- Yesterday Followups -->
      <section v-if="yesterdayFollowups.length" class="panel mt-lg">
        <div class="panel-head"><h3>昨日跟踪</h3></div>
        <div class="followup-list">
          <div v-for="f in yesterdayFollowups" :key="f.stock_code" class="followup-row">
            <span class="followup-code">{{ f.stock_code }}</span>
            <span class="followup-name">{{ f.stock_name }}</span>
            <span class="followup-label" :class="f.expectation_label || 'neutral'">
              {{ f.expectation_label || '待评估' }}
            </span>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 任务运行                               -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'jobs'">
      <div v-for="group in DISPLAY_GROUPS" :key="group">
        <template v-if="jobsByGroup[group]?.length">
          <h3 class="group-title">{{ group }}</h3>
          <div class="job-list">
            <div v-for="job in jobsByGroup[group]" :key="job.id" class="job-card">
              <div class="job-main">
                <span class="job-name">{{ job.name }}</span>
                <span class="job-type">{{ job.job_type }}</span>
              </div>
              <div class="job-status">
                <span class="status-badge" :class="statusClass(job.latest_run_summary?.status)">
                  {{ job.latest_run_summary?.status || '未运行' }}
                </span>
                <span v-if="job.engine_type" class="job-engine">{{ job.engine_type }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Recent Runs -->
      <section class="panel mt-lg">
        <div class="panel-head"><h3>最近运行</h3></div>
        <div class="run-list">
          <div v-for="run in payload.runs?.items?.slice(0, 20) || []" :key="run.id" class="run-row">
            <span class="run-name">{{ run.job_name || '未命名' }}</span>
            <span class="run-type">{{ run.result_type || run.run_type }}</span>
            <span class="run-date">{{ run.trading_date }}</span>
            <span class="status-badge" :class="statusClass(run.status)">{{ run.status }}</span>
            <span v-if="run.duration_ms" class="run-duration">{{ (run.duration_ms / 1000).toFixed(1) }}s</span>
          </div>
          <div v-if="!(payload.runs?.items?.length) && !queryLoading" class="empty-state">
            <p>暂无运行</p>
            <span>尚未执行任何任务</span>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 选股池                                 -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'picks'">
      <section class="panel">
        <div class="panel-head"><h3>选股池</h3></div>
        <div class="pick-grid">
          <div v-for="rec in todayPicks" :key="rec.stock_code" class="pick-card pick-card--detailed">
            <div class="pick-header">
              <span class="pick-code">{{ rec.stock_code }}</span>
              <span class="pick-name">{{ rec.stock_name }}</span>
              <span v-if="rec.primary_pick_level" class="pick-badge" :class="rec.primary_pick_level">
                {{ pickLevelLabel(rec.primary_pick_level) }}
              </span>
            </div>
            <div class="pick-detail-grid">
              <div v-if="rec.sector_name"><span class="detail-label">板块</span><span class="detail-value">{{ rec.sector_name }}</span></div>
              <div><span class="detail-label">信号源</span><span class="detail-value">{{ rec.source_count || 1 }}</span></div>
              <div v-if="rec.min_priority_rank"><span class="detail-label">优先级</span><span class="detail-value">#{{ rec.min_priority_rank }}</span></div>
            </div>
            <div v-if="rec.tags?.length" class="pick-tags">
              <span v-for="tag in rec.tags" :key="tag" class="tag-chip">{{ tag }}</span>
            </div>
            <p v-if="rec.reason_summary" class="pick-reason">{{ rec.reason_summary }}</p>
            <div v-if="rec.outcomes?.length" class="outcome-section">
              <span class="outcome-title">T+N 表现</span>
              <div class="outcome-chips">
                <span v-for="o in rec.outcomes" :key="o.window" class="outcome-chip" :class="o.close_change_pct > 0 ? 'positive' : 'negative'">
                  {{ o.window }}: {{ o.close_change_pct > 0 ? '+' : '' }}{{ o.close_change_pct?.toFixed(2) }}%
                </span>
              </div>
            </div>
          </div>
          <div v-if="!todayPicks.length && !queryLoading" class="empty-state">
            <p>暂无选股结果</p>
            <span>今日尚未产生选股结果</span>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 复盘与经验                             -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'review'">
      <section class="panel">
        <div class="panel-head"><h3>交易复盘</h3></div>
        <div v-if="dailyReview.market_summary_json || dailyReview.market_summary" class="review-section">
          <h4 class="review-subtitle">市场概况</h4>
          <p class="review-text">{{ dailyReview.market_summary?.market_phase || '暂无数据' }}</p>
        </div>
        <div v-if="dailyReview.top_themes?.length" class="review-section">
          <h4 class="review-subtitle">主线板块</h4>
          <div class="theme-list">
            <div v-for="t in dailyReview.top_themes" :key="t.theme || t" class="theme-item">
              <span class="theme-name">{{ t.theme || t }}</span>
              <span v-if="t.sector" class="theme-sector">{{ t.sector }}</span>
            </div>
          </div>
        </div>
        <div v-if="dailyReview.failed_patterns?.length" class="review-section">
          <h4 class="review-subtitle">失败模式</h4>
          <div class="failure-list">
            <span v-for="f in dailyReview.failed_patterns" :key="f" class="failure-chip">{{ f }}</span>
          </div>
        </div>
        <div v-if="!dailyReview.market_summary && !queryLoading" class="empty-state">
          <p>暂无复盘</p>
          <span>今日尚未生成复盘数据</span>
        </div>
      </section>

      <section class="panel mt-lg">
        <div class="panel-head"><h3>经验卡片</h3></div>
        <div class="exp-list">
          <div v-for="card in experienceCards" :key="card.title" class="exp-card">
            <span class="exp-tag">{{ card.tag }}</span>
            <span class="exp-title">{{ card.title }}</span>
            <span class="exp-hits">{{ card.hit_count || 0 }} 次</span>
          </div>
          <div v-if="!experienceCards.length && !queryLoading" class="empty-state">
            <p>暂无经验</p>
            <span>经验库为空</span>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 配置                                   -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'config'">
      <section class="panel">
        <div class="panel-head"><h3>执行引擎</h3></div>
        <div class="engine-list">
          <div v-for="eng in engines" :key="eng.type" class="engine-card" :class="{ disabled: !eng.available }">
            <div class="engine-main">
              <span class="engine-name">{{ eng.name }}</span>
              <span class="status-badge" :class="eng.available ? 'status-success' : 'status-danger'">
                {{ eng.available ? '可用' : '不可用' }}
              </span>
            </div>
            <p class="engine-desc">{{ eng.description }}</p>
            <div v-if="eng.config_fields?.length" class="engine-fields">
              配置项: {{ eng.config_fields.join(', ') }}
            </div>
          </div>
        </div>
      </section>

      <section class="panel mt-lg">
        <div class="panel-head"><h3>任务调度</h3></div>
        <div class="job-config-list">
          <div v-for="job in payload.jobs?.items || []" :key="job.id" class="job-config-card">
            <div class="job-config-main">
              <strong>{{ job.name }}</strong>
              <span class="job-config-cron">{{ job.schedule_rrule_or_cron || job.schedule_label }}</span>
            </div>
            <div class="job-config-meta">
              <span>引擎: {{ job.engine_type || 'claude-code' }}</span>
              <span>自动调度: {{ job.auto_schedule !== false ? '开' : '关' }}</span>
              <span v-if="job.last_executed_at">上次执行: {{ formatDateTime(job.last_executed_at) }}</span>
            </div>
          </div>
          <div v-if="!(payload.jobs?.items?.length) && !queryLoading" class="empty-state">
            <p>暂无任务</p>
            <span>当前没有配置的任务</span>
          </div>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
/* ── Tab Navigation ── */
.tab-nav {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--surface-active, rgba(255,255,255,0.04));
  border-radius: 12px;
  margin-bottom: 20px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted, #94a3b8);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text, #e2e8f0); background: rgba(255,255,255,0.04); }
.tab-btn.active { color: var(--text, #e2e8f0); background: var(--surface, #1e293b); }
.tab-icon { font-size: 14px; }

/* ── Pick Cards ── */
.pick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.pick-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--surface, #1e293b);
  border: 1px solid var(--border, rgba(255,255,255,0.06));
}
.pick-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.pick-code { font-family: monospace; font-size: 13px; color: var(--text-muted, #94a3b8); font-weight: 600; }
.pick-name { font-weight: 600; font-size: 15px; flex: 1; }
.pick-badge { font-size: 11px; padding: 2px 8px; border-radius: 20px; font-weight: 600; }
.pick-badge.strong_recommend { color: #f87171; background: rgba(248,113,113,0.1); }
.pick-badge.confirm { color: #fbbf24; background: rgba(251,191,36,0.1); }
.pick-badge.candidate { color: #60a5fa; background: rgba(96,165,250,0.1); }
.pick-badge.watch { color: #94a3b8; background: rgba(148,163,184,0.1); }
.pick-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 6px; }
.pick-sector { color: #60a5fa; }
.pick-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.tag-chip { font-size: 11px; padding: 1px 8px; border-radius: 20px; background: rgba(148,163,184,0.08); color: var(--text-muted, #94a3b8); }
.pick-reason { font-size: 13px; color: var(--text-secondary, #cbd5e1); line-height: 1.5; margin: 4px 0 0; }

/* ── Detailed Pick ── */
.pick-detail-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 8px; }
.detail-label { font-size: 11px; color: var(--text-muted, #94a3b8); display: block; }
.detail-value { font-size: 14px; font-weight: 600; }

/* ── Outcomes ── */
.outcome-section { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border, rgba(255,255,255,0.06)); }
.outcome-title { font-size: 11px; color: var(--text-muted, #94a3b8); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; display: block; }
.outcome-chips { display: flex; gap: 6px; }
.outcome-chip { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.outcome-chip.positive { color: #4ade80; background: rgba(74,222,128,0.1); }
.outcome-chip.negative { color: #f87171; background: rgba(248,113,113,0.1); }

/* ── Job Cards ── */
.group-title { font-size: 13px; font-weight: 600; color: var(--text-muted, #94a3b8); text-transform: uppercase; letter-spacing: 0.05em; margin: 20px 0 10px; }
.job-list { display: flex; flex-direction: column; gap: 6px; }
.job-card { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.job-main { display: flex; align-items: center; gap: 8px; }
.job-name { font-weight: 600; font-size: 14px; }
.job-type { font-size: 12px; color: var(--text-muted, #94a3b8); padding: 1px 8px; border-radius: 20px; background: rgba(148,163,184,0.08); }
.job-status { display: flex; align-items: center; gap: 8px; }
.job-engine { font-size: 11px; color: #60a5fa; font-family: monospace; }

/* ── Status Badges ── */
.status-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px; }
.status-success { color: #4ade80; background: rgba(74,222,128,0.1); }
.status-danger { color: #f87171; background: rgba(248,113,113,0.1); }
.status-neutral { color: #94a3b8; background: rgba(148,163,184,0.08); }

/* ── Run List ── */
.run-list { display: flex; flex-direction: column; gap: 4px; }
.run-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-radius: 6px; font-size: 13px; }
.run-row:hover { background: var(--surface-hover, rgba(255,255,255,0.02)); }
.run-name { font-weight: 600; flex: 1; }
.run-type { color: var(--text-muted, #94a3b8); font-size: 12px; }
.run-date { color: var(--text-muted, #94a3b8); font-size: 12px; font-family: monospace; }
.run-duration { color: var(--text-muted, #94a3b8); font-size: 12px; }

/* ── Followups ── */
.followup-list { display: flex; flex-direction: column; gap: 4px; }
.followup-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; font-size: 13px; }
.followup-code { font-family: monospace; color: var(--text-muted, #94a3b8); }
.followup-name { font-weight: 600; flex: 1; }
.followup-label { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.followup-label.met { color: #4ade80; background: rgba(74,222,128,0.1); }
.followup-label.missed { color: #f87171; background: rgba(248,113,113,0.1); }
.followup-label.neutral { color: #94a3b8; background: rgba(148,163,184,0.08); }

/* ── Review Sections ── */
.review-section { margin-bottom: 16px; }
.review-subtitle { font-size: 13px; font-weight: 600; color: var(--text-muted, #94a3b8); margin-bottom: 6px; }
.review-text { font-size: 14px; line-height: 1.6; }
.theme-list { display: flex; flex-wrap: wrap; gap: 6px; }
.theme-item { display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 6px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.theme-name { font-weight: 600; font-size: 13px; }
.theme-sector { font-size: 12px; color: var(--text-muted, #94a3b8); }
.failure-list { display: flex; flex-wrap: wrap; gap: 6px; }
.failure-chip { font-size: 12px; padding: 3px 10px; border-radius: 20px; color: #f87171; background: rgba(248,113,113,0.1); }

/* ── Experience Cards ── */
.exp-list { display: flex; flex-direction: column; gap: 6px; }
.exp-card { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.exp-tag { font-size: 11px; padding: 1px 8px; border-radius: 20px; background: rgba(148,163,184,0.08); color: var(--text-muted, #94a3b8); }
.exp-title { font-weight: 600; font-size: 13px; flex: 1; }
.exp-hits { font-size: 12px; color: var(--text-muted, #94a3b8); }

/* ── Engine Cards ── */
.engine-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.engine-card { padding: 14px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.engine-card.disabled { opacity: 0.6; }
.engine-main { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.engine-name { font-weight: 600; font-size: 14px; }
.engine-desc { font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 6px; }
.engine-fields { font-size: 11px; color: var(--text-muted, #94a3b8); font-family: monospace; }

/* ── Job Config ── */
.job-config-list { display: flex; flex-direction: column; gap: 6px; }
.job-config-card { padding: 10px 14px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.job-config-main { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.job-config-cron { font-family: monospace; font-size: 12px; color: var(--text-muted, #94a3b8); }
.job-config-meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted, #94a3b8); }

/* ── Empty State ── */
.empty-state { text-align: center; padding: 32px; color: var(--text-muted, #94a3b8); }
.empty-state p { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.empty-state span { font-size: 12px; }

/* ── Utility ── */
.mt-lg { margin-top: 20px; }
</style>
