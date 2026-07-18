<script setup>
import { computed, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRouter } from "vue-router";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import StatusBadge from "../components/ui/StatusBadge.vue";
import { fetchJson } from "../lib/api";
import { formatDateTime, todayIso } from "../lib/formatters";
import { useTimerCleanup } from "../composables/useTimerCleanup";

defineOptions({ name: "ai-jobs" });

const router = useRouter();
const queryClient = useQueryClient();

const selectedJobId = ref(null);
const executingIds = ref(new Set());
const actionError = ref("");
// P2-8j/C3: setTimeout 集中管理，卸载时清理避免泄漏
const { later } = useTimerCleanup();

const aiJobsQuery = useQuery({
  queryKey: ["ai-jobs"],
  queryFn: () => fetchJson("/api/ai/jobs"),
  refetchInterval: () => (document.hidden ? false : 30_000),
  staleTime: 15_000,
});

const schedulerQuery = useQuery({
  queryKey: ["ai-scheduler-status"],
  queryFn: () => fetchJson("/api/ai/scheduler-status"),
  refetchInterval: () => (document.hidden ? false : 30_000),
  staleTime: 15_000,
});

const jobs = computed(() => aiJobsQuery.data.value?.items || []);
const selectedJob = computed(() => jobs.value.find((job) => job.id === selectedJobId.value) || jobs.value[0] || null);

const historyQuery = useQuery({
  queryKey: computed(() => ["ai-job-history", selectedJob.value?.id]),
  queryFn: () => fetchJson(`/api/ai/jobs/${selectedJob.value.id}/history`),
  enabled: computed(() => !!selectedJob.value?.id),
  staleTime: 30_000,
});

const schedulerStatuses = computed(() => schedulerQuery.data.value?.db_job_statuses || []);
const schedulerStatusById = computed(() => {
  const map = new Map();
  for (const item of schedulerStatuses.value) map.set(item.id, item);
  return map;
});

const queryLoading = computed(() => aiJobsQuery.isLoading.value || schedulerQuery.isLoading.value);
const queryFetching = computed(() => aiJobsQuery.isFetching.value || schedulerQuery.isFetching.value);
const schedulerLoading = computed(() => schedulerQuery.isLoading.value);
const historyLoading = computed(() => historyQuery.isLoading.value);
// P2-4: 跟随 vue-query dataUpdatedAt，每次 30s 刷新重算，避免 keep-alive 下时间冻结
const queryUpdatedAt = computed(() => {
  void aiJobsQuery.dataUpdatedAt.value;
  return formatDateTime(new Date().toISOString());
});

const today = computed(() => {
  void aiJobsQuery.dataUpdatedAt.value;
  return todayIso();
});

const nowMinutes = computed(() => {
  // 依赖 dataUpdatedAt，past-due 判断才会随刷新前进
  void aiJobsQuery.dataUpdatedAt.value;
  void schedulerQuery.dataUpdatedAt.value;
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
});

function parseScheduleMinutes(label) {
  if (!label) return null;
  const m = String(label).match(/(\d{1,2}):(\d{2})/);
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

function deriveState(job) {
  if (!job.enabled) return "disabled";
  const latest = job.latest_run_summary;
  if (latest && latest.trading_date === today.value) {
    if (latest.status === "success") return "success";
    if (latest.status === "failed") return "failed";
    if (["running", "pending", "dispatched"].includes(latest.status)) return "running";
    return "unknown";
  }
  const sched = parseScheduleMinutes(job.schedule_label);
  if (sched !== null && sched < nowMinutes.value) return "past-due";
  return "upcoming";
}

const stateMeta = {
  success: { label: "已完成", color: "var(--success, #10b981)", emoji: "✓" },
  failed: { label: "失败", color: "#ef4444", emoji: "!" },
  running: { label: "运行中", color: "#06b6d4", emoji: "…" },
  "past-due": { label: "未执行", color: "#f59e0b", emoji: "?" },
  upcoming: { label: "待执行", color: "#94a3b8", emoji: "○" },
  disabled: { label: "已停用", color: "#475569", emoji: "—" },
  unknown: { label: "未知", color: "var(--text-muted, #94a3b8)", emoji: "?" },
};

const timelineGroups = computed(() => {
  const decorated = jobs.value
    .map((job) => ({
      ...job,
      _minutes: parseScheduleMinutes(job.schedule_label) ?? 9999,
      _state: deriveState(job),
      _scheduler: schedulerStatusById.value.get(job.id),
    }))
    .sort((a, b) => a._minutes - b._minutes || a.id - b.id);

  const order = ["盘前", "盘中", "盘后", "夜间", "周报"];
  const byGroup = new Map();
  for (const job of decorated) {
    const group = job.display_group || "其他";
    if (!byGroup.has(group)) byGroup.set(group, []);
    byGroup.get(group).push(job);
  }
  return order
    .filter((group) => byGroup.has(group))
    .map((group) => ({ group, jobs: byGroup.get(group) }))
    .concat(
      Array.from(byGroup.keys())
        .filter((group) => !order.includes(group))
        .map((group) => ({ group, jobs: byGroup.get(group) })),
    );
});

const summaryCards = computed(() => {
  const enabled = jobs.value.filter((job) => job.enabled).length;
  const todayRuns = jobs.value.map((job) => job.latest_run_summary).filter((run) => run?.trading_date === today.value);
  const success = todayRuns.filter((run) => run.status === "success").length;
  const failed = todayRuns.filter((run) => run.status === "failed").length;
  return {
    total: jobs.value.length,
    enabled,
    success,
    failed,
    registered: schedulerQuery.data.value?.registered_ai_skill_jobs ?? 0,
    schedulerRunning: !!schedulerQuery.data.value?.scheduler_running,
  };
});

const selectedHistory = computed(() => historyQuery.data.value?.runs || []);

function statusClass(status) {
  // 返回 StatusBadge 的 status prop 值
  if (status === "success") return "success";
  if (status === "failed") return "danger";
  if (["running", "pending", "dispatched"].includes(status)) return "warning";
  return "neutral";
}

function selectJob(job) {
  selectedJobId.value = job.id;
  actionError.value = "";
}

async function refreshAll() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["ai-jobs"] }),
    queryClient.invalidateQueries({ queryKey: ["ai-scheduler-status"] }),
    queryClient.invalidateQueries({ queryKey: ["ai-job-history"] }),
  ]);
}

async function executeNow(job) {
  if (executingIds.value.has(job.id)) return;
  actionError.value = "";
  executingIds.value = new Set([...executingIds.value, job.id]);
  try {
    await fetchJson(`/api/ai/jobs/${job.id}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    later(() => refreshAll(), 3_000);
  } catch (error) {
    actionError.value = `执行失败：${error.message || error}`;
  } finally {
    later(() => {
      const next = new Set(executingIds.value);
      next.delete(job.id);
      executingIds.value = next;
    }, 5_000);
  }
}

async function toggleJobEnabled(job) {
  actionError.value = "";
  try {
    await fetchJson(`/api/ai/jobs/${job.id}/toggle-enabled`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !job.enabled }),
    });
    await refreshAll();
  } catch (error) {
    actionError.value = `启停任务失败：${error.message || error}`;
  }
}

async function toggleJobSchedule(job) {
  actionError.value = "";
  try {
    await fetchJson(`/api/ai/jobs/${job.id}/toggle-schedule`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_schedule: !job.auto_schedule }),
    });
    await refreshAll();
  } catch (error) {
    actionError.value = `调整调度失败：${error.message || error}`;
  }
}

function goDetail(job, run = null) {
  const latest = run || job.latest_run_summary || {};
  const tradingDate = latest.trading_date || today.value;
  if (job.job_type === "news_scan") {
    router.push({ path: "/news" });
    return;
  }
  if (["day_review", "position_review", "weekly_review"].includes(job.job_type)) {
    router.push({ path: "/review", query: { trading_date: tradingDate, ...(latest.run_id || latest.id ? { run_id: String(latest.run_id || latest.id) } : {}) } });
    return;
  }
  const runId = latest.run_id || latest.id;
  if (runId) {
    router.push({ path: "/ai-center", query: { tab: "results", trading_date: tradingDate, run_id: String(runId) } });
    return;
  }
  selectJob(job);
}
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">自动化任务 · {{ today }}</p>
        <h2>AI任务</h2>
        <p class="hero-copy">查看定时任务、调度状态、最近运行结果，并支持手动执行。</p>
      </div>
      <div class="hero-actions">
        <button class="ghost-button" @click="refreshAll">刷新</button>
        <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
      </div>
    </header>

    <section class="card-grid">
      <MetricCard label="任务总数" :value="summaryCards.total" :sub-value="`${summaryCards.enabled} 个已启用`" :loading="queryLoading" trend="neutral" />
      <MetricCard label="调度器" :value="summaryCards.schedulerRunning ? '运行中' : '未运行'" :sub-value="`${summaryCards.registered} 个任务已注册`" :loading="schedulerLoading" :trend="summaryCards.schedulerRunning ? 'up' : 'down'" />
      <MetricCard label="今日完成" :value="summaryCards.success" :sub-value="`${today} 成功任务`" :loading="queryLoading" trend="up" />
      <MetricCard label="今日异常" :value="summaryCards.failed" sub-value="失败或需人工处理" :loading="queryLoading" :trend="summaryCards.failed ? 'down' : 'neutral'" />
    </section>

    <p v-if="actionError" class="error-banner">{{ actionError }}</p>

    <section class="job-layout">
      <DataPanel title="任务时间线" :subtitle="`当前 ${String(Math.floor(nowMinutes / 60)).padStart(2, '0')}:${String(nowMinutes % 60).padStart(2, '0')}`">
        <EmptyState v-if="!timelineGroups.length && !queryLoading" title="暂无 AI 任务" description="当前没有配置定时任务。" />
        <div v-for="section in timelineGroups" :key="section.group" class="timeline-section">
          <h3 class="timeline-group-label">{{ section.group }}</h3>
          <div class="timeline-rail">
            <article
              v-for="job in section.jobs"
              :key="job.id"
              class="timeline-card"
              :class="[`state-${job._state}`, { active: selectedJob?.id === job.id }]"
              @click="selectJob(job)"
            >
              <div class="card-head">
                <span class="time-label">{{ job.schedule_label || '--' }}</span>
                <span class="state-badge" :style="{ color: stateMeta[job._state].color }">
                  {{ stateMeta[job._state].emoji }} {{ stateMeta[job._state].label }}
                </span>
              </div>
              <h4 class="job-title">{{ job.skill_name || job.name }}</h4>
              <p v-if="job.latest_run_summary?.headline" class="job-headline">{{ job.latest_run_summary.headline }}</p>
              <p v-else class="job-headline placeholder">
                {{ job._state === "upcoming" ? "等待按时执行" : job._state === "past-due" ? "今日尚无产物" : "—" }}
              </p>
              <div class="job-meta-row">
                <span>{{ job.engine_type || 'claude-code' }}</span>
                <span>{{ job._scheduler?.registered_in_scheduler ? '已注册调度' : job.auto_schedule ? '待注册' : '手动' }}</span>
              </div>
              <div class="card-actions" @click.stop>
                <button
                  v-if="job.enabled"
                  class="action-btn primary"
                  :disabled="executingIds.has(job.id) || job._state === 'running'"
                  @click="executeNow(job)"
                >
                  {{ executingIds.has(job.id) ? "已派发…" : job._state === "running" ? "运行中…" : "立即执行" }}
                </button>
                <button class="action-btn ghost" @click="goDetail(job)">查看详情</button>
              </div>
            </article>
          </div>
        </div>
      </DataPanel>

      <DataPanel title="任务详情" :subtitle="selectedJob?.name || '选择左侧任务'">
        <EmptyState v-if="!selectedJob" title="请选择任务" description="点击任务卡片查看调度配置与运行历史。" />
        <template v-else>
          <div class="detail-stack">
            <div class="detail-row"><span>任务类型</span><strong>{{ selectedJob.job_type || '--' }}</strong></div>
            <div class="detail-row"><span>调度</span><strong>{{ selectedJob.schedule_rrule_or_cron || selectedJob.schedule_label || '--' }}</strong></div>
            <div class="detail-row"><span>执行引擎</span><strong>{{ selectedJob.engine_type || 'claude-code' }}</strong></div>
            <div class="detail-row"><span>上次执行</span><strong>{{ formatDateTime(selectedJob.last_executed_at || selectedJob.latest_run_summary?.finished_at) }}</strong></div>
          </div>

          <div class="toggle-grid">
            <label class="toggle-switch" :title="selectedJob.enabled ? '点击禁用' : '点击启用'">
              <input type="checkbox" :checked="selectedJob.enabled" @change="toggleJobEnabled(selectedJob)" />
              <span class="toggle-slider"></span>
              <span class="toggle-label">启用</span>
            </label>
            <label class="toggle-switch" :title="selectedJob.auto_schedule ? '关闭自动调度' : '开启自动调度'" :style="{ opacity: selectedJob.enabled ? 1 : 0.45 }">
              <input type="checkbox" :checked="selectedJob.auto_schedule" :disabled="!selectedJob.enabled" @change="toggleJobSchedule(selectedJob)" />
              <span class="toggle-slider"></span>
              <span class="toggle-label">调度</span>
            </label>
          </div>

          <div class="detail-actions">
            <button class="action-btn primary" :disabled="!selectedJob.enabled || executingIds.has(selectedJob.id)" @click="executeNow(selectedJob)">立即执行</button>
            <button class="action-btn ghost" @click="goDetail(selectedJob)">查看最新结果</button>
          </div>

          <section class="history-section">
            <h4>最近运行</h4>
            <div v-if="historyLoading" class="history-hint">加载运行历史...</div>
            <button v-for="run in selectedHistory.slice(0, 8)" :key="run.id" class="run-row" @click="goDetail(selectedJob, run)">
              <span class="run-name">{{ run.trading_date }}</span>
              <StatusBadge :status="statusClass(run.status)">{{ run.status }}</StatusBadge>
              <span class="run-duration">{{ run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '--' }}</span>
              <span>{{ formatDateTime(run.finished_at || run.started_at) }}</span>
            </button>
            <div v-if="!historyLoading && !selectedHistory.length" class="history-hint">暂无运行历史</div>
          </section>
        </template>
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
.hero-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.error-banner {
  margin: 0;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: #fecaca;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.22);
  font-size: 13px;
}

.job-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
  gap: var(--space-4);
  align-items: start;
}

.timeline-section + .timeline-section {
  margin-top: var(--space-4);
}

.timeline-group-label {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.timeline-rail {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-3);
}

.timeline-card {
  position: relative;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  cursor: pointer;
  transition: all var(--transition-fast);
  display: grid;
  gap: 6px;
  min-height: 150px;
}

.timeline-card:hover,
.timeline-card.active {
  border-color: var(--accent, #06b6d4);
  transform: translateY(-1px);
}

.timeline-card.state-success { border-left: 3px solid var(--up, #ef4444); }
.timeline-card.state-failed { border-left: 3px solid #ef4444; }
.timeline-card.state-running { border-left: 3px solid #06b6d4; }
.timeline-card.state-past-due { border-left: 3px solid #f59e0b; }
.timeline-card.state-upcoming { border-left: 3px solid rgba(148, 163, 184, 0.4); }
.timeline-card.state-disabled { border-left: 3px solid rgba(71, 85, 105, 0.4); opacity: 0.55; }

.card-head,
.job-meta-row,
.detail-row,
.run-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.time-label {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.state-badge,
.job-meta-row,
.run-duration {
  font-size: 11px;
  font-weight: 600;
}

.job-meta-row,
.run-duration {
  color: var(--text-muted);
}

.job-title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text);
}

.job-headline {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.job-headline.placeholder {
  color: var(--text-muted);
  font-style: italic;
}

.card-actions,
.detail-actions,
.toggle-grid {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.action-btn {
  flex: 1;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.action-btn.primary {
  background: var(--accent-soft, rgba(6, 182, 212, 0.1));
  color: var(--accent, #06b6d4);
  border-color: rgba(6, 182, 212, 0.3);
}

.action-btn.primary:hover:not(:disabled) { background: rgba(6, 182, 212, 0.18); }
.action-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn.ghost { background: transparent; color: var(--text-secondary); border-color: var(--border); }
.action-btn.ghost:hover { background: rgba(255, 255, 255, 0.04); color: var(--text); }

.detail-stack {
  display: grid;
  gap: 10px;
  margin-bottom: var(--space-4);
}

.detail-row {
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 13px;
}

.detail-row strong {
  color: var(--text);
  text-align: right;
}

.toggle-grid {
  margin-bottom: var(--space-4);
}

.toggle-switch { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.toggle-switch input { display: none; }
.toggle-slider { position: relative; width: 36px; height: 20px; border-radius: 20px; background: rgba(148,163,184,0.2); transition: background 0.2s ease; flex-shrink: 0; }
.toggle-slider::after { content: ''; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #94a3b8; transition: all 0.2s ease; }
.toggle-switch input:checked + .toggle-slider { background: rgba(74,222,128,0.3); }
.toggle-switch input:checked + .toggle-slider::after { transform: translateX(16px); background: var(--success, #10b981); }
.toggle-switch input:disabled + .toggle-slider { opacity: 0.4; cursor: not-allowed; }
.toggle-label { font-size: 12px; color: var(--text-muted); min-width: 28px; }

.history-section {
  margin-top: var(--space-5);
  display: grid;
  gap: 8px;
}

.history-section h4 {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.run-row {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
}

.run-row:hover { border-color: var(--accent); color: var(--text); }
.run-name { font-weight: 700; color: var(--text); }
.history-hint { color: var(--text-muted); font-size: 13px; padding: 8px 0; }

@media (max-width: 1100px) {
  .job-layout { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .timeline-rail { grid-template-columns: 1fr; }
  .hero-actions { justify-content: flex-start; }
}
</style>
