<script setup>
const props = defineProps({
  rows: { type: Number, default: 3 },
  columns: { type: Number, default: 1 },
  type: { type: String, default: "card" }, // 'card', 'list', 'table'
});
</script>

<template>
  <div class="skeleton-wrapper" :class="`type-${type}`">
    <div
      v-for="i in rows"
      :key="i"
      class="skeleton-row"
      :style="{ animationDelay: `${(i - 1) * 100}ms` }"
    >
      <div
        v-for="j in columns"
        :key="j"
        class="skeleton-item"
        :style="{ animationDelay: `${(i * columns + j - 1) * 50}ms` }"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.skeleton-wrapper {
  display: grid;
  gap: var(--space-3);
}

.skeleton-row {
  display: grid;
  grid-template-columns: repeat(v-bind(columns), minmax(0, 1fr));
  gap: var(--space-3);
}

.skeleton-item {
  height: 80px;
  border-radius: var(--radius-md);
  background: linear-gradient(90deg, var(--surface-hover) 25%, var(--surface-active) 50%, var(--surface-hover) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.type-list .skeleton-item {
  height: 48px;
}

.type-table .skeleton-item {
  height: 40px;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
