<script setup>
import DataPanel from "./DataPanel.vue";
import EmptyState from "./EmptyState.vue";

defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyTitle: { type: String, default: "暂无数据" },
  emptyDescription: { type: String, default: "当前没有数据" },
  keyField: { type: String, default: "id" },
  selectable: { type: Boolean, default: false },
  selectedIndex: { type: Number, default: -1 },
});

defineEmits(["select"])
;</script>

<template>
  <DataPanel :title="title">
    <div class="list-stack">
      <button
        v-for="(item, index) in items"
        :key="item[keyField] || index"
        class="list-button"
        :class="{ active: selectable && selectedIndex === index }"
        @click="selectable && $emit('select', index)"
      >
        <slot :item="item" :index="index">
          <strong>{{ item.name || item.title || "--" }}</strong>
          <span>{{ item.description || "" }}</span>
        </slot>
      </button>
      <EmptyState
        v-if="!items.length && !loading"
        :title="emptyTitle"
        :description="emptyDescription"
      />
    </div>
  </DataPanel>
</template>
