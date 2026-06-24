<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import RealtimeFeed from "../components/news/RealtimeFeed.vue";
import { fetchJson } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "news" });

// ── Tab state — URL 持久化（?tab=live / 默认 daily）
// 与 AiCenterView 一致的做法：path-level alias 不适用，仅靠 query.tab
const TAB_KEYS = ["daily", "live"];
const route = useRoute();
const router = useRouter();

function initialTabFromRoute() {
  const fromQuery = route.query?.tab;
  if (typeof fromQuery === "string" && TAB_KEYS.includes(fromQuery)) return fromQuery;
  return "daily";
}

const activeTab = ref(initialTabFromRoute());

watch(
  () => route.query.tab,
  () => {
    const next = initialTabFromRoute();
    if (next !== activeTab.value) activeTab.value = next;
  },
);

watch(activeTab, (next) => {
  const currentQuery = { ...route.query };
  if (next === "daily") delete currentQuery.tab;
  else currentQuery.tab = next;
  if (currentQuery.tab !== route.query.tab) {
    router.replace({ path: route.path, query: currentQuery }).catch(() => {});
  }
});

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

// 兼容 stock_pick 风格产物：6 月起 0820 任务改产 structured_picks（按个股推荐
// 而非按新闻头条），同时仍保留 structured_summary 三段定调 + raw_output_text
// 完整 HTML 报告。前端把这些都渲染出来，而不是显示空态。
const structuredPicks = computed(() => resultPayload.value?.structured_picks || []);
const rawOutputHtml = computed(() => activeRun.value?.raw_output_text || activeRun.value?.raw_output || "");

const hasAnyContent = computed(
  () =>
    headlineItems.value.length > 0 ||
    marketImplications.value.length > 0 ||
    watchThemes.value.length > 0 ||
    structuredPicks.value.length > 0 ||
    Object.keys(summary.value).length > 0 ||
    rawOutputHtml.value.length > 0,
);

const showRawOutput = ref(false);

function pickLevelBadge(level) {
  if (!level) return null;
  const map = {
    strong_recommend: { label: "强烈推荐", cls: "level-strong" },
    recommend: { label: "推荐", cls: "level-rec" },
    watch: { label: "观察", cls: "level-watch" },
    hold: { label: "持仓", cls: "level-hold" },
  };
  return map[level] || { label: String(level), cls: "level-other" };
}

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

    <!-- Tab Bar — AI 日报 / 即时资讯 -->
    <nav class="news-tabs">
      <button
        class="news-tab-btn"
        :class="{ active: activeTab === 'daily' }"
        @click="activeTab = 'daily'"
      >
        <span class="tab-icon">📰</span>
        <span class="tab-label">AI 日报 · 每日 08:20</span>
      </button>
      <button
        class="news-tab-btn"
        :class="{ active: activeTab === 'live' }"
        @click="activeTab = 'live'"
      >
        <span class="tab-icon">⚡</span>
        <span class="tab-label">即时资讯 · 实时</span>
      </button>
    </nav>

    <!-- Tab: AI 日报（原有内容完全保留） -->
    <template v-if="activeTab === 'daily'">
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

      <!-- structured_picks：6 月起 0820 任务改产的「个股推荐池」 -->
      <DataPanel v-if="structuredPicks.length" :title="`重点个股 · ${structuredPicks.length}`">
        <div class="pick-grid">
          <article v-for="(pick, i) in structuredPicks" :key="`pk-${i}`" class="pick-card">
            <header class="pick-head">
              <span class="pick-code">{{ pick.stock_code }}</span>
              <span class="pick-name">{{ pick.stock_name }}</span>
              <span
                v-if="pickLevelBadge(pick.pick_level)"
                :class="['pick-level-badge', pickLevelBadge(pick.pick_level).cls]"
              >
                {{ pickLevelBadge(pick.pick_level).label }}
              </span>
              <span v-if="pick.sector_name" class="chip chip-sector">{{ pick.sector_name }}</span>
            </header>
            <p v-if="pick.reason_summary" class="pick-reason">{{ pick.reason_summary }}</p>
            <p v-if="pick.reason_detail" class="pick-detail">{{ pick.reason_detail }}</p>
            <footer v-if="pick.theme_tags?.length || pick.entry_hint" class="pick-meta">
              <span
                v-for="(tag, idx) in pick.theme_tags || []"
                :key="`pkt-${i}-${idx}`"
                class="chip chip-theme"
              >
                {{ tag }}
              </span>
              <span v-if="pick.entry_hint" class="pick-entry-hint">入场提示：{{ pick.entry_hint }}</span>
            </footer>
          </article>
        </div>
      </DataPanel>

      <!-- raw_output：完整 HTML 报告（折叠展开，避免一上来铺满屏幕） -->
      <DataPanel v-if="rawOutputHtml">
        <template #header>
          <div class="raw-output-header">
            <h3 class="panel-title-inline">完整分析报告</h3>
            <button class="toggle-btn" @click="showRawOutput = !showRawOutput">
              {{ showRawOutput ? "收起" : "展开" }}
            </button>
          </div>
        </template>
        <div v-show="showRawOutput" class="raw-output-body" v-html="rawOutputHtml"></div>
        <p v-if="!showRawOutput" class="raw-output-hint">
          点击右上角「展开」查看 AI 产出的完整 HTML 分析（含板块涨幅排行、资金流向、个股链路解读等）。
        </p>
      </DataPanel>

      <EmptyState
        v-if="!hasAnyContent"
        title="本期产物未包含可识别字段"
        description="该日 0820 任务结构不属于已知任何一种 (headline_items / structured_picks / raw_output)。可能仍在执行中，或产物格式有变更。"
      />
    </template>
    </template>

    <!-- Tab: 即时资讯（懒挂载 — 切到该 Tab 才开始 60s 轮询） -->
    <template v-else-if="activeTab === 'live'">
      <RealtimeFeed />
    </template>
  </section>
</template>

<style scoped>
.page {
  display: grid;
  gap: var(--space-4);
}

/* Tab Bar — 与 AiCenterView 视觉一致 */
.news-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--surface-active, rgba(255, 255, 255, 0.04));
  border-radius: 12px;
  overflow-x: auto;
}
.news-tab-btn {
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
.news-tab-btn:hover {
  color: var(--text, #e2e8f0);
  background: rgba(255, 255, 255, 0.04);
}
.news-tab-btn.active {
  color: var(--text, #e2e8f0);
  background: var(--surface, #1e293b);
}
.tab-icon {
  font-size: 14px;
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

/* Pick 卡片（structured_picks） */
.pick-grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
}

.pick-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  display: grid;
  gap: 8px;
}

.pick-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.pick-code {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: var(--text-muted);
}

.pick-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.pick-level-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.level-strong {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.35);
}
.level-rec {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.level-watch {
  background: rgba(6, 182, 212, 0.1);
  color: #67e8f9;
  border: 1px solid rgba(6, 182, 212, 0.25);
}
.level-hold,
.level-other {
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-secondary);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.pick-reason {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--text);
}

.pick-detail {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.pick-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
}

.chip-theme {
  background: rgba(168, 85, 247, 0.1);
  color: #d8b4fe;
  border: 1px solid rgba(168, 85, 247, 0.25);
}

.pick-entry-hint {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-left: auto;
}

/* 完整 HTML 报告（raw_output） */
.raw-output-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.panel-title-inline {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.toggle-btn {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
}
.toggle-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.raw-output-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
}

/* raw_output 内嵌 HTML 用的内联 class — Skill 产物里有自定义 .stock / .sector /
   .up / .down / .alert-good / .risk-box / .limit-up / .tag / .inflow / .outflow */
.raw-output-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}
.raw-output-body :deep(th),
.raw-output-body :deep(td) {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}
.raw-output-body :deep(th) {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.raw-output-body :deep(h2) {
  font-size: 15px;
  margin: 16px 0 8px;
  color: var(--text);
}
.raw-output-body :deep(h3) {
  font-size: 14px;
  margin: 12px 0 6px;
}
.raw-output-body :deep(p) {
  line-height: 1.7;
  font-size: 13.5px;
  margin: 6px 0;
}
.raw-output-body :deep(.up),
.raw-output-body :deep(.inflow) {
  color: var(--up, #ef4444);
  font-weight: 600;
}
.raw-output-body :deep(.down),
.raw-output-body :deep(.outflow) {
  color: var(--down, #10b981);
  font-weight: 600;
}
.raw-output-body :deep(.sector) {
  color: #67e8f9;
  font-weight: 500;
}
.raw-output-body :deep(.stock) {
  color: #fcd34d;
  font-weight: 500;
}
.raw-output-body :deep(.limit-up) {
  color: var(--up, #ef4444);
  font-weight: 700;
}
.raw-output-body :deep(.alert-good),
.raw-output-body :deep(.risk-box) {
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  margin: 8px 0;
  font-size: 13px;
}
.raw-output-body :deep(.alert-good) {
  background: rgba(16, 185, 129, 0.08);
  border-left: 3px solid var(--success, #10b981);
}
.raw-output-body :deep(.risk-box) {
  background: rgba(239, 68, 68, 0.06);
  border-left: 3px solid var(--up, #ef4444);
}
.raw-output-body :deep(.tag) {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-secondary);
  font-size: 11px;
  margin: 0 2px;
}
.raw-output-body :deep(hr) {
  border: 0;
  border-top: 1px dashed var(--border);
  margin: 16px 0;
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
