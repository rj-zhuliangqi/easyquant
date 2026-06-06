<script setup>
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppSidebar from "./components/AppSidebar.vue";

const route = useRoute();
const isLoginPage = computed(() => route.path === "/login");
const keepAliveNames = computed(() => ["home", "alerts", "opportunity-pool", "sector-monitor", "limit-up-ladder", "ai-center", "workspace"]);
</script>

<template>
  <div v-if="isLoginPage" class="login-shell">
    <RouterView />
  </div>
  <div v-else class="app-shell">
    <AppSidebar />
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
</style>
