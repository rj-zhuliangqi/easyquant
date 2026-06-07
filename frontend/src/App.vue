<script setup>
import { computed, ref } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppSidebar from "./components/AppSidebar.vue";
import MobileTopBar from "./components/MobileTopBar.vue";
import { getUsername } from "./lib/auth";

const route = useRoute();
const isLoginPage = computed(() => route.path === "/login");
const keepAliveNames = computed(() => ["home", "alerts", "opportunity-pool", "sector-monitor", "limit-up-ladder", "ai-center", "workspace"]);

const sidebarOpen = ref(false);
const username = computed(() => getUsername());

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value;
}

function closeSidebar() {
  sidebarOpen.value = false;
}
</script>

<template>
  <div v-if="isLoginPage" class="login-shell">
    <RouterView />
  </div>
  <div v-else class="app-shell">
    <!-- Mobile top bar (hidden on desktop) -->
    <MobileTopBar @toggle-sidebar="toggleSidebar" :username="username" />

    <!-- Sidebar overlay (mobile only) -->
    <Transition name="overlay-fade">
      <div v-if="sidebarOpen" class="sidebar-overlay" @click="closeSidebar"></div>
    </Transition>

    <AppSidebar :is-open="sidebarOpen" @close="closeSidebar" />
    <main class="main-shell">
      <RouterView v-slot="{ Component }">
        <Transition name="page-fade" mode="out-in">
          <KeepAlive :include="keepAliveNames">
            <component :is="Component" :key="route.name" />
          </KeepAlive>
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style>
/* Page transition animation */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity var(--transition-normal), transform var(--transition-normal);
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Sidebar overlay */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 299;
}

.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity var(--transition-normal);
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}
</style>
