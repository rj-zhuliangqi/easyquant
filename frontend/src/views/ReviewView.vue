<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "review" });

const route = useRoute();
const router = useRouter();

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const selectedDate = ref(typeof route.query.trading_date === "string" ? route.query.trading_date : todayIso());

watch(
  () => route.query.trading_date,
  (value) => {
    if (typeof value === "string" && value !== selectedDate.value) selectedDate.value = value;
  },
);

watch(selectedDate, (value) => {
  const nextQuery = { ...route.query, trading_date: value };
  if (nextQuery.trading_date !== route.query.trading_date) {
    router.replace({ path: route.path, query: nextQuery }).catch(() => {});
  }
});

const reviewQuery = useQuery({
  queryKey: computed(() => ["ai-trading-day-review", selectedDate.value]),
  queryFn: () => fetchJson(`/api/ai/trading-days/${selectedDate.value}`),
  staleTime: 30_000,
});

const runsQuery = useQuery({
  queryKey: computed(() => ["ai-review-runs", selectedDate.value]),
  queryFn: () => fetchJson(`/api/ai/runs?trading_date=${selectedDate.value}`),
  staleTime: 30_000,
});

const review = computed(() => reviewQuery.data.value || {});
const reviewRuns = computed(() =>
  (runsQuery.data.value?.items || []).filter((run) => ["day_review", "position_review", "weekly_review"].includes(run.job_type)),
);

const queryLoading = computed(() => reviewQuery.isLoading.value || runsQuery.isLoading.value);
const queryFetching = computed(() => reviewQuery.isFetching.value || runsQuery.isFetching.value);
const runsLoading = computed(() => runsQuery.isLoading.value);
const queryUpdatedAt = computed(() => formatDateTime(reviewQuery.dataUpdatedAt.value ? new Date(reviewQuery.dataUpdatedAt.value).toISOString() : null));

const sections = computed(() => [
  { key: "market_summary", title: "市场概况", empty: "暂无市场概况" },
  { key: "top_themes", title: "主线板块", empty: "暂无主线板块" },
  { key: "failed_patterns", title: "失败模式", empty: "暂无失败模式" },
  { key: "recommended_picks_review", title: "推荐复盘", empty: "暂无推荐复盘" },
  { key: "position_review", title: "持仓复盘", empty: "暂无持仓复盘" },
  { key: "lesson_items", title: "经验条目", empty: "暂无经验条目" },
  { key: "next_day_focus", title: "次日关注", empty: "暂无次日关注" },
]);

function hasValue(value) {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return String(value).trim().length > 0;
}

const hasAnyReview = computed(() => sections.value.some((section) => hasValue(review.value?.[section.key])));

function displayValue(value) {
  if (value == null || value === "") return "--";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function shiftDate(delta) {
  const [y, m, d] = selectedDate.value.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  selectedDate.value = `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}-${String(dt.getUTCDate()).padStart(2, "0")}`;
}

function goToday() {
  selectedDate.value = todayIso();
}

function openRun(run) {
  router.push({ path: "/ai-center", query: { tab: "results", trading_date: run.trading_date, run_id: String(run.id) } });
}
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">盘后复盘 · {{ selectedDate }}</p>
        <h2>复盘中心</h2>
        <p class="hero-copy">聚合每日复盘、持仓复盘与经验条目，沉淀次日关注方向。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <section class="filter-row">
      <div class="date-picker">
        <button class="date-step" @click="shiftDate(-1)" title="前一天">‹</button>
        <input v-model="selectedDate" type="date" class="date-input" />
        <button class="date-step" @click="shiftDate(1)" title="后一天">›</button>
        <button class="today-btn" @click="goToday">今天</button>
      </div>
    </section>

    <EmptyState v-if="!hasAnyReview && !queryLoading" title="当日暂无复盘" description="该交易日尚未生成复盘数据，可切换其他日期查看。" />

    <section v-if="hasAnyReview" class="review-grid">
      <DataPanel v-for="section in sections" :key="section.key" :title="section.title">
        <template v-if="hasValue(review[section.key])">
          <div v-if="Array.isArray(review[section.key])" class="chip-list">
            <article v-for="(item, index) in review[section.key]" :key="index" class="review-chip-card">
              <pre>{{ displayValue(item) }}</pre>
            </article>
          </div>
          <pre v-else class="review-text">{{ displayValue(review[section.key]) }}</pre>
        </template>
        <p v-else class="muted-text">{{ section.empty }}</p>
      </DataPanel>
    </section>

    <DataPanel title="复盘运行记录" class="mt-lg">
      <div v-if="reviewRuns.length" class="run-list">
        <button v-for="run in reviewRuns" :key="run.id" class="run-row" @click="openRun(run)">
          <span class="run-name">{{ run.job_name || run.skill_name || '复盘任务' }}</span>
          <span class="run-type">{{ run.job_type }}</span>
          <span class="run-date">{{ formatDateTime(run.finished_at || run.started_at) }}</span>
          <span class="status-badge" :class="run.status === 'success' ? 'status-success' : run.status === 'failed' ? 'status-danger' : 'status-neutral'">
            {{ run.status }}
          </span>
        </button>
      </div>
      <EmptyState v-else-if="!runsLoading" title="暂无运行记录" description="当天没有复盘类 AI 任务运行记录。" />
    </DataPanel>
  </section>
</template>

<style scoped>
.filter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.date-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-step,
.today-btn,
.date-input {
  padding: 7px 10px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 13px;
}

.date-step,
.today-btn {
  cursor: pointer;
}

.date-step:hover,
.today-btn:hover {
  border-color: var(--border-hover);
  background: var(--surface-hover);
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-4);
}

.review-text,
.review-chip-card pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.7;
  color: var(--text-secondary);
  font-size: 13px;
}

.chip-list {
  display: grid;
  gap: 10px;
}

.review-chip-card {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border);
}

.muted-text {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

.run-list {
  display: grid;
  gap: 8px;
}

.run-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
  color: var(--text-secondary);
  cursor: pointer;
}

.run-row:hover {
  border-color: var(--accent);
  color: var(--text);
}

.run-name {
  flex: 1;
  text-align: left;
  font-weight: 600;
  color: var(--text);
}

.run-type,
.run-date {
  font-size: 12px;
  color: var(--text-muted);
}

.status-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px; }
.status-success { color: #4ade80; background: rgba(74,222,128,0.1); }
.status-danger { color: #f87171; background: rgba(248,113,113,0.1); }
.status-neutral { color: #94a3b8; background: rgba(148,163,184,0.08); }
.mt-lg { margin-top: var(--space-4); }

@media (max-width: 640px) {
  .review-grid { grid-template-columns: 1fr; }
  .run-row { flex-wrap: wrap; }
}
</style>
