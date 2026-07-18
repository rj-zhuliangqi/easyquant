<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { useResponsive } from "../composables/useResponsive";

defineOptions({ name: "opportunity-pool" });

const { isMobileLayout } = useResponsive();

const mode = ref("strong-sector");
const selectedIndex = ref(0);
const items = ref([]);
const queryLoadingState = ref(true);
const queryFetchingState = ref(false);
const listError = ref(null);
let requestSeq = 0;
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

async function refreshOpportunities() {
  const seq = ++requestSeq;
  queryFetchingState.value = true;
  listError.value = null;
  try {
    if (mode.value === "ai-t-plus-1") {
      const payload = await fetchJson("/api/ai/picks?run_type=production");
      if (seq !== requestSeq) return;  // P2-5 竞态保护
      items.value = (payload.items || []).map(normalizeAiPick);
    } else {
      const payload = await fetchJson(`/api/opportunities?mode=${encodeURIComponent(mode.value)}&limit=20`);
      if (seq !== requestSeq) return;
      items.value = payload.items || [];
    }
  } catch (error) {
    if (seq === requestSeq) listError.value = error.message || String(error);
  } finally {
    if (seq === requestSeq) {
      queryLoadingState.value = false;
      queryFetchingState.value = false;
    }
  }
}

watch(
  () => bootstrapQuery.data.value?.payload,
  (payload) => {
    applyBootstrap(payload);
  },
  { immediate: true },
);

watch(mode, async () => {
  selectedIndex.value = 0;
  await refreshOpportunities();
});

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
</style>
