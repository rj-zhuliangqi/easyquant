<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: [String, Number, Boolean, null], default: null },
  options: { type: Array, required: true }, // [{value,label,hint?,group?}] or [{label, options:[...]}]
  placeholder: { type: String, default: "请选择" },
  size: { type: String, default: "md" }, // 'sm' | 'md' | 'lg'
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "change"]);

const open = ref(false);
const query = ref("");
const triggerRef = ref(null);
const listRef = ref(null);
const activeIndex = ref(0);
const panelStyle = ref({});

const flatOptions = computed(() => {
  const list = [];
  for (const entry of props.options) {
    if (entry && Array.isArray(entry.options)) {
      for (const opt of entry.options) {
        list.push({ ...opt, group: entry.label || "" });
      }
    } else if (entry) {
      list.push({ ...entry, group: "" });
    }
  }
  return list;
});

const filteredOptions = computed(() => {
  if (!query.value) return flatOptions.value;
  const q = query.value.toLowerCase();
  return flatOptions.value.filter(
    (o) => String(o.label || "").toLowerCase().includes(q) || String(o.hint || "").toLowerCase().includes(q),
  );
});

const selected = computed(() => flatOptions.value.find((o) => o.value === props.modelValue) || null);

const sizeStyle = computed(() => {
  if (props.size === "sm") return { padding: "6px 28px 6px 10px", fontSize: "13px", minHeight: "30px" };
  if (props.size === "lg") return { padding: "12px 36px 12px 14px", fontSize: "15px", minHeight: "46px" };
  return { padding: "10px 32px 10px 12px", fontSize: "14px", minHeight: "40px" };
});

const showSearch = computed(() => flatOptions.value.length >= 8);

function positionPanel() {
  const rect = triggerRef.value?.getBoundingClientRect();
  if (!rect) return;
  const panelMaxH = Math.min(window.innerHeight - rect.bottom - 12, 320);
  panelStyle.value = {
    position: "fixed",
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    maxHeight: `${panelMaxH}px`,
  };
}

async function toggle() {
  if (props.disabled) return;
  open.value = !open.value;
  if (open.value) {
    query.value = "";
    activeIndex.value = Math.max(
      0,
      filteredOptions.value.findIndex((o) => o.value === props.modelValue),
    );
    await nextTick();
    positionPanel();
    listRef.value?.focus?.();
  }
}

function close() {
  open.value = false;
  query.value = "";
}

function pick(opt) {
  if (opt.disabled) return;
  emit("update:modelValue", opt.value);
  emit("change", opt.value);
  close();
}

function onKeydown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    close();
    triggerRef.value?.focus?.();
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = Math.min(filteredOptions.value.length - 1, activeIndex.value + 1);
    scrollActiveIntoView();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = Math.max(0, activeIndex.value - 1);
    scrollActiveIntoView();
  } else if (event.key === "Enter") {
    event.preventDefault();
    const opt = filteredOptions.value[activeIndex.value];
    if (opt) pick(opt);
  }
}

function scrollActiveIntoView() {
  nextTick(() => {
    const el = listRef.value?.querySelector?.(`[data-idx="${activeIndex.value}"]`);
    el?.scrollIntoView?.({ block: "nearest" });
  });
}

function onDocClick(event) {
  if (!open.value) return;
  const triggerEl = triggerRef.value;
  const panelEl = listRef.value;
  if (triggerEl?.contains(event.target)) return;
  if (panelEl?.contains(event.target)) return;
  close();
}

watch(query, () => {
  activeIndex.value = 0;
});

onMounted(() => {
  document.addEventListener("mousedown", onDocClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onDocClick);
});

function fmtHint(hint) {
  return hint ? ` · ${hint}` : "";
}

// 把 group 信息保留，给模板分组渲染用
const groupedOptions = computed(() => {
  if (props.options.length && props.options[0]?.options) {
    return props.options.map((g) => ({
      label: g.label,
      items: g.options.map((o) => ({ ...o, group: g.label })),
    }));
  }
  return [{ label: "", items: flatOptions.value }];
});
</script>

<template>
  <div class="ui-select" :class="{ 'is-open': open, 'is-disabled': disabled }">
    <button
      ref="triggerRef"
      type="button"
      class="ui-select-trigger"
      :style="sizeStyle"
      :disabled="disabled"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <span class="ui-select-value" :class="{ 'is-placeholder': !selected }">
        {{ selected ? selected.label : placeholder }}
        <small v-if="selected?.hint" class="ui-select-hint">{{ fmtHint(selected.hint) }}</small>
      </span>
      <svg class="ui-select-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <polyline points="6 9 12 15 18 9" stroke="currentColor" stroke-width="2" />
      </svg>
    </button>
    <Teleport to="body">
      <div
        v-if="open"
        ref="listRef"
        tabindex="-1"
        class="ui-select-panel"
        :style="panelStyle"
        @keydown="onKeydown"
      >
        <input
          v-if="showSearch"
          v-model="query"
          class="ui-select-search"
          placeholder="搜索…"
          @keydown.stop="onKeydown"
        />
        <ul class="ui-select-list">
          <template v-for="group in groupedOptions" :key="group.label || '_'">
            <li v-if="group.label" class="ui-select-group">{{ group.label }}</li>
            <li
              v-for="(opt, gi) in group.items"
              :key="`${group.label}_${opt.value}_${gi}`"
              class="ui-select-item"
              :class="{
                'is-active': opt.value === modelValue,
                'is-highlighted': flatOptions.indexOf(opt) === activeIndex,
                'is-disabled': opt.disabled,
              }"
              :data-idx="flatOptions.indexOf(opt)"
              @click="pick(opt)"
              @mouseenter="activeIndex = flatOptions.indexOf(opt)"
            >
              <span class="ui-select-item-label">{{ opt.label }}</span>
              <span v-if="opt.hint" class="ui-select-item-hint">{{ opt.hint }}</span>
              <span v-if="opt.value === modelValue" class="ui-select-item-check">✓</span>
            </li>
          </template>
          <li v-if="!filteredOptions.length" class="ui-select-empty">无匹配项</li>
        </ul>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.ui-select {
  position: relative;
  display: inline-block;
  width: 100%;
}

.ui-select-trigger {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  text-align: left;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  appearance: none;
}

.ui-select-trigger:hover:not(:disabled) {
  border-color: var(--border-strong, rgba(148, 163, 184, 0.3));
}

.ui-select-trigger:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.ui-select.is-disabled .ui-select-trigger {
  opacity: 0.5;
  cursor: not-allowed;
}

.ui-select.is-open .ui-select-trigger {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.ui-select-value {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ui-select-value.is-placeholder {
  color: var(--text-muted);
}

.ui-select-hint {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 400;
}

.ui-select-chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.ui-select.is-open .ui-select-chevron {
  transform: rotate(180deg);
}

.ui-select-panel {
  z-index: 9999;
  background: var(--surface-elevated, var(--surface));
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  outline: none;
}

.ui-select-search {
  flex-shrink: 0;
  padding: 10px 12px;
  border: none;
  border-bottom: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  outline: none;
}

.ui-select-list {
  list-style: none;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  flex: 1;
}

.ui-select-group {
  padding: 8px 10px 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.ui-select-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm, 4px);
  font-size: 14px;
  color: var(--text);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.ui-select-item.is-highlighted {
  background: var(--accent-soft, rgba(56, 189, 248, 0.12));
}

.ui-select-item.is-active {
  color: var(--accent);
  font-weight: 600;
}

.ui-select-item.is-active.is-highlighted {
  background: var(--accent-soft, rgba(56, 189, 248, 0.16));
}

.ui-select-item.is-disabled {
  opacity: 0.4;
  pointer-events: none;
}

.ui-select-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ui-select-item-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.ui-select-item-check {
  color: var(--accent);
  font-weight: 700;
}

.ui-select-empty {
  padding: 12px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}
</style>