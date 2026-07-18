<script setup>
const props = defineProps({
  isLoading: Boolean,
  isFetching: Boolean,
  isError: { type: Boolean, default: false },
  error: { type: String, default: "" },
  updatedAt: {
    type: String,
    default: "",
  },
});
const emit = defineEmits(["retry"]);
</script>

<template>
  <div class="query-state" :class="{ fetching: isFetching, error: isError }">
    <div v-if="isError" class="error-state">
      <span class="status-dot error-dot"></span>
      <span class="status-text error-text">加载失败</span>
      <button class="retry-btn" type="button" @click="emit('retry')">重试</button>
    </div>
    <div v-else class="status-indicator">
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

.error-state {
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

.status-dot.error-dot {
  background: var(--danger, #ef4444);
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

.error-text {
  color: var(--danger, #ef4444);
}

.retry-btn {
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-full, 999px);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.retry-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.update-time {
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.7;
}
</style>
