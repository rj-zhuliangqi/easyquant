import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "./lib/auth";

// LoginView 保持静态（登出后首屏，体积小）；其余路由懒加载，减小首屏 chunk（P3-5）
import LoginView from "./views/LoginView.vue";

const HomeView = () => import("./views/HomeView.vue");
const AlertsView = () => import("./views/AlertsView.vue");
const NewsView = () => import("./views/NewsView.vue");
const SectorMonitorView = () => import("./views/SectorMonitorView.vue");
const LimitUpView = () => import("./views/LimitUpView.vue");
const OpportunityPoolView = () => import("./views/OpportunityPoolView.vue");
const WorkspaceView = () => import("./views/WorkspaceView.vue");
const AiCenterView = () => import("./views/AiCenterView.vue");
const AiJobsView = () => import("./views/AiJobsView.vue");
const ReviewView = () => import("./views/ReviewView.vue");
const UserMgmtView = () => import("./views/UserMgmtView.vue");

export const routes = [
  { path: "/login", name: "login", component: LoginView, meta: { title: "登录" } },
  { path: "/", name: "home", component: HomeView, meta: { title: "首页", keepAlive: true } },
  { path: "/news", name: "news", component: NewsView, meta: { title: "消息面", keepAlive: true } },
  { path: "/alerts", name: "alerts", component: AlertsView, meta: { title: "预警中心", keepAlive: true } },
  { path: "/opportunity-pool", name: "opportunity-pool", component: OpportunityPoolView, meta: { title: "机会池", keepAlive: true } },
  { path: "/sector-monitor", name: "sector-monitor", component: SectorMonitorView, meta: { title: "板块资金监控", keepAlive: true } },
  { path: "/limit-up-ladder", name: "limit-up-ladder", component: LimitUpView, meta: { title: "A股连板梯队", keepAlive: true } },
  { path: "/ai-center", name: "ai-center", component: AiCenterView, meta: { title: "AI 中台", keepAlive: true } },
  { path: "/review", name: "review", component: ReviewView, meta: { title: "复盘", keepAlive: true } },
  { path: "/ai-jobs", name: "ai-jobs", component: AiJobsView, meta: { title: "AI 任务", keepAlive: true } },
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
