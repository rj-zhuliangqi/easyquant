<script setup>
import QueryState from "./QueryState.vue";

defineProps({
  eyebrow: { type: String, default: "" },
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  isLoading: { type: Boolean, default: false },
  isFetching: { type: Boolean, default: false },
  updatedAt: { type: String, default: "" },
});
</script>

<template>
  <header class="page-hero">
    <div>
      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <p v-if="subtitle" class="hero-copy">{{ subtitle }}</p>
    </div>
    <QueryState :is-loading="isLoading" :is-fetching="isFetching" :updated-at="updatedAt" />
  </header>
</template>
