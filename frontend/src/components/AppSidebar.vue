<script setup>
import { computed } from "vue";
import { useQueryClient } from "@tanstack/vue-query";
import { RouterLink } from "vue-router";
import { routes } from "../router";
import { fetchJson, pageQueryKey } from "../lib/api";

const queryClient = useQueryClient();

const navItems = computed(() =>
  routes.map((route) => ({
    name: route.name,
    label: route.meta.title,
    path: route.path,
  })),
);

async function prefetch(pathName) {
  if (pathName === "home" || pathName === "alerts" || pathName === "sector-monitor" || pathName === "limit-up-ladder" || pathName === "opportunity-pool" || pathName === "workspace" || pathName === "ai-center") {
    await queryClient.prefetchQuery({
      queryKey: pageQueryKey(pathName),
      queryFn: () => fetchJson(`/api/page/${pathName}`),
      staleTime: 30_000,
    });
  }
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">EQ</div>
      <div>
        <h1>EasyQuant</h1>
        <p>盘中工作台</p>
      </div>
    </div>
    <nav class="nav-list" aria-label="Main navigation">
      <RouterLink
        v-for="item in navItems"
        :key="item.name"
        :to="item.path"
        class="nav-item"
        active-class="is-active"
        @mouseenter="prefetch(item.name)"
        @focus="prefetch(item.name)"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
