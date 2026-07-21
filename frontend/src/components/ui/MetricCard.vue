<script setup>
import { sanitizeHtml } from "../../lib/sanitize";

const props = defineProps({
  label: { type: String, default: "" },
  value: { type: [String, Number], default: "" },
  subValue: { type: String, default: "" },
  icon: { type: String, default: "" },
  trend: { type: String, default: "" }, // 'up', 'down', 'neutral'
  accent: { type: String, default: "" }, // override accent color
  loading: { type: Boolean, default: false },
});

const trendIcons = {
  up: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>`,
  down: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>`,
  neutral: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
};

const trendColors = {
  up: "var(--success)",
  down: "var(--danger)",
  neutral: "var(--text-muted)",
};
</script>

<template>
  <article class="metric-card" :class="{ 'is-loading': loading }">
    <div class="metric-header">
      <span class="metric-label">{{ label }}</span>
      <span v-if="trend" class="metric-trend" :style="{ color: trendColors[trend] || trendColors.neutral }">
        <span class="trend-icon" v-html="sanitizeHtml(trendIcons[trend])"></span>
      </span>
    </div>
    <strong class="metric-value" :style="accent ? { color: accent } : {}">
      <template v-if="loading">
        <span class="skeleton-text" style="width: 80px; height: 32px; display: inline-block; border-radius: 6px;"></span>
      </template>
      <template v-else>{{ value }}</template>
    </strong>
    <small class="metric-sub" :class="{ 'skeleton-sub': loading }">
      <template v-if="!loading">{{ subValue }}</template>
    </small>
  </article>
</template>

<style scoped>
.metric-card {
  position: relative;
  overflow: hidden;
}

.metric-card.is-loading .metric-value {
  color: transparent;
}

.metric-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.metric-label {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
}

.metric-trend {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
}

.trend-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.trend-icon :deep(svg) {
  width: 14px;
  height: 14px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  line-height: 1.2;
}

.metric-sub {
  color: var(--text-muted);
  font-size: 12px;
  min-height: 18px;
}

.skeleton-text {
  background: linear-gradient(90deg, var(--surface-hover) 25%, var(--surface-active) 50%, var(--surface-hover) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
