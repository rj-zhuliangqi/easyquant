<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatAmount, formatDateTime, formatPercent } from "../lib/formatters";

defineOptions({ name: "sector-monitor" });

const bootstrapQuery = useQuery({
  queryKey: pageQueryKey("sector-monitor"),
  queryFn: () => fetchJson("/api/page/sector-monitor"),
});

const payload = computed(() => bootstrapQuery.data.value?.payload ?? {});
const selectedSector = ref("");
const queryLoading = computed(() => bootstrapQuery.isLoading.value);
const queryFetching = computed(() => bootstrapQuery.isFetching.value || workspaceQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(bootstrapQuery.data.value?.updated_at));

watch(
  () => payload.value.defaults?.selected_sector,
  (value) => {
    if (value && !selectedSector.value) selectedSector.value = value;
  },
  { immediate: true },
);

const workspaceQuery = useQuery({
  queryKey: computed(() => ["sector-workspace", selectedSector.value]),
  queryFn: () =>
    fetchJson(
      `/api/sector-workspace?sector_type=industry&sector_name=${encodeURIComponent(selectedSector.value)}&metric=net_strength&granularity=minute&lookback_days=1`,
    ),
  enabled: computed(() => Boolean(selectedSector.value)),
  initialData: () => payload.value.workspace,
  placeholderData: (previous) => previous,
});

const comparisonOption = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { top: 0, textStyle: { color: "#94a3b8" } },
  grid: { left: 32, right: 24, top: 40, bottom: 32 },
  xAxis: {
    type: "category",
    data: payload.value.comparison?.labels || [],
    boundaryGap: false,
  },
  yAxis: { type: "value", scale: true },
  series: (payload.value.comparison?.series || []).map((series) => ({
    name: series.sector_name,
    type: "line",
    smooth: true,
    showSymbol: false,
    areaStyle: { opacity: 0.08 },
    data: (series.points || []).map((point) => point.value),
  })),
}));
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">板块跟踪</p>
        <h2>板块资金监控</h2>
        <p class="hero-copy">实时追踪行业与概念板块资金流，对比龙头表现与强度。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <DataPanel title="板块对比趋势" class="hero-chart-panel">
      <EChartPanel :option="comparisonOption" />
    </DataPanel>

    <section class="card-grid three-up">
      <DataPanel title="强势流入">
        <div class="list-stack">
          <button
            v-for="item in payload.overview?.leaders || []"
            :key="item.sector_name"
            class="list-button"
            :class="{ active: selectedSector === item.sector_name }"
            @click="selectedSector = item.sector_name"
          >
            <strong>{{ item.sector_name }}</strong>
            <span>{{ formatAmount(item.net_amount) }}</span>
            <small :class="{ 'text-up': (item.net_strength || 0) > 0, 'text-down': (item.net_strength || 0) < 0 }">{{ formatPercent(item.net_strength * 100) }}</small>
          </button>
          <EmptyState
            v-if="!(payload.overview?.leaders?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有强势流入板块"
          />
        </div>
      </DataPanel>

      <DataPanel title="弱势流出">
        <div class="list-stack">
          <div v-for="item in payload.overview?.laggards || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>{{ formatAmount(item.net_amount) }}</span>
            <small class="text-danger">{{ formatPercent(item.net_strength * 100) }}</small>
          </div>
          <EmptyState
            v-if="!(payload.overview?.laggards?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有弱势流出板块"
          />
        </div>
      </DataPanel>

      <DataPanel title="监控信号">
        <div class="list-stack">
          <div v-for="item in payload.signals?.items || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>持续性 {{ item.persistence }}</span>
            <small>加速度 {{ item.acceleration_1 }}</small>
          </div>
          <EmptyState
            v-if="!(payload.signals?.items?.length) && !queryLoading"
            title="暂无信号"
            description="当前没有监控信号"
          />
        </div>
      </DataPanel>
    </section>

    <section class="card-grid two-up">
      <DataPanel title="选中板块摘要">
        <div class="detail-block">
          <strong>{{ workspaceQuery.data?.resolved_sector_name || selectedSector || "等待选择" }}</strong>
          <p>{{ workspaceQuery.data?.detail?.summary_text || "当前聚合视图优先保留上次内容，后台刷新明细。" }}</p>
          <small>更新时间 {{ formatDateTime(workspaceQuery.data?.detail_updated_at || workspaceQuery.data?.detail?.captured_at) }}</small>
        </div>
      </DataPanel>

      <DataPanel title="观察池">
        <div class="list-stack">
          <div v-for="item in payload.watchlist?.items || []" :key="`${item.sector_type}-${item.sector_name}`" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <small>{{ item.sector_type }}</small>
          </div>
          <EmptyState
            v-if="!(payload.watchlist?.items?.length) && !queryLoading"
            title="暂无观察"
            description="观察池为空"
          />
        </div>
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
.hero-chart-panel {
  border-color: rgba(6, 182, 212, 0.12);
}

.hero-chart-panel :deep(.chart-panel) {
  height: 420px;
}

@media (max-width: 640px) {
  .hero-chart-panel :deep(.chart-panel) {
    height: 280px;
  }
}
</style>
