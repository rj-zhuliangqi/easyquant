<script setup>
import { computed, ref, watch, nextTick } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime } from "../lib/formatters";
import { useResponsive } from "../composables/useResponsive";

defineOptions({ name: "alerts" });

const { isMobileLayout } = useResponsive();

const signalType = ref("all");
const strength = ref("all");
const timeWindow = ref("today");
const selectedIndex = ref(0);
const summary = ref({});
const feed = ref({ items: [], updated_at: null });
const listLoading = ref(true);
const listFetching = ref(false);
const listError = ref(null);
let requestSeq = 0;
const detailPanel = ref(null);

const bootstrapQuery = useQuery({
  queryKey: pageQueryKey("alerts"),
  queryFn: () => fetchJson("/api/page/alerts"),
});

function applyBootstrap(payload) {
  if (!payload) return;
  summary.value = payload.summary || {};
  feed.value = payload.feed || { items: [], updated_at: null };
  listLoading.value = false;
}

const watchActionMessage = ref("");
function extractCodeFromName(name) {
  // 个股 subject_name 可能是 "600900 长江电力" 或纯名称；尽量提取 6 位数字代码
  const m = String(name || "").match(/\b(\d{6})\b/);
  return m ? m[1] : "";
}
async function watchStockFromAlert(alert) {
  const subjectName = String(alert.subject_name || "");
  const code = alert.stock_code || extractCodeFromName(subjectName);
  if (!code) {
    watchActionMessage.value = `未提取到代码：${subjectName}`;
    return;
  }
  watchActionMessage.value = "加入中…";
  try {
    const current = await fetchJson("/api/workspace");
    const stocks = current.watched_stocks || [];
    if (stocks.some((s) => s.stock_code === code)) {
      watchActionMessage.value = `已在观察列表：${code}`;
      return;
    }
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: current.watched_sectors || [],
        watched_stocks: [...stocks, { stock_code: code, stock_name: subjectName.replace(/\b\d{6}\b\s*/, "").trim() || code }],
      }),
    });
    watchActionMessage.value = `✅ 已加入观察：${code}`;
  } catch (error) {
    watchActionMessage.value = `加入失败：${error.message || error}`;
  }
}
async function watchSectorFromAlert(alert) {
  const sectorType = alert.sector_type || (alert.subject_type === "sector" ? "industry" : "industry");
  const sectorName = alert.sector_name || alert.subject_name;
  if (!sectorName) {
    watchActionMessage.value = "未取到板块名";
    return;
  }
  watchActionMessage.value = "加入中…";
  try {
    const current = await fetchJson("/api/workspace");
    const sectors = current.watched_sectors || [];
    if (sectors.some((s) => s.sector_name === sectorName)) {
      watchActionMessage.value = `已在观察列表：${sectorName}`;
      return;
    }
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: [...sectors, { sector_type: sectorType, sector_name: sectorName }],
        watched_stocks: current.watched_stocks || [],
      }),
    });
    watchActionMessage.value = `✅ 已加入观察：${sectorName}`;
  } catch (error) {
    watchActionMessage.value = `加入失败：${error.message || error}`;
  }
}

async function refreshAlerts() {
  const seq = ++requestSeq;
  listFetching.value = true;
  listError.value = null;
  try {
    const [nextSummary, nextFeed] = await Promise.all([
      fetchJson("/api/alerts/summary"),
      fetchJson(
        `/api/alerts/feed?signal_type=${encodeURIComponent(signalType.value)}&strength=${encodeURIComponent(strength.value)}&time_window=${encodeURIComponent(timeWindow.value)}&limit=20`,
      ),
    ]);
    // P2-5: 快速切筛选时旧响应可能晚到，序号不匹配则丢弃
    if (seq !== requestSeq) return;
    summary.value = nextSummary;
    feed.value = nextFeed;
  } catch (error) {
    if (seq === requestSeq) listError.value = error.message || String(error);
  } finally {
    if (seq === requestSeq) {
      listLoading.value = false;
      listFetching.value = false;
    }
  }
}

watch(
  () => bootstrapQuery.data.value?.payload,
  (payload) => {
    applyBootstrap(payload);
  },
  { immediate: true },
);

watch([signalType, strength, timeWindow], async () => {
  selectedIndex.value = 0;
  await refreshAlerts();
});

// On mobile, scroll to detail panel when selection changes
watch(selectedIndex, async () => {
  if (isMobileLayout.value && detailPanel.value) {
    await nextTick();
    detailPanel.value.$el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

const items = computed(() => feed.value.items || []);
const activeAlert = computed(() => items.value[selectedIndex.value] || null);
const queryUpdatedAt = computed(() => formatDateTime(feed.value.updated_at || bootstrapQuery.data.value?.updated_at));
const queryLoading = computed(() => bootstrapQuery.isLoading.value && listLoading.value);
const queryFetching = computed(() => bootstrapQuery.isFetching.value || listFetching.value);
const queryError = computed(() => bootstrapQuery.isError.value || !!listError.value);
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">盘中信号</p>
        <h2>预警中心</h2>
        <p class="hero-copy">实时监控市场、板块、个股异动信号，按强度与时间窗筛选。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :is-error="queryError" :updated-at="queryUpdatedAt" @retry="refreshAlerts" />
    </header>

    <section class="filter-grid">
      <label>
        <span>信号类型</span>
        <select v-model="signalType">
          <option value="all">全部</option>
          <option value="market">市场</option>
          <option value="sector">板块</option>
          <option value="limit_up">连板</option>
          <option value="stock">个股</option>
        </select>
      </label>
      <label>
        <span>强度</span>
        <select v-model="strength">
          <option value="all">全部</option>
          <option value="high-priority">高优先级</option>
          <option value="confirmed">仅确认信号</option>
        </select>
      </label>
      <label>
        <span>时间窗</span>
        <select v-model="timeWindow">
          <option value="today">今日</option>
          <option value="30m">近 30 分钟</option>
          <option value="15m">近 15 分钟</option>
          <option value="5m">近 5 分钟</option>
        </select>
      </label>
    </section>

    <section class="card-grid three-up">
      <MetricCard label="预警总数" :value="summary.total ?? 0" :loading="queryLoading" />
      <MetricCard label="高优先级" :value="summary.high_priority_count ?? 0" :loading="queryLoading" trend="neutral" />
      <MetricCard label="顶部信号" :value="summary.top_signal?.subject_name || '--'" :loading="queryLoading" />
    </section>

    <section class="card-grid two-up">
      <DataPanel title="预警时间流">
        <div class="list-stack">
          <button
            v-for="(item, index) in items"
            :key="`${item.title}-${index}`"
            class="list-button"
            :class="{ active: selectedIndex === index }"
            @click="selectedIndex = index"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.subject_name }} · {{ item.freshness_level }}</span>
            <small>{{ item.reason }}</small>
          </button>
          <div v-if="listError" class="list-error">
            加载失败：{{ listError }}
            <button class="inline-retry" type="button" @click="refreshAlerts">重试</button>
          </div>
          <EmptyState
            v-else-if="!items.length && !queryLoading"
            title="暂无预警"
            description="当前筛选条件下没有匹配的信号"
          />
        </div>
      </DataPanel>

      <DataPanel ref="detailPanel" title="信号详情" class="detail-panel">
        <div v-if="activeAlert" class="detail-block">
          <strong>{{ activeAlert.title }}</strong>
          <p>{{ activeAlert.reason }}</p>
          <small>{{ activeAlert.subject_name }} · {{ activeAlert.status }} · {{ activeAlert.source_label }}</small>
          <!-- P4-3: 详情补两个可执行动作 -->
          <div class="detail-actions">
            <RouterLink
              v-if="activeAlert.sector_name || activeAlert.subject_type === 'sector'"
              class="action-link"
              :to="{ path: '/sector-monitor', query: { sector: activeAlert.sector_name || activeAlert.subject_name } }"
            >查看板块</RouterLink>
            <button
              v-if="activeAlert.subject_type === 'stock' && activeAlert.subject_name"
              class="action-btn"
              type="button"
              @click="watchStockFromAlert(activeAlert)"
            >＋ 加入观察</button>
            <button
              v-else-if="(activeAlert.sector_name || activeAlert.subject_type === 'sector') && activeAlert.subject_name"
              class="action-btn"
              type="button"
              @click="watchSectorFromAlert(activeAlert)"
            >＋ 加入观察</button>
          </div>
          <small v-if="watchActionMessage" class="watch-action-msg">{{ watchActionMessage }}</small>
        </div>
        <EmptyState
          v-else
          title="暂无预警"
          description="当前筛选条件下没有匹配的信号"
        />
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
@media (max-width: 640px) {
  .detail-panel {
    border-top: 2px solid var(--border-hover);
  }
}
/* P4-3: 详情区动作按钮 */
.detail-actions { display: flex; gap: 12px; margin-top: 8px; align-items: center; flex-wrap: wrap; }
.action-link {
  font-size: 12px; color: var(--accent, #06b6d4); text-decoration: none;
  padding: 4px 10px; border: 1px solid rgba(6,182,212,0.3); border-radius: 6px;
}
.action-link:hover { background: rgba(6,182,212,0.1); }
.action-btn {
  font-size: 12px; padding: 4px 10px; border-radius: 6px; border: none;
  background: var(--accent, #06b6d4); color: #fff; cursor: pointer; font-weight: 600;
}
.action-btn:hover { opacity: 0.9; }
.watch-action-msg { display: block; margin-top: 6px; color: var(--text-muted, #94a3b8); }
.list-error { padding: 10px; color: var(--danger, #ef4444); font-size: 13px; }
.inline-retry { margin-left: 8px; padding: 2px 10px; border-radius: 4px; border: 1px solid var(--border, rgba(255,255,255,0.1)); background: transparent; color: var(--text, #e2e8f0); cursor: pointer; }
</style>
