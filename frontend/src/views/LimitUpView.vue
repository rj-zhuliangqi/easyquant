<script setup>
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
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
      areaStyle: {},
      color: "#ff7f11",
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
      <article class="metric-card">
        <span>最高连板</span>
        <strong>{{ payload.summary?.highest_board ?? "--" }}</strong>
      </article>
      <article class="metric-card">
        <span>涨停总数</span>
        <strong>{{ payload.summary?.limit_up_count ?? "--" }}</strong>
      </article>
      <article class="metric-card">
        <span>晋级率</span>
        <strong>{{ formatPercent((payload.summary?.promotion_rate || 0) * 100) }}</strong>
      </article>
      <article class="metric-card">
        <span>温度带</span>
        <strong>{{ payload.temperature?.temperature_band || "--" }}</strong>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>温度历史</h3>
      </div>
      <EChartPanel :option="chartOption" />
    </section>

    <section class="card-grid two-up">
      <article class="panel">
        <div class="panel-head">
          <h3>梯队分组</h3>
        </div>
        <div class="list-stack">
          <div v-for="group in payload.ladder?.groups || []" :key="group.board_count" class="row-card">
            <strong>{{ group.board_count }} 连板</strong>
            <span>{{ group.stock_count }} 只</span>
            <small>{{ group.leader?.name || "无龙头" }}</small>
          </div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <h3>炸板池</h3>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.broken?.items || []" :key="item.code" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ item.code }}</span>
            <small>炸板 {{ item.broken_board_count }} 次</small>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>
