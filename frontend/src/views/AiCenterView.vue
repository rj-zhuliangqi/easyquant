<script setup>
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import QueryState from "../components/QueryState.vue";
import { fetchJson, fetchStream, pageQueryKey } from "../lib/api";
import { marked } from "marked";
import { sanitizeHtml } from "../lib/sanitize";

defineOptions({ name: "ai-center" });

const route = useRoute();
const router = useRouter();

// AI 中台只保留平台驾驶舱、通用结果、Skill 工坊与引擎配置。
// 业务域页面（AI任务 / 机会池 / 复盘）由各自独立路由承接。
const TAB_KEYS = ["overview", "results", "skill-chat", "config"];
const DEPRECATED_TAB_TARGETS = {
  jobs: "/ai-jobs",
  picks: "/opportunity-pool",
  review: "/review",
};

// ── Tab state — persisted in URL query so a refresh keeps the user on the
// same tab and shared links land where the sender intended. The router-level
// /review and /ai-jobs paths set ?tab=review / ?tab=jobs respectively, so the
// same AiCenterView component serves both alias routes.
function initialTabFromRoute() {
  const fromQuery = route.query?.tab;
  if (typeof fromQuery === "string" && TAB_KEYS.includes(fromQuery)) return fromQuery;
  return "overview";
}

const activeTab = ref(initialTabFromRoute());

// React to in-app route changes (e.g. clicking sidebar /review while already
// inside AiCenterView).
watch(
  () => [route.path, route.query.tab],
  () => {
    const fromQuery = route.query?.tab;
    if (typeof fromQuery === "string" && DEPRECATED_TAB_TARGETS[fromQuery]) {
      const query = { ...route.query };
      delete query.tab;
      router.replace({ path: DEPRECATED_TAB_TARGETS[fromQuery], query }).catch(() => {});
      return;
    }
    const next = initialTabFromRoute();
    if (next !== activeTab.value) activeTab.value = next;
  },
  { immediate: true },
);

// Persist tab changes to the URL without spamming history (replace, not push).
watch(activeTab, (next) => {
  const currentQuery = { ...route.query };
  if (next === "overview") {
    delete currentQuery.tab;
  } else {
    currentQuery.tab = next;
  }
  // Only call router.replace when the query actually changed, otherwise we
  // recurse on the route watcher above.
  if (currentQuery.tab !== route.query.tab) {
    router.replace({ path: route.path, query: currentQuery }).catch(() => {});
  }
});
const tabs = [
  { key: "overview", label: "今日概览", icon: "📊" },
  { key: "results", label: "任务结果", icon: "📄" },
  { key: "skill-chat", label: "Skill工坊", icon: "🤖" },
  { key: "config", label: "配置", icon: "🔧" },
];

// ── Data queries ──
const pageQuery = useQuery({
  queryKey: pageQueryKey("ai-center"),
  queryFn: () => fetchJson("/api/page/ai-center"),
  staleTime: 30_000,
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const summary = computed(() => payload.value.overview?.summary || {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);

const entryCards = computed(() => [
  {
    title: "AI任务",
    description: "查看定时任务、调度状态和手动执行入口。",
    to: "/ai-jobs",
    stat: `${summary.value.ops_summary?.success_jobs ?? 0}/${summary.value.ops_summary?.total_jobs ?? 0}`,
    statLabel: "今日成功/任务",
  },
  {
    title: "机会池",
    description: "查看强势板块候选与 AI T+1 选股结果。",
    to: "/opportunity-pool",
    stat: summary.value.today_pick_count ?? 0,
    statLabel: "当日推荐",
  },
  {
    title: "复盘中心",
    description: "沉淀日内复盘、失败模式和次日关注。",
    to: "/review",
    stat: summary.value.experience_count ?? 0,
    statLabel: "经验条目",
  },
  {
    title: "消息面",
    description: "查看盘前 AI 消息面和即时资讯流。",
    to: "/news",
    stat: "08:20",
    statLabel: "每日任务",
  },
]);

function pickLevelLabel(level) {
  const map = { strong_recommend: "强烈推荐", confirm: "确认", candidate: "候选", watch: "观察" };
  return map[level] || level;
}

function statusClass(status) {
  if (status === "success") return "status-success";
  if (status === "failed") return "status-danger";
  return "status-neutral";
}

// ── Engine config state ──
const enginesQuery = useQuery({
  queryKey: ["ai-engines"],
  queryFn: () => fetchJson("/api/ai/engines"),
  enabled: computed(() => activeTab.value === "config"),
  staleTime: 60_000,
});
const engines = computed(() => enginesQuery.data.value?.engines || []);

// ── Job Results state ──
function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

const resultDate = ref(typeof route.query.trading_date === "string" ? route.query.trading_date : todayIso());
const selectedRunId = ref(route.query.run_id ? Number(route.query.run_id) : null);

const resultsQuery = useQuery({
  queryKey: computed(() => ["ai-runs-by-date", resultDate.value]),
  queryFn: () => fetchJson(`/api/ai/runs?trading_date=${resultDate.value}&status=success`),
  enabled: computed(() => activeTab.value === "results"),
  staleTime: 30_000,
});
const resultItems = computed(() => resultsQuery.data.value?.items || []);

watch(
  () => [route.query.trading_date, route.query.run_id, route.query.tab],
  () => {
    if (typeof route.query.trading_date === "string" && route.query.trading_date !== resultDate.value) {
      resultDate.value = route.query.trading_date;
    }
    const nextRunId = route.query.run_id ? Number(route.query.run_id) : null;
    if (nextRunId !== selectedRunId.value) selectedRunId.value = nextRunId;
  },
);

watch(resultItems, (items) => {
  if (!selectedRunId.value && items.length) {
    selectedRunId.value = items[0].id;
  }
});

watch(selectedRunId, (next) => {
  if (activeTab.value !== "results") return;
  const currentQuery = { ...route.query, tab: "results", trading_date: resultDate.value };
  if (next) currentQuery.run_id = String(next);
  else delete currentQuery.run_id;
  if (currentQuery.run_id !== route.query.run_id || currentQuery.trading_date !== route.query.trading_date) {
    router.replace({ path: route.path, query: currentQuery }).catch(() => {});
  }
});

const detailQuery = useQuery({
  queryKey: computed(() => ["ai-run-detail", selectedRunId.value]),
  queryFn: () => fetchJson(`/api/ai/runs/${selectedRunId.value}`),
  enabled: computed(() => activeTab.value === "results" && !!selectedRunId.value),
  staleTime: 60_000,
});
const resultDetail = computed(() => detailQuery.data.value || {});
const rawResultOutput = computed(() =>
  resultDetail.value?.raw_output_text ||
  resultDetail.value?.raw_output ||
  resultDetail.value?.result_payload?.raw_output ||
  "",
);
const structuredPicks = computed(() =>
  resultDetail.value?.picks || resultDetail.value?.result_payload?.structured_picks || [],
);
const resultPayloadJson = computed(() => {
  const payload = resultDetail.value?.result_payload;
  if (!payload || !Object.keys(payload).length) return "";
  return JSON.stringify(payload, null, 2);
});
const renderedMarkdown = computed(() => {
  let raw = rawResultOutput.value;
  if (!raw) return "";

  // Auto-detect: if raw_output contains HTML tags, render directly
  const isHtml = /<[a-z][\s\S]*>/i.test(raw);
  if (isHtml) return sanitizeHtml(raw);

  // Legacy markdown output — convert to HTML via marked + post-process
  raw = raw.replace(/^【([^】]+)】\s*$/gm, "## $1");
  raw = raw.replace(/^={3,}\s*$/gm, "---");
  raw = raw.replace(/^[→›]\s*/gm, "- ");
  const html = marked(raw);
  return sanitizeHtml(html
    .replace(/([+-]\d+\.?\d*%)/g, (m) => {
      const color = m.startsWith("+") ? "#4ade80" : "#f87171";
      return `<span style="color:${color};font-weight:600">${m}</span>`;
    })
    .replace(/(涨停|一字板|地天板)/g, '<span style="color:#f87171;font-weight:600">$1</span>')
    .replace(/(跌停|一字跌停)/g, '<span style="color:#93c5fd;font-weight:600">$1</span>'));
});

// ── Skill Chat state ──
const chatMessages = ref([]);
const chatInput = ref("");
const chatLoading = ref(false);
const chatStreaming = ref(false);
const chatDraft = ref(null);
let chatAbortController = null;

async function sendChatMessage() {
  const message = chatInput.value.trim();
  if (!message || chatLoading.value) return;

  chatMessages.value.push({ role: "user", content: message });
  chatInput.value = "";
  chatLoading.value = true;
  chatDraft.value = null;

  // 流式占位：先 push 一个空的 assistant 消息，每收到 delta 就 in-place 写入
  const assistantMsg = { role: "assistant", content: "" };
  chatMessages.value.push(assistantMsg);
  chatStreaming.value = true;
  chatAbortController = new AbortController();

  let streamedText = "";

  try {
    await fetchStream(
      "/api/ai/skill-chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: chatMessages.value.slice(0, -2), // 排除 user + 占位 assistant
        }),
        signal: chatAbortController.signal,
      },
      (event) => {
        if (event?.type === "delta" && typeof event.text === "string") {
          streamedText += event.text;
          assistantMsg.content = streamedText;
        } else if (event?.type === "done") {
          if (!streamedText && event.response) {
            assistantMsg.content = event.response;
            streamedText = event.response;
          }
          if (event.skill_draft) {
            chatDraft.value = event.skill_draft;
          }
        } else if (event?.type === "error") {
          const msg = event.message || "未知错误";
          assistantMsg.content = streamedText
            ? `${streamedText}\n\n[错误] ${msg}`
            : `[错误] ${msg}`;
        }
      },
    );
    if (!assistantMsg.content) assistantMsg.content = "无响应";
  } catch (error) {
    if (error?.name === "AbortError") {
      assistantMsg.content = streamedText
        ? `${streamedText}\n\n[已停止生成]`
        : "[已停止生成]";
    } else {
      assistantMsg.content = streamedText
        ? `${streamedText}\n\n[请求失败] ${error.message || "未知错误"}`
        : `请求失败: ${error.message || "未知错误"}`;
    }
  } finally {
    chatLoading.value = false;
    chatStreaming.value = false;
    chatAbortController = null;
  }
}

function stopChat() {
  if (chatAbortController) {
    chatAbortController.abort();
  }
}

function clearChat() {
  if (chatAbortController) chatAbortController.abort();
  chatMessages.value = [];
  chatDraft.value = null;
  chatInput.value = "";
  chatLoading.value = false;
  chatStreaming.value = false;
}

function applySkillDraft() {
  chatMessages.value.push({
    role: "assistant",
    content: "当前版本仅生成策略配置草案；应用到任务请先在 AI任务 / 配置流程中人工确认。",
  });
}

</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">策略与运行</p>
        <h2>AI 中台</h2>
        <p class="hero-copy">AI 平台驾驶舱：运行摘要、通用结果查看、Skill 工坊与执行配置。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" />
    </header>

    <!-- Tab Navigation -->
    <nav class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </nav>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 今日概览                               -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'overview'">
      <section class="card-grid">
        <article class="metric-card">
          <span>当日推荐</span>
          <strong>{{ summary.today_pick_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>昨日跟踪</span>
          <strong>{{ summary.yesterday_followup_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>经验条目</span>
          <strong>{{ summary.experience_count ?? 0 }}</strong>
        </article>
        <article class="metric-card">
          <span>成功任务</span>
          <strong>{{ summary.ops_summary?.success_jobs ?? 0 }}/{{ summary.ops_summary?.total_jobs ?? 0 }}</strong>
        </article>
      </section>

      <section class="entry-grid mt-lg">
        <RouterLink v-for="card in entryCards" :key="card.to" :to="card.to" class="entry-card">
          <div>
            <span class="entry-stat">{{ card.stat }}</span>
            <small>{{ card.statLabel }}</small>
          </div>
          <strong>{{ card.title }}</strong>
          <p>{{ card.description }}</p>
        </RouterLink>
      </section>

      <section class="panel mt-lg">
        <div class="panel-head"><h3>平台摘要</h3></div>
        <div class="summary-grid">
          <div class="summary-item">
            <span>昨日跟踪</span>
            <strong>{{ summary.yesterday_followup_count ?? 0 }}</strong>
          </div>
          <div class="summary-item">
            <span>可用 Skill</span>
            <strong>{{ payload.skills?.items?.length ?? 0 }}</strong>
          </div>
          <div class="summary-item">
            <span>规则包</span>
            <strong>{{ payload.rulepacks?.items?.length ?? 0 }}</strong>
          </div>
          <div class="summary-item">
            <span>最近运行</span>
            <strong>{{ payload.runs?.items?.length ?? 0 }}</strong>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 任务结果                               -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'results'">
      <section class="panel">
        <div class="panel-head">
          <h3>任务结果</h3>
          <div class="result-filters">
            <input
              type="date"
              v-model="resultDate"
              class="date-input"
              @change="selectedRunId = null"
            />
            <select v-if="resultItems.length" v-model.number="selectedRunId" class="job-select">
              <option :value="null" disabled>选择任务...</option>
              <option v-for="item in resultItems" :key="item.id" :value="item.id">
                {{ item.job_name || item.skill_name || item.id }} · {{ item.status }}
                {{ item.structured_summary?.market_phase ? `— ${item.structured_summary.market_phase}` : '' }}
              </option>
            </select>
          </div>
        </div>

        <div v-if="selectedRunId && (renderedMarkdown || structuredPicks.length || resultPayloadJson)" class="result-content">
          <div class="result-meta-row">
            <strong>{{ resultDetail.job_name || resultDetail.skill_name || '任务结果' }}</strong>
            <span class="run-type">{{ resultDetail.job_type || resultDetail.result_type }}</span>
            <span class="run-date">{{ resultDetail.trading_date }}</span>
            <span class="status-badge" :class="statusClass(resultDetail.status)">{{ resultDetail.status }}</span>
          </div>

          <div v-if="structuredPicks.length" class="result-pick-grid">
            <article v-for="pick in structuredPicks" :key="`${pick.stock_code}-${pick.stock_name}`" class="result-pick-card">
              <div class="pick-header">
                <span class="pick-code">{{ pick.stock_code }}</span>
                <span class="pick-name">{{ pick.stock_name }}</span>
                <span v-if="pick.pick_level" class="pick-badge" :class="pick.pick_level">{{ pickLevelLabel(pick.pick_level) }}</span>
              </div>
              <div class="pick-meta">
                <span v-if="pick.sector_name" class="pick-sector">{{ pick.sector_name }}</span>
                <span v-if="pick.confidence_score != null">置信度 {{ pick.confidence_score }}</span>
              </div>
              <p v-if="pick.reason_summary" class="pick-reason">{{ pick.reason_summary }}</p>
              <p v-if="pick.entry_hint" class="pick-reason">入场提示：{{ pick.entry_hint }}</p>
              <div v-if="pick.theme_tags?.length" class="pick-tags">
                <span v-for="tag in pick.theme_tags" :key="tag" class="tag-chip">{{ tag }}</span>
              </div>
            </article>
          </div>

          <div v-if="renderedMarkdown" class="markdown-body" v-html="renderedMarkdown"></div>
          <pre v-else-if="resultPayloadJson" class="result-json">{{ resultPayloadJson }}</pre>
        </div>

        <div v-else-if="selectedRunId && resultDetail.status === 'failed'" class="empty-state">
          <p>任务执行失败</p>
          <span>{{ resultDetail.error_stage || '' }} {{ resultDetail.error_text || '未返回错误详情' }}</span>
        </div>

        <div v-else-if="selectedRunId" class="empty-state">
          <p>该任务暂无可展示结果</p>
          <span>run_id={{ selectedRunId }} 未返回 raw_output_text / structured_picks / result_payload。</span>
        </div>

        <div v-else-if="!resultItems.length" class="empty-state">
          <p>暂无结果</p>
          <span>{{ resultDate }} 没有任何成功执行的任务结果</span>
        </div>

        <div v-else class="result-hint">
          <span>请从上方下拉选择一个任务查看详细结果</span>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: Skill工坊                              -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'skill-chat'">
      <section class="panel">
        <div class="panel-head">
          <h3>🤖 Skill 工坊</h3>
          <button class="btn-clear" @click="clearChat">清空对话</button>
        </div>
        <div class="chat-container">
          <div class="chat-messages">
            <div v-if="!chatMessages.length" class="chat-welcome">
              <p>👋 欢迎来到 Skill 工坊！</p>
              <span>通过自然语言描述你的选股策略需求，AI 将帮你生成策略配置。</span>
              <div class="chat-examples">
                <button class="example-chip" @click="chatInput = '帮我创建一个早盘强势股筛选策略，要求：1. 量比大于2 2. 涨幅大于3% 3. 排除ST股'">
                  💡 早盘强势股筛选
                </button>
                <button class="example-chip" @click="chatInput = '创建一个尾盘资金流入选股策略，筛选尾盘30分钟主力资金净流入前20的股票'">
                  💡 尾盘资金流入选股
                </button>
                <button class="example-chip" @click="chatInput = '帮我创建一个板块轮动策略，追踪当日热点板块中的龙头股'">
                  💡 板块轮动策略
                </button>
              </div>
            </div>
            <div
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              class="chat-message"
              :class="msg.role"
            >
              <div class="chat-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
              <div class="chat-bubble">
                <div class="chat-text">
                  {{ msg.content }}<span
                    v-if="chatStreaming && idx === chatMessages.length - 1"
                    class="caret"
                  >▍</span>
                </div>
              </div>
            </div>
            <div v-if="chatLoading && !chatStreaming" class="chat-message assistant">
              <div class="chat-avatar">🤖</div>
              <div class="chat-bubble loading">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
          </div>

          <!-- Skill Draft Preview -->
          <div v-if="chatDraft" class="chat-draft">
            <h4>📋 生成的策略配置</h4>
            <pre class="draft-json">{{ JSON.stringify(chatDraft, null, 2) }}</pre>
            <div class="draft-actions">
              <button class="btn-apply" @click="applySkillDraft">✅ 应用此配置</button>
              <button class="btn-cancel" @click="chatDraft = null">❌ 放弃</button>
            </div>
          </div>

          <div class="chat-input-area">
            <textarea
              v-model="chatInput"
              class="chat-input"
              placeholder="描述你的选股策略需求..."
              rows="3"
              :disabled="chatStreaming"
              @keydown.enter.prevent="sendChatMessage"
            ></textarea>
            <button
              v-if="chatStreaming"
              class="chat-stop-btn"
              type="button"
              @click="stopChat"
            >
              ⏹ 停止
            </button>
            <button
              v-else
              class="chat-send-btn"
              type="button"
              :disabled="!chatInput.trim() || chatLoading"
              @click="sendChatMessage"
            >
              {{ chatLoading ? '生成中...' : '发送' }}
            </button>
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════════════════════════════════════ -->
    <!-- Tab: 配置                                   -->
    <!-- ═══════════════════════════════════════════ -->
    <template v-if="activeTab === 'config'">
      <section class="panel">
        <div class="panel-head"><h3>执行引擎</h3></div>
        <div class="engine-list">
          <div v-for="eng in engines" :key="eng.type" class="engine-card" :class="{ disabled: !eng.available }">
            <div class="engine-main">
              <span class="engine-name">{{ eng.name }}</span>
              <span class="status-badge" :class="eng.available ? 'status-success' : 'status-danger'">
                {{ eng.available ? '可用' : '不可用' }}
              </span>
            </div>
            <p class="engine-desc">{{ eng.description }}</p>
            <div v-if="eng.config_fields?.length" class="engine-fields">
              配置项: {{ eng.config_fields.join(', ') }}
            </div>
          </div>
        </div>
      </section>

      <section class="panel mt-lg">
        <div class="panel-head"><h3>任务调度</h3></div>
        <div class="handoff-card">
          <strong>任务启停与调度已迁移到 AI任务</strong>
          <p>这里保留执行引擎能力说明；定时任务状态、手动执行和调度开关请到独立页面处理。</p>
          <RouterLink class="handoff-link" to="/ai-jobs">进入 AI任务 →</RouterLink>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
/* ── Tab Navigation ── */
.tab-nav {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--surface-active, rgba(255,255,255,0.04));
  border-radius: 12px;
  margin-bottom: 20px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted, #94a3b8);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.tab-btn:hover { color: var(--text, #e2e8f0); background: rgba(255,255,255,0.04); }
.tab-btn.active { color: var(--text, #e2e8f0); background: var(--surface, #1e293b); }
.tab-icon { font-size: 14px; }

/* ── Entry Cards ── */
.entry-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.entry-card { display: grid; gap: 8px; padding: 16px; border-radius: 12px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text, #e2e8f0); text-decoration: none; transition: all 0.15s ease; }
.entry-card:hover { border-color: var(--accent, #06b6d4); transform: translateY(-1px); }
.entry-card div { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.entry-stat { font-size: 22px; font-weight: 800; color: var(--accent, #06b6d4); }
.entry-card small { color: var(--text-muted, #94a3b8); font-size: 11px; }
.entry-card strong { font-size: 15px; }
.entry-card p { margin: 0; color: var(--text-secondary, #cbd5e1); font-size: 13px; line-height: 1.6; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.summary-item { padding: 12px; border-radius: 10px; background: rgba(255,255,255,0.025); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.summary-item span { display: block; color: var(--text-muted, #94a3b8); font-size: 12px; margin-bottom: 6px; }
.summary-item strong { font-size: 20px; color: var(--text, #e2e8f0); }

/* ── Pick Cards ── */
.pick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.pick-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--surface, #1e293b);
  border: 1px solid var(--border, rgba(255,255,255,0.06));
}
.pick-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.pick-code { font-family: monospace; font-size: 13px; color: var(--text-muted, #94a3b8); font-weight: 600; }
.pick-name { font-weight: 600; font-size: 15px; flex: 1; }
.pick-badge { font-size: 11px; padding: 2px 8px; border-radius: 20px; font-weight: 600; }
.pick-badge.strong_recommend { color: #f87171; background: rgba(248,113,113,0.1); }
.pick-badge.confirm { color: #fbbf24; background: rgba(251,191,36,0.1); }
.pick-badge.candidate { color: #60a5fa; background: rgba(96,165,250,0.1); }
.pick-badge.watch { color: #94a3b8; background: rgba(148,163,184,0.1); }
.pick-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 6px; }
.pick-sector { color: #60a5fa; }
.pick-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.tag-chip { font-size: 11px; padding: 1px 8px; border-radius: 20px; background: rgba(148,163,184,0.08); color: var(--text-muted, #94a3b8); }
.pick-reason { font-size: 13px; color: var(--text-secondary, #cbd5e1); line-height: 1.5; margin: 4px 0 0; }

/* ── Engine Cards ── */
.engine-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.engine-card { padding: 14px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.engine-card.disabled { opacity: 0.6; }
.engine-main { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.engine-name { font-weight: 600; font-size: 14px; }
.engine-desc { font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 6px; }
.engine-fields { font-size: 11px; color: var(--text-muted, #94a3b8); font-family: monospace; }

/* ── Handoff Card ── */
.handoff-card { padding: 16px; border-radius: 10px; background: rgba(255,255,255,0.025); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.handoff-card strong { display: block; margin-bottom: 6px; color: var(--text, #e2e8f0); }
.handoff-card p { margin: 0 0 12px; color: var(--text-secondary, #cbd5e1); font-size: 13px; line-height: 1.6; }
.handoff-link { color: var(--accent, #06b6d4); font-weight: 700; text-decoration: none; }
.handoff-link:hover { text-decoration: underline; }

/* ── Empty State ── */
.empty-state { text-align: center; padding: 32px; color: var(--text-muted, #94a3b8); }
.empty-state p { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.empty-state span { font-size: 12px; }

/* ── Utility ── */
.mt-lg { margin-top: 20px; }

/* ── Skill Chat ── */
.chat-container { display: flex; flex-direction: column; gap: 16px; }
.chat-messages { display: flex; flex-direction: column; gap: 12px; min-height: 200px; }
.chat-welcome { text-align: center; padding: 40px 20px; color: var(--text-muted, #94a3b8); }
.chat-welcome p { font-size: 18px; font-weight: 600; margin-bottom: 8px; color: var(--text, #e2e8f0); }
.chat-welcome span { font-size: 13px; display: block; margin-bottom: 20px; }
.chat-examples { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.example-chip { padding: 8px 14px; border-radius: 20px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text-muted, #94a3b8); font-size: 12px; cursor: pointer; transition: all 0.15s ease; }
.example-chip:hover { background: rgba(255,255,255,0.04); color: var(--text, #e2e8f0); }

.chat-message { display: flex; gap: 10px; align-items: flex-start; }
.chat-message.user { flex-direction: row-reverse; }
.chat-avatar { font-size: 20px; flex-shrink: 0; }
.chat-bubble { padding: 10px 14px; border-radius: 12px; max-width: 80%; }
.chat-message.user .chat-bubble { background: var(--surface-active, rgba(255,255,255,0.04)); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.chat-message.assistant .chat-bubble { background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.chat-text { margin: 0; white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 13px; line-height: 1.6; color: var(--text, #e2e8f0); }
.caret { display: inline-block; width: 7px; margin-left: 2px; color: var(--accent, #0ea5e9); animation: caret-blink 1s steps(1) infinite; }
@keyframes caret-blink { 50% { opacity: 0; } }

.chat-input-area { display: flex; gap: 10px; align-items: flex-end; }
.chat-input { flex: 1; padding: 10px 14px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text, #e2e8f0); font-size: 13px; resize: vertical; min-height: 60px; }
.chat-input:focus { outline: none; border-color: rgba(255,255,255,0.15); }
.chat-input:disabled { opacity: 0.6; cursor: not-allowed; }
.chat-send-btn { padding: 10px 20px; border-radius: 10px; background: var(--accent, #0ea5e9); color: white; font-size: 13px; font-weight: 600; border: none; cursor: pointer; transition: all 0.15s ease; }
.chat-send-btn:hover:not(:disabled) { background: #0284c7; }
.chat-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.chat-stop-btn { padding: 10px 20px; border-radius: 10px; background: rgba(248,113,113,0.15); color: #f87171; font-size: 13px; font-weight: 600; border: 1px solid rgba(248,113,113,0.35); cursor: pointer; transition: all 0.15s ease; }
.chat-stop-btn:hover { background: rgba(248,113,113,0.25); }

.chat-draft { padding: 16px; border-radius: 10px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.chat-draft h4 { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: var(--text, #e2e8f0); }
.draft-json { padding: 12px; border-radius: 8px; background: rgba(0,0,0,0.2); font-family: monospace; font-size: 12px; line-height: 1.5; color: var(--text-muted, #94a3b8); overflow-x: auto; margin-bottom: 12px; }
.draft-actions { display: flex; gap: 10px; }
.btn-apply { padding: 8px 16px; border-radius: 8px; background: rgba(74,222,128,0.1); color: #4ade80; font-size: 13px; font-weight: 600; border: none; cursor: pointer; }
.btn-cancel { padding: 8px 16px; border-radius: 8px; background: rgba(248,113,113,0.1); color: #f87171; font-size: 13px; font-weight: 600; border: none; cursor: pointer; }
.btn-clear { padding: 4px 10px; border-radius: 6px; background: rgba(148,163,184,0.08); color: var(--text-muted, #94a3b8); font-size: 11px; border: none; cursor: pointer; }
.btn-clear:hover { background: rgba(148,163,184,0.15); }

/* Typing indicator */
.loading { display: flex; gap: 4px; padding: 12px 16px; }
.typing-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted, #94a3b8); animation: typing 1.4s infinite ease-in-out both; }
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── Job Results ── */
.date-input { padding: 6px 10px; border-radius: 8px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text, #e2e8f0); font-size: 13px; font-family: monospace; }
.date-input:focus { outline: none; border-color: rgba(255,255,255,0.15); }
.job-select { padding: 6px 10px; border-radius: 8px; background: var(--surface, #1e293b); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text, #e2e8f0); font-size: 13px; min-width: 260px; max-width: 560px; }
.job-select:focus { outline: none; border-color: rgba(255,255,255,0.15); }
.result-meta-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border, rgba(255,255,255,0.06)); }
.result-pick-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; margin-bottom: 18px; }
.result-pick-card { padding: 12px; border-radius: 10px; background: rgba(255,255,255,0.025); border: 1px solid var(--border, rgba(255,255,255,0.06)); }
.result-json { padding: 12px; border-radius: 10px; background: rgba(0,0,0,0.28); border: 1px solid var(--border, rgba(255,255,255,0.06)); color: var(--text-secondary, #cbd5e1); overflow-x: auto; font-size: 12px; line-height: 1.6; }

/* ── Markdown Body — 金融报告风格 ── */
.markdown-body {
  font-size: 15px; line-height: 1.9; color: var(--text, #e2e8f0);
  max-width: 100%; overflow-x: auto; word-break: break-word;
}
.markdown-body h2 {
  font-size: 18px; font-weight: 700; color: var(--text, #e2e8f0);
  margin: 28px 0 14px; padding-bottom: 10px;
  border-bottom: 2px solid rgba(248,113,113,0.3);
}
.markdown-body h3 {
  font-size: 16px; font-weight: 700; color: var(--text, #e2e8f0);
  margin: 24px 0 12px; padding-left: 10px;
  border-left: 3px solid var(--accent, #06b6d4);
}
.markdown-body h1 {
  font-size: 20px; font-weight: 700; margin: 28px 0 14px;
  border-bottom: 2px solid rgba(248,113,113,0.3); padding-bottom: 10px;
}
.markdown-body p { margin: 12px 0; }
.markdown-body ul, .markdown-body ol { padding-left: 20px; margin: 10px 0; }
.markdown-body li { margin: 6px 0; line-height: 1.8; }
.markdown-body b { color: #fbbf24; font-weight: 700; }
.markdown-body strong { color: #60a5fa; font-weight: 700; }
.markdown-body em { color: #fbbf24; }
.markdown-body code { padding: 2px 6px; border-radius: 4px; background: rgba(148,163,184,0.08); font-size: 12px; font-family: monospace; }
.markdown-body pre { padding: 12px; border-radius: 8px; background: rgba(0,0,0,0.3); overflow-x: auto; margin: 12px 0; max-width: 100%; }
.markdown-body pre code { background: transparent; padding: 0; }
.markdown-body table { border-collapse: collapse; width: 100%; margin: 14px 0; display: block; overflow-x: auto; }
.markdown-body th, .markdown-body td { padding: 8px 10px; border: 1px solid rgba(255,255,255,0.08); text-align: left; font-size: 13px; }
.markdown-body th { background: rgba(255,255,255,0.06); font-weight: 700; color: #e2e8f0; }
.markdown-body blockquote { border-left: 3px solid #60a5fa; padding-left: 12px; margin: 12px 0; color: var(--text-muted, #94a3b8); }
.markdown-body hr { border: none; border-top: 2px solid rgba(255,255,255,0.1); margin: 24px 0; }

/* ── A股惯例：涨红跌绿 ── */
.markdown-body .up { color: #f87171; font-weight: 700; }
.markdown-body .down { color: #4ade80; font-weight: 700; }
.markdown-body .limit-up {
  color: #fff; font-weight: 700;
  padding: 2px 8px; border-radius: 4px;
  background: rgba(248,113,113,0.25); border: 1px solid rgba(248,113,113,0.4);
}
.markdown-body .limit-down {
  color: #fff; font-weight: 700;
  padding: 2px 8px; border-radius: 4px;
  background: rgba(74,222,128,0.25); border: 1px solid rgba(74,222,128,0.4);
}

/* ── 股票名醒目：加粗+金色+大字号 ── */
.markdown-body .stock {
  color: #fbbf24; font-weight: 800; font-size: 1.05em;
  padding: 1px 2px; border-radius: 2px;
}

/* ── 板块名称：蓝色+加粗 ── */
.markdown-body .sector { color: #60a5fa; font-weight: 700; }

/* ── 关键数字/金额 ── */
.markdown-body .highlight {
  color: #fde047; font-weight: 700;
  background: rgba(253,224,71,0.12); padding: 1px 6px; border-radius: 3px;
}

/* ── 资金流向：涨红跌绿 ── */
.markdown-body .inflow { color: #f87171; font-weight: 700; }
.markdown-body .outflow { color: #4ade80; font-weight: 700; }

/* ── 利好/利空：卡片式 ── */
.markdown-body .alert-good {
  padding: 14px 18px; border-radius: 10px;
  background: rgba(248,113,113,0.08); border-left: 3px solid #f87171;
  margin: 16px 0; line-height: 1.7;
}
.markdown-body .alert-good b { color: #f87171; }
.markdown-body .alert-bad {
  padding: 14px 18px; border-radius: 10px;
  background: rgba(74,222,128,0.08); border-left: 3px solid #4ade80;
  margin: 16px 0; line-height: 1.7;
}
.markdown-body .alert-bad b { color: #4ade80; }

/* ── 风险提示 ── */
.markdown-body .risk-box {
  padding: 14px 18px; border-radius: 10px;
  background: rgba(251,191,36,0.06); border-left: 3px solid #fbbf24;
  margin: 16px 0; line-height: 1.7;
}
.markdown-body .risk-box b { color: #fbbf24; }
.markdown-body .risk-box ul { margin: 8px 0 0; }
.markdown-body .risk-box li { color: #94a3b8; }

/* ── 主题标签 ── */
.markdown-body .tag {
  display: inline-block; padding: 3px 10px; border-radius: 14px;
  background: rgba(6,182,212,0.12); color: #06b6d4;
  font-size: 12px; font-weight: 600; margin: 2px 4px 4px 0;
}

/* ── 列表内股票条目间距 ── */
.markdown-body ul li { margin: 8px 0; }

/* ── Result filters & content — mobile safe ── */
.result-filters { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.result-content { margin-top: 16px; overflow-x: hidden; }
.result-hint { text-align: center; padding: 40px; color: var(--text-muted, #94a3b8); font-size: 13px; }

/* ── Mobile: task results ── */
@media (max-width: 640px) {
  .markdown-body { font-size: 14px; line-height: 1.8; }
  .markdown-body h2 { font-size: 16px; margin: 20px 0 10px; }
  .markdown-body h3 { font-size: 15px; margin: 16px 0 8px; }
  .markdown-body p { margin: 10px 0; }
  .markdown-body table { font-size: 12px; }
  .markdown-body th, .markdown-body td { padding: 5px 6px; }
  .markdown-body .alert-good, .markdown-body .alert-bad, .markdown-body .risk-box { padding: 10px 12px; }
  .result-filters { flex-direction: column; align-items: stretch; }
  .date-input { width: 100%; }
  .job-select { min-width: 0; width: 100%; }
}
</style>