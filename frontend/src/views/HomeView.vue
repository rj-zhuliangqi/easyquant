<script setup>
import { computed, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRouter } from "vue-router";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatAmount, formatDateTime, formatNumber, formatPercent } from "../lib/formatters";

defineOptions({ name: "home" });

const router = useRouter();
const queryClient = useQueryClient();

const selectedSymbol = ref("sh000001");

const pageQuery = useQuery({
  queryKey: pageQueryKey("home"),
  queryFn: () => fetchJson("/api/page/home"),
});

// AI jobs list — drives the timeline. Refreshes every 30s so manual /
// scheduled runs show up without a full page reload.
const aiJobsQuery = useQuery({
  queryKey: ["ai-jobs"],
  queryFn: () => fetchJson("/api/ai/jobs"),
  refetchInterval: 30_000,
  staleTime: 15_000,
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const marketOverview = computed(() => payload.value.market_overview ?? {});
const systemSummary = computed(() => payload.value.system_summary ?? {});
const status = computed(() => payload.value.status ?? {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(pageQuery.data.value?.updated_at));
const selectedIndex = computed(
  () => (marketOverview.value.indices || []).find((item) => item.symbol === selectedSymbol.value) || marketOverview.value.indices?.[0] || null,
);

// ── Timeline helpers ──
const today = computed(() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
});

const nowMinutes = computed(() => {
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
});

function parseScheduleMinutes(label) {
  // schedule_label looks like "08:20", "09:26", "周五22:00"
  if (!label) return null;
  const m = String(label).match(/(\d{1,2}):(\d{2})/);
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

// Sort all jobs by schedule time of day, then bucket them by display_group.
const timelineGroups = computed(() => {
  const items = aiJobsQuery.data.value?.items || [];
  const decorated = items
    .map((j) => ({
      ...j,
      _minutes: parseScheduleMinutes(j.schedule_label) ?? 9999,
      _state: deriveState(j),
    }))
    .sort((a, b) => a._minutes - b._minutes);

  // Preserve canonical group order regardless of how the API returned them.
  const ORDER = ["盘前", "盘中", "盘后", "夜间", "周报"];
  const byGroup = new Map();
  for (const job of decorated) {
    const group = job.display_group || "其他";
    if (!byGroup.has(group)) byGroup.set(group, []);
    byGroup.get(group).push(job);
  }
  return ORDER.filter((g) => byGroup.has(g))
    .map((g) => ({ group: g, jobs: byGroup.get(g) }))
    .concat(
      Array.from(byGroup.keys())
        .filter((g) => !ORDER.includes(g))
        .map((g) => ({ group: g, jobs: byGroup.get(g) })),
    );
});

function deriveState(job) {
  // Returns: 'success' | 'failed' | 'running' | 'pending' | 'past-due' | 'upcoming' | 'disabled'
  if (!job.enabled) return "disabled";
  const latest = job.latest_run_summary;
  if (latest && latest.trading_date === today.value) {
    if (latest.status === "success") return "success";
    if (latest.status === "failed") return "failed";
    if (latest.status === "running") return "running";
    return "success"; // any other terminal status — treat as completed
  }
  const sched = parseScheduleMinutes(job.schedule_label);
  if (sched !== null && sched < nowMinutes.value) return "past-due";
  return "upcoming";
}

const stateMeta = {
  success: { label: "已完成", color: "var(--up, #ef4444)", emoji: "✓" },
  failed: { label: "失败", color: "#ef4444", emoji: "!" },
  running: { label: "运行中", color: "#06b6d4", emoji: "…" },
  "past-due": { label: "未执行", color: "#f59e0b", emoji: "?" },
  upcoming: { label: "待执行", color: "#94a3b8", emoji: "○" },
  disabled: { label: "已停用", color: "#475569", emoji: "—" },
};

// Manual execute — fire-and-forget; UI polls via refetchInterval.
const executingIds = ref(new Set());

async function executeNow(job) {
  if (executingIds.value.has(job.id)) return;
  executingIds.value = new Set([...executingIds.value, job.id]);
  try {
    await fetchJson(`/api/ai/jobs/${job.id}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    // Optimistic — refetch in 3s so users see status flip to running/success.
    setTimeout(() => queryClient.invalidateQueries({ queryKey: ["ai-jobs"] }), 3_000);
  } catch (e) {
    console.error("manual execute failed", e);
    alert(`执行失败: ${e.message || e}`);
  } finally {
    setTimeout(() => {
      const next = new Set(executingIds.value);
      next.delete(job.id);
      executingIds.value = next;
    }, 5_000);
  }
}

function goDetail(job) {
  // Route to the most relevant detail view for this job type.
  if (job.job_type === "news_scan") {
    router.push({ path: "/news" });
    return;
  }
  // Other types — go to AI center on the results tab, filtered by job name.
  router.push({ path: "/ai-center", query: { tab: "results", job: job.name } });
}

const chartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 24, right: 16, top: 28, bottom: 24 },
  xAxis: {
    type: "category",
    data: (selectedIndex.value?.points || []).map((item) => item.label),
    boundaryGap: false,
  },
  yAxis: { type: "value", scale: true },
  series: [
    {
      type: "line",
      smooth: true,
      data: (selectedIndex.value?.points || []).map((item) => item.value),
      areaStyle: {
        color: {
          type: "linear",
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(6, 182, 212, 0.3)" },
            { offset: 1, color: "rgba(6, 182, 212, 0.02)" },
          ],
        },
      },
      lineStyle: { width: 2, color: "#06b6d4" },
      showSymbol: false,
      color: "#06b6d4",
    },
  ],
}));
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">今日 AI 工作台 · {{ today }}</p>
        <h2>盘中脉搏 + AI 任务时间线</h2>
        <p class="hero-copy">从盘前到夜间，AI Skill 按时段自动执行；点卡片查看详情，或手动立即执行。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <!-- ═══ AI Timeline (the new heart of the home page) ═══ -->
    <DataPanel title="今日 AI 任务时间线" :subtitle="`${nowMinutes >= 1440 ? '次日' : '当前'} ${String(Math.floor(nowMinutes/60)).padStart(2,'0')}:${String(nowMinutes%60).padStart(2,'0')}`">
      <div v-for="section in timelineGroups" :key="section.group" class="timeline-section">
        <h3 class="timeline-group-label">{{ section.group }}</h3>
        <div class="timeline-rail">
          <article
            v-for="job in section.jobs"
            :key="job.id"
            class="timeline-card"
            :class="[`state-${job._state}`]"
            @click="goDetail(job)"
          >
            <div class="card-head">
              <span class="time-label">{{ job.schedule_label }}</span>
              <span class="state-badge" :style="{ color: stateMeta[job._state].color }">
                {{ stateMeta[job._state].emoji }} {{ stateMeta[job._state].label }}
              </span>
            </div>
            <h4 class="job-title">{{ job.skill_name || job.name }}</h4>
            <p v-if="job.latest_run_summary?.headline" class="job-headline">
              {{ job.latest_run_summary.headline }}
            </p>
            <p v-else class="job-headline placeholder">
              {{ job._state === "upcoming" ? "等待按时执行" : job._state === "past-due" ? "今日尚无产物" : "—" }}
            </p>
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

    <!-- ═══ Market overview (original) ═══ -->
    <section class="card-grid">
      <MetricCard
        label="监控状态"
        :value="status.market_open ? '盘中运行' : '非交易时段'"
        :sub-value="formatDateTime(status.updated_at)"
        :loading="queryLoading"
        trend="neutral"
      />
      <MetricCard
        label="最强流入板块"
        :value="systemSummary.sector_monitor?.strongest_inflow_sector || '--'"
        :sub-value="formatAmount(systemSummary.sector_monitor?.strongest_inflow_amount)"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="最高连板"
        :value="systemSummary.limit_up_ladder?.highest_board ?? '--'"
        :sub-value="`晋级率 ${formatPercent((systemSummary.limit_up_ladder?.promotion_rate || 0) * 100)}`"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="上涨 / 下跌"
        :value="`${marketOverview.breadth?.up_count ?? 0} / ${marketOverview.breadth?.down_count ?? 0}`"
        :sub-value="`活跃度 ${formatPercent(marketOverview.breadth?.market_activity)}`"
        :loading="queryLoading"
        :trend="(marketOverview.breadth?.up_count || 0) > (marketOverview.breadth?.down_count || 0) ? 'up' : 'down'"
      />
    </section>

    <DataPanel title="指数趋势" :subtitle="selectedIndex?.name || '等待数据'">
      <template #actions>
        <div class="switch-row">
          <button
            v-for="item in marketOverview.indices || []"
            :key="item.symbol"
            class="ghost-button"
            :class="{ active: selectedSymbol === item.symbol }"
            @click="selectedSymbol = item.symbol"
          >
            {{ item.name }}
          </button>
        </div>
      </template>
      <EChartPanel :option="chartOption" />
    </DataPanel>

    <section class="card-grid two-up">
      <DataPanel title="指数快照">
        <div class="list-stack">
          <div v-for="item in marketOverview.indices || []" :key="item.symbol" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ formatNumber(item.price) }}</span>
            <small :class="{ 'text-success': (item.change_percent || 0) > 0, 'text-danger': (item.change_percent || 0) < 0 }">
              {{ formatPercent(item.change_percent) }}
            </small>
          </div>
        </div>
      </DataPanel>

      <DataPanel title="行动优先级">
        <div class="detail-block">
          <strong>{{ systemSummary.action_priority?.title || "--" }}</strong>
          <p>{{ systemSummary.action_priority?.reason || "等待数据" }}</p>
          <small>告警 {{ systemSummary.alert_summary?.count ?? 0 }} 条，机会 {{ systemSummary.opportunity_summary?.count ?? 0 }} 个</small>
        </div>
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
.timeline-section + .timeline-section {
  margin-top: var(--space-3);
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
  min-height: 130px;
}

.timeline-card:hover {
  border-color: var(--accent, #06b6d4);
  transform: translateY(-1px);
}

.timeline-card.state-success {
  border-left: 3px solid var(--up, #ef4444);
}

.timeline-card.state-failed {
  border-left: 3px solid #ef4444;
}

.timeline-card.state-running {
  border-left: 3px solid #06b6d4;
}

.timeline-card.state-past-due {
  border-left: 3px solid #f59e0b;
  opacity: 0.85;
}

.timeline-card.state-upcoming {
  border-left: 3px solid rgba(148, 163, 184, 0.4);
  opacity: 0.7;
}

.timeline-card.state-disabled {
  border-left: 3px solid rgba(71, 85, 105, 0.4);
  opacity: 0.4;
  cursor: not-allowed;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.time-label {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.state-badge {
  font-size: 11px;
  font-weight: 600;
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

.card-actions {
  display: flex;
  gap: 6px;
  margin-top: auto;
  padding-top: 4px;
}

.action-btn {
  flex: 1;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.action-btn.primary {
  background: var(--accent-soft, rgba(6, 182, 212, 0.1));
  color: var(--accent, #06b6d4);
  border-color: rgba(6, 182, 212, 0.3);
}

.action-btn.primary:hover:not(:disabled) {
  background: rgba(6, 182, 212, 0.18);
}

.action-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.ghost {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border, rgba(255, 255, 255, 0.08));
}

.action-btn.ghost:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

@media (max-width: 640px) {
  .timeline-rail {
    grid-template-columns: 1fr;
  }
}
</style>
