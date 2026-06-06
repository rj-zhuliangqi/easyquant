<script setup>
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

onMounted(() => {
  chart = window.echarts?.init(host.value);
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
  <div ref="host" class="chart-panel"></div>
</template>

<style scoped>
.chart-panel {
  height: 320px;
  border-radius: var(--radius-md);
  overflow: hidden;
}
</style>
