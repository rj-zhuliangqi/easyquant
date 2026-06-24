<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "news" });

// Default: today, formatted YYYY-MM-DD (local time).
function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const selectedDate = ref(todayIso());

// Fetch all news_scan runs; we then pick the latest for the selected date
// client-side. The backend route is generic — no new API needed.
const newsQuery = useQuery({
  queryKey: computed(() => ["ai-runs", "news_scan", selectedDate.value]),
  queryFn: () =>
    fetchJson(`/api/ai/runs?job_type=news_scan&trading_date=${selectedDate.value}`),
  staleTime: 30_000,
});

const items = computed(() => newsQuery.data.value?.items ?? []);

// The list is already ordered by started_at desc in the backend, so first item
// is the most recent run for the day. Some days may have multiple re-runs.
const activeRun = computed(() => items.value[0] ?? null);

const resultPayload = computed(() => activeRun.value?.result_payload ?? {});
const summary = computed(() => {
  // structured_summary lives on the run; backend serializes it into
  // structured_summary when present, but list_runs only exposes it inside
  // result_payload depending on the path. Fall back to either.
  const fromRun = activeRun.value?.structured_summary || activeRun.value?.summary;
  if (fromRun && Object.keys(fromRun).length) return fromRun;
  return resultPayload.value?.summary || {};
});

const headlineItems = computed(() => resultPayload.value?.headline_items || []);
const marketImplications = computed(() => resultPayload.value?.market_implications || []);
const watchThemes = computed(() => resultPayload.value?.watch_themes || []);

const dataSources = computed(() => {
  const meta = activeRun.value?.meta || activeRun.value?._meta || {};
  return meta?.data_sources_used || [];
});

const finishedAt = computed(() => formatDateTime(activeRun.value?.finished_at));

const queryLoading = computed(() => newsQuery.isLoading.value);
const queryFetching = computed(() => newsQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(activeRun.value?.finished_at));

function impactClass(impact) {
  if (!impact) return "tag-neutral";
  const lower = String(impact).toLowerCase();
  if (lower === "positive" || lower === "正面" || lower === "利好") return "tag-up";
  if (lower === "negative" || lower === "负面" || lower === "利空") return "tag-down";
  return "tag-neutral";
}

function impactLabel(impact) {
  if (!impact) return "中性";
  const lower = String(impact).toLowerCase();
  if (lower === "positive") return "利好";
  if (lower === "negative") return "利空";
  if (lower === "neutral") return "中性";
  return impact;
}

// Step the date by ±1 day
function shiftDate(delta) {
  const [y, m, d] = selectedDate.value.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  const yy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  selectedDate.value = `${yy}-${mm}-${dd}`;
}

function goToday() {
  selectedDate.value = todayIso();
}

watch(selectedDate, () => {
  // Vue-query auto-refetches via the reactive queryKey.
});
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">每日 08:20 · AI 消息面</p>
        <h2>盘前消息面</h2>
        <p class="hero-copy">
          自动抓取东财 / 新浪 / 同花顺 等多源新闻，AI 归纳为头条 / 市场影响 / 题材关注。
        </p>
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
      <span v-if="activeRun" class="finished-at">完成于 {{ finishedAt }}</span>
      <span v-if="dataSources.length" class="sources">
        数据源:
        <span v-for="src in dataSources" :key="src" class="source-badge">{{ src }}</span>
      </span>
    </section>

    <EmptyState
      v-if="!activeRun && !queryLoading"
      title="当日暂无消息面分析"
      description="该交易日没有产出 0820 消息面挖掘任务，或任务尚未执行。可切换其他日期查看。"
    />

    <template v-if="activeRun">
      <!-- summary block -->
      <DataPanel v-if="summary && Object.keys(summary).length" title="今日定调">
        <div v-if="summary.market_phase" class="phase-block">
          <span class="phase-label">市场阶段</span>
          <p class="phase-text">{{ summary.market_phase }}</p>
        </div>
        <div v-if="Array.isArray(summary.hot_sectors) && summary.hot_sectors.length" class="summary-block">
          <span class="block-label">热点板块</span>
          <ul class="bullet-list bullet-up">
            <li v-for="(s, i) in summary.hot_sectors" :key="`hs-${i}`">{{ s }}</li>
          </ul>
        </div>
        <div v-if="Array.isArray(summary.risk_signals) && summary.risk_signals.length" class="summary-block">
          <span class="block-label">风险信号</span>
          <ul class="bullet-list bullet-down">
            <li v-for="(s, i) in summary.risk_signals" :key="`rs-${i}`">{{ s }}</li>
          </ul>
        </div>
      </DataPanel>

      <!-- headline_items: news cards -->
      <DataPanel v-if="headlineItems.length" :title="`头条新闻 · ${headlineItems.length}`">
        <div class="headline-grid">
          <article v-for="(item, i) in headlineItems" :key="`hl-${i}`" class="headline-card">
            <header class="headline-header">
              <span :class="['impact-tag', impactClass(item.impact)]">{{ impactLabel(item.impact) }}</span>
              <h3 class="headline-title">{{ item.title }}</h3>
            </header>
            <p v-if="item.detail" class="headline-detail">{{ item.detail }}</p>
            <footer v-if="item.affected_sectors?.length || item.affected_stocks?.length" class="headline-tags">
              <span v-for="(s, idx) in item.affected_sectors || []" :key="`sec-${i}-${idx}`" class="chip chip-sector">
                {{ s }}
              </span>
              <span v-for="(s, idx) in item.affected_stocks || []" :key="`stk-${i}-${idx}`" class="chip chip-stock">
                {{ s }}
              </span>
            </footer>
          </article>
        </div>
      </DataPanel>

      <!-- market_implications: simple bullet list -->
      <DataPanel v-if="marketImplications.length" :title="`市场影响 · ${marketImplications.length}`">
        <ol class="implication-list">
          <li v-for="(text, i) in marketImplications" :key="`mi-${i}`">{{ text }}</li>
        </ol>
      </DataPanel>

      <!-- watch_themes -->
      <DataPanel v-if="watchThemes.length" :title="`关注题材 · ${watchThemes.length}`">
        <div class="theme-grid">
          <article v-for="(theme, i) in watchThemes" :key="`th-${i}`" class="theme-card">
            <h3 class="theme-title">{{ theme.theme }}</h3>
            <p v-if="theme.reason" class="theme-reason">{{ theme.reason }}</p>
            <div v-if="theme.stocks?.length" class="theme-stocks">
              <span v-for="(s, idx) in theme.stocks" :key="`ts-${i}-${idx}`" class="chip chip-stock">{{ s }}</span>
            </div>
          </article>
        </div>
      </DataPanel>

      <EmptyState
        v-if="!headlineItems.length && !marketImplications.length && !watchThemes.length"
        title="本期产物未包含新闻明细"
        description="该日 0820 任务可能直接走 stock_pick 模式，未拆分 headline_items / market_implications / watch_themes 三段。"
      />
    </template>
  </section>
</template>

<style scoped>
.page {
  display: grid;
  gap: var(--space-4);
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

.page-hero h2 {
  margin: 4px 0 0;
  font-size: 22px;
  letter-spacing: -0.02em;
}

.hero-copy {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 13px;
  max-width: 60ch;
}

/* Filter row */
.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-alt, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  font-size: 13px;
}

.date-picker {
  display: flex;
  align-items: center;
  gap: 4px;
}

.date-step {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
}

.date-step:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.date-input {
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  background: rgba(0, 0, 0, 0.2);
  color: var(--text);
  font-size: 13px;
  color-scheme: dark;
}

.today-btn {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(6, 182, 212, 0.3);
  background: var(--accent-soft, rgba(6, 182, 212, 0.08));
  color: var(--accent);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.finished-at {
  color: var(--text-muted);
  font-size: 12px;
}

.sources {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--text-muted);
  font-size: 11px;
  margin-left: auto;
}

.source-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-secondary);
  font-size: 11px;
  border: 1px solid rgba(148, 163, 184, 0.12);
}

/* Summary block */
.phase-block {
  margin-bottom: var(--space-3);
}

.phase-label,
.block-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.phase-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(6, 182, 212, 0.06);
  border-left: 3px solid var(--accent);
}

.summary-block {
  margin-top: var(--space-3);
}

.bullet-list {
  margin: 4px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.bullet-list li {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text);
}

.bullet-up li::marker {
  color: var(--up, #ef4444);
}

.bullet-down li::marker {
  color: var(--down, #10b981);
}

/* Headline cards */
.headline-grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.headline-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  display: grid;
  gap: 8px;
}

.headline-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.impact-tag {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.tag-up {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.25);
}

.tag-down {
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.tag-neutral {
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.headline-title {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  font-weight: 600;
}

.headline-detail {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.headline-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
}

.chip {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}

.chip-sector {
  background: rgba(6, 182, 212, 0.1);
  color: #67e8f9;
  border: 1px solid rgba(6, 182, 212, 0.25);
}

.chip-stock {
  background: rgba(245, 158, 11, 0.1);
  color: #fcd34d;
  border: 1px solid rgba(245, 158, 11, 0.25);
}

/* Implications list */
.implication-list {
  margin: 0;
  padding-left: 22px;
  display: grid;
  gap: 8px;
}

.implication-list li {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text);
}

/* Theme grid */
.theme-grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}

.theme-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  display: grid;
  gap: 6px;
}

.theme-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
}

.theme-reason {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-secondary);
}

.theme-stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

@media (max-width: 640px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }
  .sources {
    margin-left: 0;
  }
  .headline-grid,
  .theme-grid {
    grid-template-columns: 1fr;
  }
}
</style>
