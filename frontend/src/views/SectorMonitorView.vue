<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
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
  legend: { top: 0, textStyle: { color: "#355070" } },
  grid: { left: 24, right: 16, top: 32, bottom: 24 },
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
        <p class="hero-copy">首屏由聚合接口一次下发，切换板块时只刷新受影响面板。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <section class="card-grid three-up">
      <article class="panel">
        <div class="panel-head">
          <h3>强势流入</h3>
        </div>
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
            <small>{{ formatPercent(item.net_strength * 100) }}</small>
          </button>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <h3>弱势流出</h3>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.overview?.laggards || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>{{ formatAmount(item.net_amount) }}</span>
            <small>{{ formatPercent(item.net_strength * 100) }}</small>
          </div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <h3>监控信号</h3>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.signals?.items || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>持续性 {{ item.persistence }}</span>
            <small>加速度 {{ item.acceleration_1 }}</small>
          </div>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>板块对比趋势</h3>
      </div>
      <EChartPanel :option="comparisonOption" />
    </section>

    <section class="card-grid two-up">
      <article class="panel">
        <div class="panel-head">
          <h3>选中板块摘要</h3>
        </div>
        <div class="detail-block">
          <strong>{{ workspaceQuery.data?.resolved_sector_name || selectedSector || "等待选择" }}</strong>
          <p>{{ workspaceQuery.data?.detail?.summary_text || "当前聚合视图优先保留上次内容，后台刷新明细。" }}</p>
          <small>更新时间 {{ formatDateTime(workspaceQuery.data?.detail_updated_at || workspaceQuery.data?.detail?.captured_at) }}</small>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <h3>观察池</h3>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.watchlist?.items || []" :key="`${item.sector_type}-${item.sector_name}`" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <small>{{ item.sector_type }}</small>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>
