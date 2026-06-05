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
});

const host = ref(null);
let chart;
let resizeObserver;

function applyOption() {
  if (!chart || !props.option) return;
  chart.setOption(props.option, true);
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
