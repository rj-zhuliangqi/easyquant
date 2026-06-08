<script setup>
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  option: {
    type: Object,
    required: true,
  },
  autoresize: {
    type: Boolean,
    default: true,
  },
  theme: {
    type: String,
    default: "dark",
  },
  title: {
    type: String,
    default: "",
  },
  description: {
    type: String,
    default: "",
  },
});

const host = ref(null);
let chart;
let resizeObserver;

// Dark theme colors for ECharts
const darkTheme = {
  backgroundColor: "transparent",
  textStyle: { color: "#94a3b8" },
  title: { textStyle: { color: "#f1f5f9" } },
  legend: {
    textStyle: { color: "#94a3b8" },
    pageTextStyle: { color: "#94a3b8" },
  },
  tooltip: {
    backgroundColor: "rgba(21, 29, 46, 0.95)",
    borderColor: "rgba(148, 163, 184, 0.15)",
    textStyle: { color: "#f1f5f9" },
  },
  axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.15)" } },
  splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.08)" } },
  axisLabel: { color: "#64748b" },
};

const chartColors = ["#06b6d4", "#8b5cf6", "#f59e0b", "#10b981", "#ec4899", "#6366f1"];

function applyOption() {
  if (!chart || !props.option) return;

  const themedOption = {
    ...props.option,
    backgroundColor: darkTheme.backgroundColor,
    color: chartColors,
    textStyle: { ...darkTheme.textStyle, ...props.option.textStyle },
    title: props.option.title
      ? { ...darkTheme.title, ...props.option.title, textStyle: { ...darkTheme.title.textStyle, ...props.option.title.textStyle } }
      : undefined,
    legend: props.option.legend
      ? { ...darkTheme.legend, ...props.option.legend, textStyle: { ...darkTheme.legend.textStyle, ...props.option.legend.textStyle } }
      : undefined,
    tooltip: props.option.tooltip
      ? { ...darkTheme.tooltip, ...props.option.tooltip, textStyle: { ...darkTheme.tooltip.textStyle, ...props.option.tooltip.textStyle } }
      : darkTheme.tooltip,
    xAxis: props.option.xAxis
      ? Array.isArray(props.option.xAxis)
        ? props.option.xAxis.map((axis) => ({
            ...axis,
            axisLine: { ...darkTheme.axisLine, ...axis.axisLine },
            splitLine: { ...darkTheme.splitLine, ...axis.splitLine },
            axisLabel: { ...darkTheme.axisLabel, ...axis.axisLabel },
          }))
        : {
            ...props.option.xAxis,
            axisLine: { ...darkTheme.axisLine, ...props.option.xAxis.axisLine },
            splitLine: { ...darkTheme.splitLine, ...props.option.xAxis.splitLine },
            axisLabel: { ...darkTheme.axisLabel, ...props.option.xAxis.axisLabel },
          }
      : undefined,
    yAxis: props.option.yAxis
      ? Array.isArray(props.option.yAxis)
        ? props.option.yAxis.map((axis) => ({
            ...axis,
            axisLine: { ...darkTheme.axisLine, ...axis.axisLine },
            splitLine: { ...darkTheme.splitLine, ...axis.splitLine },
            axisLabel: { ...darkTheme.axisLabel, ...axis.axisLabel },
          }))
        : {
            ...props.option.yAxis,
            axisLine: { ...darkTheme.axisLine, ...props.option.yAxis.axisLine },
            splitLine: { ...darkTheme.splitLine, ...props.option.yAxis.splitLine },
            axisLabel: { ...darkTheme.axisLabel, ...props.option.yAxis.axisLabel },
          }
      : undefined,
  };

  chart.setOption(themedOption, true);
}

// Generate screen reader summary from chart data
function generateSummary() {
  if (!props.option) return "";
  const series = props.option.series || [];
  if (!series.length) return props.description || "图表数据加载中";

  const summaries = series.map((s) => {
    const data = s.data || [];
    if (!data.length) return `${s.name || "数据系列"}: 无数据`;
    const values = data.filter((v) => v != null);
    if (!values.length) return `${s.name || "数据系列"}: 无有效数据`;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2);
    return `${s.name || "数据系列"}: 共 ${values.length} 个数据点，最高 ${max}，最低 ${min}，平均 ${avg}`;
  });

  return summaries.join("；") + (props.description ? `。${props.description}` : "");
}

onMounted(() => {
  chart = echarts.init(host.value);
  applyOption();
  if (props.autoresize && host.value && typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(host.value);
  }
});

watch(() => props.option, applyOption, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <figure class="chart-wrapper" role="img" :aria-label="title || '数据图表'">
    <div ref="host" class="chart-panel" role="img" :aria-label="generateSummary()"></div>
    <figcaption class="sr-only">{{ generateSummary() }}</figcaption>
  </figure>
</template>

<style scoped>
.chart-wrapper {
  margin: 0;
  padding: 0;
}

.chart-panel {
  height: 320px;
  border-radius: var(--radius-md);
  overflow: hidden;
  touch-action: pan-y;
}

/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 640px) {
  .chart-panel {
    height: 220px;
  }
}
</style>
