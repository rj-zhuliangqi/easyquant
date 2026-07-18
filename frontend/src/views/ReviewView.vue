<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import StatusBadge from "../components/ui/StatusBadge.vue";
import { fetchJson } from "../lib/api";
import { formatDateTime, todayIso } from "../lib/formatters";

defineOptions({ name: "review" });

const route = useRoute();
const router = useRouter();

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

/* ── Section definitions with render type ── */
const sections = computed(() => [
  { key: "market_summary", title: "市场概况", empty: "暂无市场概况", render: "market_summary" },
  { key: "market_breadth", title: "市场宽度", empty: "暂无市场宽度", render: "market_breadth" },
  { key: "top_themes", title: "主线板块", empty: "暂无主线板块", render: "top_themes" },
  { key: "failed_patterns", title: "失败模式", empty: "暂无失败模式", render: "failed_patterns" },
  { key: "recommended_picks_review", title: "推荐复盘", empty: "暂无推荐复盘", render: "recommended_picks_review" },
  { key: "position_review", title: "持仓复盘", empty: "暂无持仓复盘", render: "position_review" },
  { key: "lesson_items", title: "经验条目", empty: "暂无经验条目", render: "lesson_items" },
  { key: "next_day_focus", title: "次日关注", empty: "暂无次日关注", render: "next_day_focus" },
]);

function hasValue(value) {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return String(value).trim().length > 0;
}

const hasAnyReview = computed(() => sections.value.some((section) => hasValue(review.value?.[section.key])));

/* ── Render helpers ── */

function isString(v) {
  return typeof v === "string";
}

function isObject(v) {
  return v && typeof v === "object" && !Array.isArray(v);
}

function safeString(v) {
  if (v == null || v === "") return "--";
  if (isString(v)) return v;
  if (isObject(v)) return JSON.stringify(v, null, 2);
  return String(v);
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
          <!-- ═══════════════════════════════════════════ -->
          <!-- market_summary — key/value pairs -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'market_summary'">
            <div v-if="isString(review.market_summary)" class="review-text">
              {{ review.market_summary }}
            </div>
            <div v-else-if="isObject(review.market_summary)" class="kv-grid">
              <div v-for="(val, key) in review.market_summary" :key="key" class="kv-row">
                <span class="kv-key">{{ key }}</span>
                <span class="kv-value">{{ safeString(val) }}</span>
              </div>
            </div>
            <div v-else class="review-text">{{ safeString(review.market_summary) }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- market_breadth — key/value pairs -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'market_breadth'">
            <div v-if="isObject(review.market_breadth)" class="kv-grid">
              <div v-for="(val, key) in review.market_breadth" :key="key" class="kv-row">
                <span class="kv-key">{{ key }}</span>
                <span class="kv-value">{{ safeString(val) }}</span>
              </div>
            </div>
            <div v-else class="review-text">{{ safeString(review.market_breadth) }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- top_themes — array of objects/strings -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'top_themes'">
            <div v-if="Array.isArray(review.top_themes) && review.top_themes.length" class="chip-list">
              <article v-for="(theme, idx) in review.top_themes" :key="idx" class="theme-card">
                <div v-if="isObject(theme)" class="theme-body">
                  <span class="theme-name">{{ theme.theme || theme.name || theme.sector || '主题' }}</span>
                  <p v-if="theme.reason || theme.detail" class="theme-reason">{{ theme.reason || theme.detail }}</p>
                  <div v-if="theme.stocks?.length" class="theme-stocks">
                    <span v-for="(s, sIdx) in theme.stocks" :key="sIdx" class="chip chip-stock">{{ s }}</span>
                  </div>
                </div>
                <div v-else class="theme-body">
                  <span class="theme-name">{{ theme }}</span>
                </div>
              </article>
            </div>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- failed_patterns — string array -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'failed_patterns'">
            <ul v-if="Array.isArray(review.failed_patterns) && review.failed_patterns.length" class="bullet-list">
              <li v-for="(item, idx) in review.failed_patterns" :key="idx">{{ item }}</li>
            </ul>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- recommended_picks_review — array of objects -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'recommended_picks_review'">
            <div v-if="Array.isArray(review.recommended_picks_review) && review.recommended_picks_review.length" class="chip-list">
              <article v-for="(pick, idx) in review.recommended_picks_review" :key="idx" class="pick-card">
                <div v-if="isObject(pick)" class="pick-body">
                  <div class="pick-header">
                    <span v-if="pick.stock_code" class="pick-code">{{ pick.stock_code }}</span>
                    <span v-if="pick.stock_name" class="pick-name">{{ pick.stock_name }}</span>
                  </div>
                  <p v-if="pick.review || pick.reason || pick.summary" class="pick-reason">{{ pick.review || pick.reason || pick.summary }}</p>
                  <div v-if="pick.effect || pick.close_change_pct != null" class="pick-meta">
                    <span v-if="pick.effect" class="pick-effect">{{ pick.effect }}</span>
                    <span v-if="pick.close_change_pct != null" :class="['pick-pct', pick.close_change_pct > 0 ? 'up' : 'down']">
                      {{ pick.close_change_pct > 0 ? '+' : '' }}{{ pick.close_change_pct.toFixed(2) }}%
                    </span>
                  </div>
                </div>
                <div v-else class="review-text">{{ safeString(pick) }}</div>
              </article>
            </div>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- position_review — array of objects -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'position_review'">
            <div v-if="Array.isArray(review.position_review) && review.position_review.length" class="chip-list">
              <article v-for="(pos, idx) in review.position_review" :key="idx" class="pick-card">
                <div v-if="isObject(pos)" class="pick-body">
                  <div class="pick-header">
                    <span v-if="pos.stock_code" class="pick-code">{{ pos.stock_code }}</span>
                    <span v-if="pos.stock_name" class="pick-name">{{ pos.stock_name }}</span>
                    <span v-if="pos.action" :class="['action-badge', pos.action]">{{ pos.action }}</span>
                  </div>
                  <p v-if="pos.reason || pos.review" class="pick-reason">{{ pos.reason || pos.review }}</p>
                </div>
                <div v-else class="review-text">{{ safeString(pos) }}</div>
              </article>
            </div>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- lesson_items — array of objects -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'lesson_items'">
            <div v-if="Array.isArray(review.lesson_items) && review.lesson_items.length" class="chip-list">
              <article v-for="(item, idx) in review.lesson_items" :key="idx" class="lesson-card">
                <div v-if="isObject(item)" class="lesson-body">
                  <div class="lesson-header">
                    <span v-if="item.tag" class="lesson-tag">{{ item.tag }}</span>
                    <strong v-if="item.title" class="lesson-title">{{ item.title }}</strong>
                  </div>
                  <p v-if="item.detail || item.content" class="lesson-detail">{{ item.detail || item.content }}</p>
                </div>
                <div v-else class="review-text">{{ safeString(item) }}</div>
              </article>
            </div>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>

          <!-- ═══════════════════════════════════════════ -->
          <!-- next_day_focus — string array -->
          <!-- ═══════════════════════════════════════════ -->
          <template v-if="section.render === 'next_day_focus'">
            <ul v-if="Array.isArray(review.next_day_focus) && review.next_day_focus.length" class="bullet-list">
              <li v-for="(item, idx) in review.next_day_focus" :key="idx">{{ item }}</li>
            </ul>
            <div v-else class="muted-text">{{ section.empty }}</div>
          </template>
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
          <StatusBadge :status="run.status === 'success' ? 'success' : run.status === 'failed' ? 'danger' : 'neutral'">
            {{ run.status }}
          </StatusBadge>
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

/* ── Key/Value Grid ── */
.kv-grid {
  display: grid;
  gap: 8px;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.kv-key {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.kv-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  text-align: right;
  word-break: break-word;
}

/* ── Chip List & Cards ── */
.chip-list {
  display: grid;
  gap: 10px;
}

/* ── Theme Card ── */
.theme-card {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border);
}

.theme-body {
  display: grid;
  gap: 6px;
}

.theme-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.theme-reason {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.theme-stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

/* ── Pick Card ── */
.pick-card {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border);
}

.pick-body {
  display: grid;
  gap: 6px;
}

.pick-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pick-code {
  font-family: monospace;
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 600;
}

.pick-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text);
}

.pick-reason {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.pick-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.pick-effect {
  font-size: 12px;
  color: var(--text-muted);
}

.pick-pct {
  font-size: 13px;
  font-weight: 700;
}

.pick-pct.up {
  color: #f87171;
}

.pick-pct.down {
  color: var(--success, #10b981);
}

/* ── Action Badge ── */
.action-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  text-transform: uppercase;
}

.action-badge.hold {
  color: #60a5fa;
  background: rgba(96,165,250,0.1);
}

.action-badge.trim {
  color: #f59e0b;
  background: rgba(251,191,36,0.1);
}

.action-badge.buy {
  color: #f87171;
  background: rgba(248,113,113,0.1);
}

.action-badge.sell {
  color: var(--success, #10b981);
  background: var(--success-soft, rgba(16,185,129,0.1));
}

.action-badge.watch {
  color: #94a3b8;
  background: rgba(148,163,184,0.1);
}

/* ── Lesson Card ── */
.lesson-card {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.025);
  border: 1px solid var(--border);
}

.lesson-body {
  display: grid;
  gap: 6px;
}

.lesson-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.lesson-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  background: rgba(6,182,212,0.1);
  color: #06b6d4;
  text-transform: uppercase;
}

.lesson-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.lesson-detail {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ── Chips ── */
.chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}

.chip-stock {
  background: rgba(251,191,36,0.1);
  color: #fbbf24;
}

/* ── Bullet List ── */
.bullet-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.bullet-list li {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text);
}

/* ── Review Text ── */
.review-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.7;
  color: var(--text-secondary);
  font-size: 13px;
}

.muted-text {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

/* ── Run List ── */
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

.mt-lg { margin-top: var(--space-4); }

@media (max-width: 640px) {
  .review-grid { grid-template-columns: 1fr; }
  .run-row { flex-wrap: wrap; }
  .kv-row { flex-direction: column; align-items: flex-start; gap: 2px; }
}
</style>
