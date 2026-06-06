<script setup>
defineProps({
  isLoading: Boolean,
  isFetching: Boolean,
  updatedAt: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <div class="query-state" :class="{ fetching: isFetching }">
    <div class="status-indicator">
      <span class="status-dot" :class="{ pulse: isFetching, idle: !isLoading && !isFetching }"></span>
      <span v-if="isLoading" class="status-text">首次加载中</span>
      <span v-else-if="isFetching" class="status-text">正在刷新</span>
      <span v-else class="status-text">已就绪</span>
    </div>
    <small v-if="updatedAt" class="update-time">更新于 {{ updatedAt }}</small>
  </div>
</template>

<style scoped>
.query-state {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}

.status-dot.idle {
  background: var(--success);
}

.status-dot.pulse {
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.4);
  }
  50% {
    opacity: 0.7;
    transform: scale(0.85);
    box-shadow: 0 0 0 6px rgba(6, 182, 212, 0);
  }
}

.status-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.fetching .status-text {
  color: var(--accent);
}

.update-time {
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.7;
}
</style>
