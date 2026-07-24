<script setup>
const props = defineProps({
  title: { type: String, default: "" },
  subtitle: { type: String, default: "" },
  loading: { type: Boolean, default: false },
  noPadding: { type: Boolean, default: false },
});
</script>

<template>
  <article class="data-panel" :class="{ 'no-padding': noPadding }">
    <header v-if="title || $slots.header || $slots.actions" class="panel-header">
      <div class="panel-header-left">
        <h3 v-if="title" class="panel-title">{{ title }}</h3>
        <p v-if="subtitle" class="panel-subtitle">{{ subtitle }}</p>
        <slot name="header" />
      </div>
      <div v-if="$slots.actions" class="panel-header-actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="panel-body" :class="{ 'is-loading': loading }">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.data-panel {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: var(--radius-lg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  overflow: hidden;
}

.data-panel:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-5) var(--space-3);
  border-bottom: 1px solid var(--border);
}

.panel-header-left {
  display: grid;
  gap: 2px;
  flex: 1;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.panel-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.panel-body {
  padding: var(--space-5);
}

.panel-body.is-loading {
  opacity: 0.6;
  pointer-events: none;
}

.data-panel.no-padding .panel-body {
  padding: 0;
}
</style>
