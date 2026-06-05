<script setup>
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
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
      areaStyle: {},
      lineStyle: { width: 3 },
      showSymbol: false,
      color: "#0f8b8d",
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
      <article class="metric-card">
        <span>监控状态</span>
        <strong>{{ status.market_open ? "盘中运行" : "非交易时段" }}</strong>
        <small>{{ formatDateTime(status.updated_at) }}</small>
      </article>
      <article class="metric-card">
        <span>最强流入板块</span>
        <strong>{{ systemSummary.sector_monitor?.strongest_inflow_sector || "--" }}</strong>
        <small>{{ formatAmount(systemSummary.sector_monitor?.strongest_inflow_amount) }}</small>
      </article>
      <article class="metric-card">
        <span>最高连板</span>
        <strong>{{ systemSummary.limit_up_ladder?.highest_board ?? "--" }}</strong>
        <small>晋级率 {{ formatPercent((systemSummary.limit_up_ladder?.promotion_rate || 0) * 100) }}</small>
      </article>
      <article class="metric-card">
        <span>上涨 / 下跌</span>
        <strong>{{ marketOverview.breadth?.up_count ?? 0 }} / {{ marketOverview.breadth?.down_count ?? 0 }}</strong>
        <small>活跃度 {{ formatPercent(marketOverview.breadth?.market_activity) }}</small>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>指数趋势</h3>
          <p>{{ selectedIndex?.name || "等待数据" }}</p>
        </div>
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
      </div>
      <EChartPanel :option="chartOption" />
    </section>

    <section class="card-grid two-up">
      <article class="panel">
        <div class="panel-head">
          <h3>指数快照</h3>
        </div>
        <div class="list-stack">
          <div v-for="item in marketOverview.indices || []" :key="item.symbol" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ formatNumber(item.price) }}</span>
            <small>{{ formatPercent(item.change_percent) }}</small>
          </div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <h3>行动优先级</h3>
        </div>
        <div class="detail-block">
          <strong>{{ systemSummary.action_priority?.title || "--" }}</strong>
          <p>{{ systemSummary.action_priority?.reason || "等待数据" }}</p>
          <small>告警 {{ systemSummary.alert_summary?.count ?? 0 }} 条，机会 {{ systemSummary.opportunity_summary?.count ?? 0 }} 个</small>
        </div>
      </article>
    </section>
  </section>
</template>
