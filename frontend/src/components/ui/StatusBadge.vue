<script setup>
const props = defineProps({
  status: { type: String, required: true }, // 'success', 'warning', 'danger', 'info', 'neutral'
  size: { type: String, default: "md" }, // 'sm', 'md', 'lg'
});

const statusConfig = {
  success: { color: "var(--success)", bg: "var(--success-soft)", label: "成功" },
  warning: { color: "var(--warning)", bg: "var(--warning-soft)", label: "警告" },
  danger: { color: "var(--danger)", bg: "var(--danger-soft)", label: "错误" },
  info: { color: "var(--info)", bg: "var(--info-soft)", label: "信息" },
  neutral: { color: "var(--text-muted)", bg: "rgba(148, 163, 184, 0.08)", label: "待定" },
};

const sizeConfig = {
  sm: { padding: "2px 8px", fontSize: "11px", height: "20px" },
  md: { padding: "3px 10px", fontSize: "12px", height: "24px" },
  lg: { padding: "4px 14px", fontSize: "13px", height: "28px" },
};

const config = statusConfig[props.status] || statusConfig.neutral;
const size = sizeConfig[props.size] || sizeConfig.md;
</script>

<template>
  <span
    class="status-badge"
    :style="{
      color: config.color,
      background: config.bg,
      padding: size.padding,
      fontSize: size.fontSize,
      minHeight: size.height,
    }"
  >
    <span class="status-dot" :style="{ background: config.color }"></span>
    <slot>{{ config.label }}</slot>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-full);
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  transition: transform var(--transition-fast);
}

.status-badge:hover {
  transform: scale(1.02);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
