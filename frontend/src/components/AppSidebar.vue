<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useQueryClient } from "@tanstack/vue-query";
import { RouterLink, useRouter } from "vue-router";
import { routes } from "../router";
import { fetchJson, pageQueryKey } from "../lib/api";
import { getUsername, isAdmin, clearToken } from "../lib/auth";
import { sanitizeHtml } from "../lib/sanitize";

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["close"]);

const queryClient = useQueryClient();
const router = useRouter();

const navItems = ref(
  routes
    .filter((route) => route.path !== "/login" && (route.path !== "/user-mgmt" || isAdmin()))
    .map((route) => ({
      name: route.name,
      label: route.meta.title,
      path: route.path,
      icon: route.meta.icon || "",
    })),
);

// Group nav items into sections for better visual hierarchy
const navSections = computed(() => {
  const items = navItems.value;
  const sectionDefs = [
    { label: "概览", names: ["home", "news", "review", "alerts"] },
    { label: "市场", names: ["sector-monitor", "limit-up-ladder", "opportunity-pool"] },
    { label: "工具", names: ["ai-jobs", "ai-center", "workspace", "user-mgmt"] },
  ];
  return sectionDefs
    .map((def) => ({
      label: def.label,
      items: items.filter((i) => def.names.includes(i.name)),
    }))
    .filter((s) => s.items.length > 0);
});

const username = ref(getUsername());
const menuOpen = ref(false);

async function prefetch(pathName) {
  if (["home", "alerts", "sector-monitor", "limit-up-ladder", "opportunity-pool", "workspace", "ai-center"].includes(pathName)) {
    await queryClient.prefetchQuery({
      queryKey: pageQueryKey(pathName),
      queryFn: () => fetchJson(`/api/page/${pathName}`),
      staleTime: 30_000,
    });
  } else if (pathName === "ai-jobs") {
    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: ["ai-jobs"],
        queryFn: () => fetchJson("/api/ai/jobs"),
        staleTime: 30_000,
      }),
      queryClient.prefetchQuery({
        queryKey: ["ai-scheduler-status"],
        queryFn: () => fetchJson("/api/ai/scheduler-status"),
        staleTime: 30_000,
      }),
    ]);
  } else if (pathName === "review") {
    const today = new Date().toISOString().slice(0, 10);
    await queryClient.prefetchQuery({
      queryKey: ["ai-trading-day-review", today],
      queryFn: () => fetchJson(`/api/ai/trading-days/${today}`),
      staleTime: 30_000,
    });
  } else if (pathName === "news") {
    // News view fetches /api/ai/runs?job_type=news_scan directly; warm that
    // up so the panel paints instantly on click. Date defaults to today.
    const today = new Date().toISOString().slice(0, 10);
    await queryClient.prefetchQuery({
      queryKey: ["ai-runs", "news_scan", today],
      queryFn: () => fetchJson(`/api/ai/runs?job_type=news_scan&trading_date=${today}`),
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
  emit("close");
  router.push("/user-mgmt");
}

function handleLogout() {
  menuOpen.value = false;
  emit("close");
  clearToken();
  queryClient.clear();
  router.push("/login");
}

function onNavClick() {
  emit("close");
}

function onClickOutside(e) {
  if (menuOpen.value && !e.target.closest(".sidebar-footer")) {
    menuOpen.value = false;
  }
}

onMounted(() => document.addEventListener("click", onClickOutside));
onUnmounted(() => document.removeEventListener("click", onClickOutside));

// Nav icons mapping
const navIcons = {
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  alerts: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
  news: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16v16H4z"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="13" y2="16"/></svg>`,
  review: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="13" y2="14"/></svg>`,
  "ai-jobs": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  "opportunity-pool": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>`,
  "sector-monitor": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
  "limit-up-ladder": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
  "ai-center": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M12 6v6l4 2"/></svg>`,
  workspace: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  "user-mgmt": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
};
</script>

<template>
  <aside class="sidebar" :class="{ 'is-open': isOpen }">
    <div class="brand">
      <div class="brand-mark">EQ</div>
      <div>
        <h1>EasyQuant</h1>
        <p>盘中工作台</p>
      </div>
    </div>

    <nav class="nav-list" aria-label="Main navigation">
      <template v-for="section in navSections" :key="section.label">
        <div class="nav-section-label">{{ section.label }}</div>
        <RouterLink
          v-for="item in section.items"
          :key="item.name"
          :to="item.path"
          class="nav-item"
          active-class="is-active"
          @mouseenter="prefetch(item.name)"
          @focus="prefetch(item.name)"
          @click="onNavClick"
        >
          <span class="nav-icon" v-html="sanitizeHtml(navIcons[item.name] || '')"></span>
          <span class="nav-label">{{ item.label }}</span>
        </RouterLink>
      </template>
    </nav>

    <div class="sidebar-footer">
      <div class="user-block" @click.stop="toggleMenu">
        <div class="user-avatar">{{ username.charAt(0).toUpperCase() }}</div>
        <span class="user-name">{{ username }}</span>
        <svg class="chevron" :class="{ open: menuOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
      <Transition name="menu-slide">
        <div v-if="menuOpen" class="user-menu">
          <button class="menu-item" @click.stop="goChangePassword">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            修改密码
          </button>
          <div class="menu-divider"></div>
          <button class="menu-item menu-item-danger" @click.stop="handleLogout">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            退出登录
          </button>
        </div>
      </Transition>
    </div>
  </aside>
</template>

<style scoped>
/* Sidebar */
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: var(--space-4) var(--space-3);
  background: var(--nav-bg);
  border-right: 1px solid var(--nav-border);
  color: var(--text);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  transition: transform var(--transition-slow), opacity var(--transition-slow);
  z-index: 300;
}

.sidebar::-webkit-scrollbar {
  width: 4px;
}

.sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.15);
  border-radius: var(--radius-full);
}

/* Brand */
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--nav-border);
}

.brand-mark {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--accent), #0891b2);
  font-weight: 800;
  font-size: 14px;
  color: #fff;
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);
  flex-shrink: 0;
}

.brand h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand p {
  margin: 2px 0 0;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
}

/* Nav list */
.nav-list {
  display: grid;
  gap: 2px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  background: transparent;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  font-size: 13px;
  font-weight: 500;
  position: relative;
  min-height: 36px;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 16px;
  background: var(--accent);
  border-radius: 0 var(--radius-full) var(--radius-full) 0;
  transition: transform var(--transition-fast);
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.nav-item.is-active {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: rgba(6, 182, 212, 0.15);
}

.nav-item.is-active::before {
  transform: translateY(-50%) scaleY(1);
}

.nav-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0.7;
}

.nav-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.nav-item.is-active .nav-icon {
  opacity: 1;
}

/* Nav section labels */
.nav-section-label {
  padding: 12px var(--space-3) 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

/* Sidebar footer */
.sidebar-footer {
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--nav-border);
  position: relative;
}

.user-block {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.user-block:hover {
  background: rgba(255, 255, 255, 0.04);
}

.user-avatar {
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
  transition: transform var(--transition-fast);
  flex-shrink: 0;
}

.chevron.open {
  transform: rotate(180deg);
}

/* User menu */
.user-menu {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  right: 0;
  background: rgba(15, 23, 42, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  padding: 6px;
  backdrop-filter: blur(16px);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
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
  background: rgba(239, 68, 68, 0.1);
}

.menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 4px 8px;
}

/* Transitions */
.menu-slide-enter-active,
.menu-slide-leave-active {
  transition: all var(--transition-fast);
}

.menu-slide-enter-from,
.menu-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* Responsive: sidebar becomes fixed overlay on tablet/mobile */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 280px;
    transform: translateX(-100%);
    box-shadow: var(--shadow-xl);
  }

  .sidebar.is-open {
    transform: translateX(0);
  }
}
</style>
