<script setup>
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppSidebar from "./components/AppSidebar.vue";

const route = useRoute();
const keepAliveNames = computed(() => ["home", "alerts", "opportunity-pool", "sector-monitor", "limit-up-ladder", "ai-center", "workspace"]);
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="main-shell">
      <RouterView v-slot="{ Component }">
        <KeepAlive :include="keepAliveNames">
          <component :is="Component" :key="route.name" />
        </KeepAlive>
      </RouterView>
    </main>
  </div>
</template>
