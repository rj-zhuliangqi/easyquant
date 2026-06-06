import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "./lib/auth";

import HomeView from "./views/HomeView.vue";
import AlertsView from "./views/AlertsView.vue";
import SectorMonitorView from "./views/SectorMonitorView.vue";
import LimitUpView from "./views/LimitUpView.vue";
import OpportunityPoolView from "./views/OpportunityPoolView.vue";
import WorkspaceView from "./views/WorkspaceView.vue";
import AiCenterView from "./views/AiCenterView.vue";
import LoginView from "./views/LoginView.vue";
import UserMgmtView from "./views/UserMgmtView.vue";

export const routes = [
  { path: "/login", name: "login", component: LoginView, meta: { title: "登录" } },
  { path: "/", name: "home", component: HomeView, meta: { title: "首页", keepAlive: true } },
  { path: "/alerts", name: "alerts", component: AlertsView, meta: { title: "预警中心", keepAlive: true } },
  { path: "/opportunity-pool", name: "opportunity-pool", component: OpportunityPoolView, meta: { title: "机会池", keepAlive: true } },
  { path: "/sector-monitor", name: "sector-monitor", component: SectorMonitorView, meta: { title: "板块资金监控", keepAlive: true } },
  { path: "/limit-up-ladder", name: "limit-up-ladder", component: LimitUpView, meta: { title: "A股连板梯队", keepAlive: true } },
  { path: "/ai-center", name: "ai-center", component: AiCenterView, meta: { title: "AI 中台", keepAlive: true } },
  { path: "/workspace", name: "workspace", component: WorkspaceView, meta: { title: "个人观察台", keepAlive: true } },
  { path: "/user-mgmt", name: "user-mgmt", component: UserMgmtView, meta: { title: "用户管理" } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition;
    return { top: 0 };
  },
});

router.beforeEach((to, from, next) => {
  if (to.path !== "/login" && !isAuthenticated()) {
    next("/login");
  } else if (to.path === "/login" && isAuthenticated()) {
    next("/");
  } else {
    next();
  }
});

router.afterEach((to) => {
  document.title = `${to.meta.title || "EasyQuant"} - EasyQuant`;
});
