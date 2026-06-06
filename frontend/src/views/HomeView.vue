<script setup>
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatAmount, formatDateTime, formatNumber, formatPercent } from "../lib/formatters";

defineOptions({ name: "home" });

const selectedSymbol = ref("sh000001");

const pageQuery = useQuery({
  queryKey: pageQueryKey("home"),
  queryFn: () => fetchJson("/api/page/home"),
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const marketOverview = computed(() => payload.value.market_overview ?? {});
const systemSummary = computed(() => payload.value.system_summary ?? {});
const status = computed(() => payload.value.status ?? {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(pageQuery.data.value?.updated_at));
const selectedIndex = computed(
  () => (marketOverview.value.indices || []).find((item) => item.symbol === selectedSymbol.value) || marketOverview.value.indices?.[0] || null,
);

const chartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 24, right: 16, top: 28, bottom: 24 },
  xAxis: {
    type: "category",
    data: (selectedIndex.value?.points || []).map((item) => item.label),
    boundaryGap: false,
  },
  yAxis: { type: "value", scale: true },
  series: [
    {
      type: "line",
      smooth: true,
      data: (selectedIndex.value?.points || []).map((item) => item.value),
      areaStyle: {
        color: {
          type: "linear",
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(6, 182, 212, 0.3)" },
            { offset: 1, color: "rgba(6, 182, 212, 0.02)" },
          ],
        },
      },
      lineStyle: { width: 2, color: "#06b6d4" },
      showSymbol: false,
      color: "#06b6d4",
    },
  ],
}));
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">市场总览</p>
        <h2>首页脉搏</h2>
        <p class="hero-copy">保留已有内容，后台刷新，不再每次切页从空白开始。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <section class="card-grid">
      <MetricCard
        label="监控状态"
        :value="status.market_open ? '盘中运行' : '非交易时段'"
        :sub-value="formatDateTime(status.updated_at)"
        :loading="queryLoading"
        trend="neutral"
      />
      <MetricCard
        label="最强流入板块"
        :value="systemSummary.sector_monitor?.strongest_inflow_sector || '--'"
        :sub-value="formatAmount(systemSummary.sector_monitor?.strongest_inflow_amount)"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="最高连板"
        :value="systemSummary.limit_up_ladder?.highest_board ?? '--'"
        :sub-value="`晋级率 ${formatPercent((systemSummary.limit_up_ladder?.promotion_rate || 0) * 100)}`"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="上涨 / 下跌"
        :value="`${marketOverview.breadth?.up_count ?? 0} / ${marketOverview.breadth?.down_count ?? 0}`"
        :sub-value="`活跃度 ${formatPercent(marketOverview.breadth?.market_activity)}`"
        :loading="queryLoading"
        :trend="(marketOverview.breadth?.up_count || 0) > (marketOverview.breadth?.down_count || 0) ? 'up' : 'down'"
      />
    </section>

    <DataPanel title="指数趋势" :subtitle="selectedIndex?.name || '等待数据'">
      <template #actions>
        <div class="switch-row">
          <button
            v-for="item in marketOverview.indices || []"
            :key="item.symbol"
            class="ghost-button"
            :class="{ active: selectedSymbol === item.symbol }"
            @click="selectedSymbol = item.symbol"
          >
            {{ item.name }}
          </button>
        </div>
      </template>
      <EChartPanel :option="chartOption" />
    </DataPanel>

    <section class="card-grid two-up">
      <DataPanel title="指数快照">
        <div class="list-stack">
          <div v-for="item in marketOverview.indices || []" :key="item.symbol" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ formatNumber(item.price) }}</span>
            <small :class="{ 'text-success': (item.change_percent || 0) > 0, 'text-danger': (item.change_percent || 0) < 0 }">
              {{ formatPercent(item.change_percent) }}
            </small>
          </div>
        </div>
      </DataPanel>

      <DataPanel title="行动优先级">
        <div class="detail-block">
          <strong>{{ systemSummary.action_priority?.title || "--" }}</strong>
          <p>{{ systemSummary.action_priority?.reason || "等待数据" }}</p>
          <small>告警 {{ systemSummary.alert_summary?.count ?? 0 }} 条，机会 {{ systemSummary.opportunity_summary?.count ?? 0 }} 个</small>
        </div>
      </DataPanel>
    </section>
  </section>
</template>
