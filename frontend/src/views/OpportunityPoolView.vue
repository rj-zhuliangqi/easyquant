<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { useResponsive } from "../composables/useResponsive";
import { useFilteredList } from "../composables/useFilteredList";

defineOptions({ name: "opportunity-pool" });

const { isMobileLayout } = useResponsive();

const mode = ref("strong-sector");
const selectedIndex = ref(0);
const items = ref([]);
const watchInFlight = ref(false);
const watchActionMessage = ref("");

// C5: 筛选驱动的列表（requestSeq 竞态 + loading/fetching/error + watch mode）
const { loading: queryLoadingState, fetching: queryFetchingState, error: listError, refresh: refreshOpportunities } = useFilteredList({
  filters: mode,
  beforeRefresh: () => { selectedIndex.value = 0; },
  fetcher: async (isCurrent) => {
    if (mode.value === "ai-t-plus-1") {
      const payload = await fetchJson("/api/ai/picks?run_type=production");
      if (!isCurrent()) return;  // P2-5 竞态保护
      items.value = (payload.items || []).map(normalizeAiPick);
    } else {
      const payload = await fetchJson(`/api/opportunities?mode=${encodeURIComponent(mode.value)}&limit=20`);
      if (!isCurrent()) return;
      items.value = payload.items || [];
    }
  },
});

async function watchFromOpportunity(item) {
  if (!item?.stock_code) return;
  watchInFlight.value = true;
  watchActionMessage.value = "加入中…";
  try {
    const current = await fetchJson("/api/workspace");
    const stocks = current.watched_stocks || [];
    if (stocks.some((s) => s.stock_code === item.stock_code)) {
      watchActionMessage.value = `已在观察列表：${item.stock_code}`;
      return;
    }
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: current.watched_sectors || [],
        watched_stocks: [...stocks, { stock_code: item.stock_code, stock_name: item.stock_name || item.stock_code }],
      }),
    });
    watchActionMessage.value = `✅ 已加入观察：${item.stock_code}`;
  } catch (error) {
    watchActionMessage.value = `加入失败：${error.message || error}`;
  } finally {
    watchInFlight.value = false;
  }
}
const detailPanel = ref(null);

const bootstrapQuery = useQuery({
  queryKey: pageQueryKey("opportunity-pool"),
  queryFn: () => fetchJson("/api/page/opportunity-pool"),
});

function normalizeAiPick(item) {
  const source = Array.isArray(item.sources) && item.sources.length ? item.sources[0] : {};
  return {
    stock_code: item.stock_code,
    stock_name: item.stock_name,
    sector_name: item.sector_name,
    theme: Array.isArray(item.tags) ? item.tags.join(" / ") : "--",
    entry_reason: source.reason_summary || "AI generated candidate",
    risk_flag: source.pick_level || "Pending review",
    mode: "AI T+1",
  };
}

function applyBootstrap(payload) {
  if (!payload) return;
  items.value = payload.opportunities?.items || [];
  queryLoadingState.value = false;
}

watch(
  () => bootstrapQuery.data.value?.payload,
  (payload) => {
    applyBootstrap(payload);
  },
  { immediate: true },
);

// C5: mode 的 watch + refresh 已由 useFilteredList 接管

// On mobile, scroll to detail panel when selection changes
watch(selectedIndex, async () => {
  if (isMobileLayout.value && detailPanel.value) {
    await nextTick();
    detailPanel.value.$el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

const activeItem = computed(() => items.value[selectedIndex.value] || null);
const queryLoading = computed(() => bootstrapQuery.isLoading.value && queryLoadingState.value);
const queryFetching = computed(() => bootstrapQuery.isFetching.value || queryFetchingState.value);
const queryError = computed(() => bootstrapQuery.isError.value || !!listError.value);
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">候选池</p>
        <h2>机会池</h2>
        <p class="hero-copy">按板块强度、龙头承接与 AI T+1 候选筛选当日机会。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :is-error="queryError" @retry="refreshOpportunities" />
    </header>

    <section class="filter-grid one-up">
      <label>
        <span>模式</span>
        <select v-model="mode">
          <option value="strong-sector">强势板块</option>
          <option value="high-conviction-limitup">高辨识度连板</option>
          <option value="sector-limitup-resonance">板块连板共振</option>
          <option value="low-first-board-expansion">首板扩散</option>
          <option value="rebound-watch">回封观察</option>
          <option value="ai-t-plus-1">AI T+1</option>
        </select>
      </label>
    </section>

    <section class="card-grid two-up">
      <DataPanel title="候选列表">
        <div class="list-stack">
          <button
            v-for="(item, index) in items"
            :key="`${item.stock_code || item.sector_name}-${index}`"
            class="list-button"
            :class="{ active: selectedIndex === index }"
            @click="selectedIndex = index"
          >
            <strong>{{ item.stock_name || item.sector_name || "--" }}</strong>
            <span>{{ item.theme || item.mode || "--" }}</span>
            <small>{{ item.entry_reason || item.reason_summary || "--" }}</small>
          </button>
          <div v-if="listError" class="list-error">
            加载失败：{{ listError }}
            <button class="inline-retry" type="button" @click="refreshOpportunities">重试</button>
          </div>
          <EmptyState
            v-else-if="!items.length && !queryLoading"
            title="暂无候选"
            description="当前模式下没有匹配的机会"
          />
        </div>
      </DataPanel>

      <DataPanel ref="detailPanel" title="详情" class="detail-panel">
        <div v-if="activeItem" class="detail-block">
          <strong>{{ activeItem.stock_name || activeItem.sector_name || "--" }}</strong>
          <p>{{ activeItem.entry_reason || activeItem.reason_summary || "--" }}</p>
          <small>{{ activeItem.risk_flag || activeItem.signal_context || "等待风控标签" }}</small>
          <!-- P4-3: 详情补可执行动作 -->
          <div class="detail-actions">
            <button
              v-if="activeItem.stock_code"
              class="action-btn"
              type="button"
              :disabled="watchInFlight"
              @click="watchFromOpportunity(activeItem)"
            >{{ watchInFlight ? "加入中…" : "＋ 加入观察" }}</button>
            <RouterLink
              v-else-if="activeItem.sector_name"
              class="action-link"
              :to="{ path: '/sector-monitor', query: { sector: activeItem.sector_name } }"
            >查看板块</RouterLink>
          </div>
          <small v-if="watchActionMessage" class="watch-action-msg">{{ watchActionMessage }}</small>
        </div>
        <EmptyState
          v-else
          title="暂无候选"
          description="选择列表中的项目查看详情"
        />
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
@media (max-width: 640px) {
  .detail-panel {
    border-top: 2px solid var(--border-hover);
  }
}
.detail-actions { display: flex; gap: 12px; margin-top: 8px; align-items: center; flex-wrap: wrap; }
.action-link { font-size: 12px; color: var(--accent, #06b6d4); text-decoration: none; padding: 4px 10px; border: 1px solid rgba(6,182,212,0.3); border-radius: 6px; }
.action-link:hover { background: rgba(6,182,212,0.1); }
.action-btn { font-size: 12px; padding: 4px 10px; border-radius: 6px; border: none; background: var(--accent, #06b6d4); color: #fff; cursor: pointer; font-weight: 600; }
.action-btn:hover:not(:disabled) { opacity: 0.9; }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.watch-action-msg { display: block; margin-top: 6px; color: var(--text-muted, #94a3b8); }
.list-error { padding: 10px; color: var(--danger, #ef4444); font-size: 13px; }
.inline-retry { margin-left: 8px; padding: 2px 10px; border-radius: 4px; border: 1px solid var(--border, rgba(255,255,255,0.1)); background: transparent; color: var(--text, #e2e8f0); cursor: pointer; }
</style>
