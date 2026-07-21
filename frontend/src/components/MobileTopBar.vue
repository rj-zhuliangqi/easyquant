<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { getUsername } from "../lib/auth";

defineEmits(["toggle-sidebar"]);

const route = useRoute();
const username = computed(() => getUsername());
const avatar = computed(() => (username.value || "U").charAt(0).toUpperCase());
const pageTitle = computed(() => route.meta?.title || "EasyQuant");
</script>

<template>
  <header class="mobile-topbar">
    <button class="topbar-toggle" @click="$emit('toggle-sidebar')" aria-label="打开导航">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <line x1="4" y1="6" x2="20" y2="6" />
        <line x1="4" y1="12" x2="20" y2="12" />
        <line x1="4" y1="18" x2="20" y2="18" />
      </svg>
    </button>

    <h1 class="topbar-title">{{ pageTitle }}</h1>

    <div class="topbar-avatar" aria-hidden="true">{{ avatar }}</div>
  </header>
</template>

<style scoped>
.mobile-topbar {
  display: none;
}

@media (max-width: 1024px) {
  .mobile-topbar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 48px;
    padding: 0 var(--space-3);
    padding-top: var(--safe-top);
    background: rgba(11, 17, 33, 0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    z-index: var(--z-sticky);
  }

  .topbar-toggle {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--text);
    flex-shrink: 0;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .topbar-toggle:hover {
    background: var(--surface-hover);
    border-color: var(--border-hover);
  }

  .topbar-toggle svg {
    width: 20px;
    height: 20px;
  }

  .topbar-title {
    flex: 1;
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .topbar-avatar {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.5), rgba(6, 182, 212, 0.2));
    display: grid;
    place-items: center;
    font-weight: 700;
    font-size: 13px;
    color: #fff;
    flex-shrink: 0;
  }
}
</style>
