<script setup>
import { sanitizeHtml } from "../../lib/sanitize";

const props = defineProps({
  title: { type: String, default: "暂无数据" },
  description: { type: String, default: "当前条件下没有匹配的数据" },
  icon: { type: String, default: "" },
});

const defaultIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></svg>`;
</script>

<template>
  <div class="empty-state">
    <div class="empty-icon" v-html="sanitizeHtml(icon || defaultIcon)"></div>
    <h4 class="empty-title">{{ title }}</h4>
    <p class="empty-desc">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
  animation: fadeInUp 0.4s ease;
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: var(--text-muted);
  margin-bottom: var(--space-4);
  opacity: 0.5;
}

.empty-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.empty-title {
  margin: 0 0 var(--space-2);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  max-width: 300px;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
