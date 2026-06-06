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
    <span v-if="isLoading">首次加载中</span>
    <span v-else-if="isFetching">正在刷新</span>
    <span v-else>已就绪</span>
    <small v-if="updatedAt">更新于 {{ updatedAt }}</small>
  </div>
</template>
