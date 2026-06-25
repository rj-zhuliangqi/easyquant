<script setup>
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import DataPanel from "../ui/DataPanel.vue";
import EmptyState from "../ui/EmptyState.vue";
import QueryState from "../QueryState.vue";
import { fetchRealtimeNews } from "../../lib/api";
import { formatRelativeTime, formatDateTime } from "../../lib/formatters";

defineOptions({ name: "realtime-feed" });

// 过滤器：用户切换 chip 时变更，vue-query 自动 refetch
const filters = ref({
  importance: 0, // 0=全部 / 1=重要 / 2=高度重要
  sort: "mixed", // mixed=重要置顶 / latest=最新 / important=重要性
  sources: [], // 来源 CSV
});

// 累加翻页缓冲 — v1 不用 useInfiniteQuery，简单的 ref + append
const accumulated = ref([]);
const isLoadingMore = ref(false);

const newsQuery = useQuery({
  queryKey: computed(() => ["news-realtime", filters.value]),
  queryFn: () =>
    fetchRealtimeNews({
      limit: 50,
      hours: 48,
      importance: filters.value.importance,
      sort: filters.value.sort,
      sources: filters.value.sources,
    }),
  refetchInterval: 60_000,
  staleTime: 30_000,
});

// 合并：第一页（newsQuery）+ 加载更多（accumulated），按 id 去重；按当前排序方式本地稳定排序
const mergedItems = computed(() => {
  const base = newsQuery.data.value?.items ?? [];
  const all = [...base, ...accumulated.value];
  const dedup = new Map();
  for (const item of all) {
    if (!dedup.has(item.id)) dedup.set(item.id, item);
  }
  const items = Array.from(dedup.values());
  if (filters.value.sort === "latest") {
    return items.sort((a, b) => b.published_at.localeCompare(a.published_at));
  }
  if (filters.value.sort === "important") {
    return items.sort((a, b) => {
      if (a.importance_level !== b.importance_level) return b.importance_level - a.importance_level;
      return b.published_at.localeCompare(a.published_at);
    });
  }
  return items.sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return b.published_at.localeCompare(a.published_at);
  });
});

const counts = computed(() => newsQuery.data.value?.counts || { total: 0, pinned: 0, high: 0, medium: 0 });
const lastFetchedAt = computed(() => newsQuery.data.value?.last_fetched_at || "");
const lastFetchedText = computed(() =>
  lastFetchedAt.value ? `${formatDateTime(lastFetchedAt.value)} · ${formatRelativeTime(lastFetchedAt.value)}` : "--",
);
const queryLoading = computed(() => newsQuery.isLoading.value);
const queryFetching = computed(() => newsQuery.isFetching.value);
const queryUpdatedAt = computed(() =>
  newsQuery.data.value?.fetched_at ? formatDateTime(newsQuery.data.value.fetched_at) : "",
);

// 已知来源 — 与后端 NewsService 注册表对齐
const SOURCE_OPTIONS = [
  { key: "eastmoney_724", label: "东财 7×24" },
  { key: "ths_live", label: "同花顺直播" },
  { key: "sina_roll", label: "新浪滚动" },
];

const SORT_OPTIONS = [
  { key: "mixed", label: "重要置顶" },
  { key: "latest", label: "最新优先" },
  { key: "important", label: "重要性" },
];

function setSort(sort) {
  filters.value = { ...filters.value, sort };
  accumulated.value = [];
}

function setImportance(level) {
  filters.value = { ...filters.value, importance: level };
  accumulated.value = [];
}

function toggleSource(key) {
  const next = new Set(filters.value.sources);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  filters.value = { ...filters.value, sources: Array.from(next) };
  accumulated.value = [];
}

function refreshNow() {
  accumulated.value = [];
  newsQuery.refetch();
}

async function loadMore() {
  if (isLoadingMore.value) return;
  const items = mergedItems.value;
  const lastId = items.length ? items[items.length - 1].id : null;
  if (!lastId) return;
  isLoadingMore.value = true;
  try {
    const result = await fetchRealtimeNews({
      limit: 50,
      hours: 168, // 翻页时放宽到 7 天，避免一直翻不出新条
      importance: filters.value.importance,
      sort: filters.value.sort,
      sources: filters.value.sources,
      sinceId: lastId,
    });
    accumulated.value = [...accumulated.value, ...(result.items || [])];
  } finally {
    isLoadingMore.value = false;
  }
}

function importanceBadge(level) {
  if (level === 2) return { label: "重要", cls: "badge-high" };
  if (level === 1) return { label: "关注", cls: "badge-medium" };
  return null;
}

function sourceLabel(source) {
  return SOURCE_OPTIONS.find((s) => s.key === source)?.label || source;
}

function tagsTooltip(item) {
  const parts = [];
  if (item.matched_action?.length) parts.push(`行为：${item.matched_action.join(" / ")}`);
  if (item.matched_industry?.length) parts.push(`行业：${item.matched_industry.join(" / ")}`);
  return parts.join("\n");
}
</script>

<template>
  <DataPanel>
    <template #header>
      <div class="feed-header">
        <div class="feed-title-block">
          <h3 class="feed-title">即时资讯流</h3>
          <p class="feed-subtitle">
            东财 7×24 / 同花顺直播 / 新浪滚动 · 每 5 分钟自动入库 · 最近拉取 {{ lastFetchedText }}
          </p>
        </div>
        <div class="feed-status">
          <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
          <button class="refresh-btn" @click="refreshNow" :disabled="queryFetching">
            ⟳ 立即刷新
          </button>
        </div>
      </div>

      <!-- 筛选 chip 行 -->
      <div class="feed-filters">
        <span class="filter-group-label">排序</span>
        <button
          v-for="opt in SORT_OPTIONS"
          :key="opt.key"
          class="chip-btn"
          :class="{ active: filters.sort === opt.key }"
          @click="setSort(opt.key)"
        >
          {{ opt.label }}
        </button>

        <span class="filter-divider"></span>

        <span class="filter-group-label">重要性</span>
        <button
          class="chip-btn"
          :class="{ active: filters.importance === 0 }"
          @click="setImportance(0)"
        >
          全部 · {{ counts.total }}
        </button>
        <button
          class="chip-btn"
          :class="{ active: filters.importance === 1 }"
          @click="setImportance(1)"
        >
          关注及以上 · {{ counts.medium + counts.high }}
        </button>
        <button
          class="chip-btn"
          :class="{ active: filters.importance === 2 }"
          @click="setImportance(2)"
        >
          重要 · {{ counts.high }}
        </button>

        <span class="filter-divider"></span>

        <span class="filter-group-label">来源</span>
        <button
          v-for="src in SOURCE_OPTIONS"
          :key="src.key"
          class="chip-btn"
          :class="{ active: filters.sources.includes(src.key) }"
          @click="toggleSource(src.key)"
        >
          {{ src.label }}
        </button>
      </div>
    </template>

    <EmptyState
      v-if="!mergedItems.length && !queryLoading"
      title="暂无符合条件的实时资讯"
      description="试着切换重要性或来源筛选；或等待下一轮 5 分钟的自动入库。"
    />

    <ol v-else class="news-list">
      <li
        v-for="item in mergedItems"
        :key="item.id"
        class="news-card"
        :class="[`level-${item.importance_level}`, { pinned: item.is_pinned }]"
      >
        <span class="level-bar"></span>
        <div class="news-body">
          <header class="news-head">
            <span v-if="item.is_pinned" class="pin-icon" title="重要双命中">📌</span>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noopener" class="news-title">
              {{ item.title }}
            </a>
            <span v-else class="news-title">{{ item.title }}</span>
            <span
              v-if="importanceBadge(item.importance_level)"
              :class="['importance-badge', importanceBadge(item.importance_level).cls]"
            >
              {{ importanceBadge(item.importance_level).label }}
            </span>
          </header>
          <p v-if="item.summary" class="news-summary">{{ item.summary }}</p>
          <footer class="news-meta">
            <span class="source-chip">{{ sourceLabel(item.source) }}</span>
            <span class="rel-time">发布时间 {{ formatRelativeTime(item.published_at) }}</span>
            <span v-if="item.fetched_at" class="fetch-time" :title="formatDateTime(item.fetched_at)">
              拉取 {{ formatRelativeTime(item.fetched_at) }}
            </span>
            <span
              v-for="tag in item.matched_action || []"
              :key="`act-${item.id}-${tag}`"
              class="match-chip match-action"
              :title="tagsTooltip(item)"
            >
              {{ tag }}
            </span>
            <span
              v-for="tag in item.matched_industry || []"
              :key="`ind-${item.id}-${tag}`"
              class="match-chip match-industry"
              :title="tagsTooltip(item)"
            >
              {{ tag }}
            </span>
          </footer>
        </div>
      </li>
    </ol>

    <div v-if="mergedItems.length" class="load-more-row">
      <button class="load-more-btn" @click="loadMore" :disabled="isLoadingMore">
        {{ isLoadingMore ? "加载中…" : "加载更多" }}
      </button>
    </div>
  </DataPanel>
</template>

<style scoped>
.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.feed-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.feed-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.feed-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.refresh-btn {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(6, 182, 212, 0.3);
  background: rgba(6, 182, 212, 0.08);
  color: var(--accent);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}
.refresh-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.feed-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border);
}

.filter-group-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-right: 2px;
}

.filter-divider {
  width: 1px;
  height: 16px;
  background: var(--border);
  margin: 0 6px;
}

.chip-btn {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.chip-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}
.chip-btn.active {
  background: rgba(6, 182, 212, 0.12);
  border-color: rgba(6, 182, 212, 0.4);
  color: var(--accent);
}

/* 资讯卡片列表 */
.news-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.news-card {
  display: flex;
  align-items: stretch;
  gap: 10px;
  padding: 10px 12px 10px 0;
  border-radius: var(--radius-md);
  background: var(--surface, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  overflow: hidden;
  transition: border-color 0.15s ease;
}
.news-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
}
.news-card.level-1 {
  border-color: rgba(245, 158, 11, 0.25);
}
.news-card.level-2 {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.03);
}

.level-bar {
  width: 4px;
  align-self: stretch;
  background: transparent;
  flex-shrink: 0;
}
.level-1 .level-bar {
  background: #f59e0b;
}
.level-2 .level-bar {
  background: var(--up, #ef4444);
}

.news-body {
  flex: 1;
  display: grid;
  gap: 4px;
  min-width: 0;
}

.news-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}

.pin-icon {
  font-size: 13px;
}

.news-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  text-decoration: none;
  line-height: 1.4;
}
a.news-title:hover {
  color: var(--accent);
  text-decoration: underline;
}

.importance-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.badge-high {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.badge-medium {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.news-summary {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-muted);
}

.source-chip {
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-secondary);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.rel-time,
.fetch-time {
  color: var(--text-muted);
}

.fetch-time {
  padding-left: 6px;
  border-left: 1px solid var(--border);
}

.match-chip {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10.5px;
  cursor: help;
}
.match-action {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.match-industry {
  background: rgba(6, 182, 212, 0.1);
  color: #67e8f9;
  border: 1px solid rgba(6, 182, 212, 0.25);
}

.load-more-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-3);
}
.load-more-btn {
  padding: 6px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12.5px;
  cursor: pointer;
}
.load-more-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}
.load-more-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}
</style>
