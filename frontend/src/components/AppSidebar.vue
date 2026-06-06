<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useQueryClient } from "@tanstack/vue-query";
import { RouterLink, useRouter } from "vue-router";
import { routes } from "../router";
import { fetchJson, pageQueryKey } from "../lib/api";
import { getUsername, isAdmin, clearToken } from "../lib/auth";

const queryClient = useQueryClient();
const router = useRouter();

const navItems = computed(() =>
  routes
    .filter((route) => route.path !== "/login" && (route.path !== "/user-mgmt" || isAdmin()))
    .map((route) => ({
      name: route.name,
      label: route.meta.title,
      path: route.path,
    })),
);

const username = computed(() => getUsername());
const menuOpen = ref(false);

async function prefetch(pathName) {
  if (pathName === "home" || pathName === "alerts" || pathName === "sector-monitor" || pathName === "limit-up-ladder" || pathName === "opportunity-pool" || pathName === "workspace" || pathName === "ai-center") {
    await queryClient.prefetchQuery({
      queryKey: pageQueryKey(pathName),
      queryFn: () => fetchJson(`/api/page/${pathName}`),
      staleTime: 30_000,
    });
  }
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value;
}

function closeMenu() {
  menuOpen.value = false;
}

function goChangePassword() {
  menuOpen.value = false;
  router.push("/user-mgmt");
}

function handleLogout() {
  menuOpen.value = false;
  clearToken();
  queryClient.clear();
  router.push("/login");
}

// Click outside to close menu
function onClickOutside(e) {
  if (menuOpen.value && !e.target.closest(".sidebar-footer")) {
    menuOpen.value = false;
  }
}

onMounted(() => document.addEventListener("click", onClickOutside));
onUnmounted(() => document.removeEventListener("click", onClickOutside));
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
    <div class="sidebar-footer">
      <div class="user-block" @click.stop="toggleMenu">
        <div class="user-avatar">{{ username.charAt(0).toUpperCase() }}</div>
        <span class="user-name">{{ username }}</span>
        <svg class="chevron" :class="{ open: menuOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <Transition name="menu-slide">
        <div v-if="menuOpen" class="user-menu">
          <button class="menu-item" @click.stop="goChangePassword">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            修改密码
          </button>
          <div class="menu-divider"></div>
          <button class="menu-item menu-item-danger" @click.stop="handleLogout">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            退出登录
          </button>
        </div>
      </Transition>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-footer {
  margin-top: auto;
  padding-top: 16px;
  position: relative;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.user-block:hover {
  background: rgba(255, 255, 255, 0.08);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(15, 139, 141, 0.5), rgba(15, 139, 141, 0.2));
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
  color: #fff;
  flex-shrink: 0;
}

.user-name {
  flex: 1;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  width: 16px;
  height: 16px;
  color: rgba(255, 255, 255, 0.4);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.chevron.open {
  transform: rotate(180deg);
}

.user-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  right: 0;
  background: rgba(19, 34, 56, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 6px;
  backdrop-filter: blur(16px);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.menu-item svg {
  width: 16px;
  height: 16px;
  opacity: 0.6;
  flex-shrink: 0;
}

.menu-item-danger {
  color: rgba(248, 113, 113, 0.9);
}

.menu-item-danger:hover {
  background: rgba(239, 68, 68, 0.12);
}

.menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 8px;
}

.menu-slide-enter-active,
.menu-slide-leave-active {
  transition: all 0.15s ease;
}

.menu-slide-enter-from,
.menu-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
