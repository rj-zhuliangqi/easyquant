<script setup>
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime, formatPercent } from "../lib/formatters";

defineOptions({ name: "limit-up-ladder" });

const pageQuery = useQuery({
  queryKey: pageQueryKey("limit-up-ladder"),
  queryFn: () => fetchJson("/api/page/limit-up-ladder"),
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(pageQuery.data.value?.updated_at));
const chartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 24, right: 16, top: 28, bottom: 24 },
  xAxis: { type: "category", data: (payload.value.temperature_history?.items || []).map((item) => item.trading_date) },
  yAxis: { type: "value", min: 0, max: 100 },
  series: [
    {
      type: "line",
      data: (payload.value.temperature_history?.items || []).map((item) => item.temperature_score),
      smooth: true,
      showSymbol: false,
      areaStyle: {
        color: {
          type: "linear",
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(245, 158, 11, 0.3)" },
            { offset: 1, color: "rgba(245, 158, 11, 0.02)" },
          ],
        },
      },
      lineStyle: { width: 2, color: "#f59e0b" },
      color: "#f59e0b",
    },
  ],
}));
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">情绪与空间</p>
        <h2>A股连板梯队</h2>
        <p class="hero-copy">保留梯队和温度视图，切页往返不再重建整个页面。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <section class="card-grid">
      <MetricCard
        label="最高连板"
        :value="payload.summary?.highest_board ?? '--'"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="涨停总数"
        :value="payload.summary?.limit_up_count ?? '--'"
        :loading="queryLoading"
      />
      <MetricCard
        label="晋级率"
        :value="formatPercent((payload.summary?.promotion_rate || 0) * 100)"
        :loading="queryLoading"
        :trend="(payload.summary?.promotion_rate || 0) > 0.5 ? 'up' : 'down'"
      />
      <MetricCard
        label="温度带"
        :value="payload.temperature?.temperature_band || '--'"
        :loading="queryLoading"
        trend="neutral"
      />
    </section>

    <DataPanel title="温度历史">
      <EChartPanel :option="chartOption" />
    </DataPanel>

    <section class="card-grid two-up">
      <DataPanel title="梯队分组">
        <div class="list-stack">
          <div v-for="group in payload.ladder?.groups || []" :key="group.board_count" class="row-card">
            <strong>{{ group.board_count }} 连板</strong>
            <span>{{ group.stock_count }} 只</span>
            <small>{{ group.leader?.name || "无龙头" }}</small>
          </div>
          <EmptyState
            v-if="!(payload.ladder?.groups?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有连板梯队数据"
          />
        </div>
      </DataPanel>

      <DataPanel title="炸板池">
        <div class="list-stack">
          <div v-for="item in payload.broken?.items || []" :key="item.code" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ item.code }}</span>
            <small>炸板 {{ item.broken_board_count }} 次</small>
          </div>
          <EmptyState
            v-if="!(payload.broken?.items?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有炸板数据"
          />
        </div>
      </DataPanel>
    </section>
  </section>
</template>
