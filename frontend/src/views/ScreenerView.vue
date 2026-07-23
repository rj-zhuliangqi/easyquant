<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import EmptyState from "../components/ui/EmptyState.vue";
import StatusBadge from "../components/ui/StatusBadge.vue";
import QueryState from "../components/QueryState.vue";
import StrategyGallery from "../components/screener/StrategyGallery.vue";
import ConditionBuilder from "../components/screener/ConditionBuilder.vue";
import ResultTable from "../components/screener/ResultTable.vue";
import StockDrawer from "../components/screener/StockDrawer.vue";
import { fetchJson, fetchScreenerStrategies, runScreener, runScreenerBacktest, deleteScreenerPreset } from "../lib/api";

defineOptions({ name: "screener" });
const queryClient = useQueryClient();

// ---------- 指标注册表 ----------
const indicatorsQuery = useQuery({
  queryKey: ["screener-indicators"],
  queryFn: () => fetchJson("/api/screener/indicators"),
  staleTime: 10 * 60 * 1000,
});
const indicatorGroups = computed(() => indicatorsQuery.data.value?.groups || []);

// ---------- 策略库（含 5 日命中历史） ----------
const strategiesQuery = useQuery({
  queryKey: ["screener-strategies"],
  queryFn: fetchScreenerStrategies,
  staleTime: 60 * 1000,
});
const strategies = computed(() => strategiesQuery.data.value || []);

// ---------- 预设（我的预设 tab） ----------
const presetsQuery = useQuery({
  queryKey: ["screener-presets"],
  queryFn: () => fetchJson("/api/screener/presets"),
  staleTime: 60 * 1000,
});
const customPresets = computed(() => (presetsQuery.data.value || []).filter((p) => !p.is_builtin));

// ---------- 状态 / 回补 ----------
const statusQuery = useQuery({
  queryKey: ["screener-status"],
  queryFn: () => fetchJson("/api/screener/status"),
  refetchInterval: 5000,
  staleTime: 3000,
});
const coverage = computed(() => statusQuery.data.value?.coverage || {});
const cache = computed(() => statusQuery.data.value?.cache || {});
const source = computed(() => statusQuery.data.value?.source || {});
const progress = computed(() => statusQuery.data.value?.progress || {});

const isBackfilling = computed(() => progress.value?.running === true);
const backfillMessage = computed(() => progress.value?.message || "");
const backfillProgressPct = computed(() => {
  const total = progress.value?.total || 0;
  const done = progress.value?.done || 0;
  if (!total) return 0;
  return Math.min(100, Math.round((done / total) * 100));
});

const backfillInFlight = ref(false);
const backfillError = ref("");
async function triggerBackfill(codeLimit = null) {
  backfillInFlight.value = true;
  backfillError.value = "";
  try {
    const body = codeLimit != null ? { code_limit: codeLimit } : {};
    const res = await fetchJson("/api/screener/backfill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res?.already_running) backfillError.value = "已有回补任务在运行";
    queryClient.invalidateQueries({ queryKey: ["screener-status"] });
  } catch (e) {
    backfillError.value = e.message || String(e);
  } finally {
    backfillInFlight.value = false;
  }
}

// ---------- 回测（P1-4 信号统计法 T+N 胜率）----------
const backtestInFlight = ref(false);
async function triggerBacktest() {
  if (!activeStrategyId.value) return;
  backtestInFlight.value = true;
  try {
    await runScreenerBacktest({ preset_id: activeStrategyId.value, days: 30 });
    // 后台 daemon 线程跑（30日×run 约 1-2 分钟），延迟刷新 strategies 拉 win_rates
    setTimeout(() => queryClient.invalidateQueries({ queryKey: ["screener-strategies"] }), 6000);
  } catch (e) {
    alert(`回测失败：${e.message || e}`);
  } finally {
    backtestInFlight.value = false;
  }
}

// ---------- Tab ----------
const TABS = [
  { key: "gallery", label: "策略库" },
  { key: "builder", label: "自由构建" },
  { key: "mine", label: "我的预设" },
];
const activeTab = ref("gallery");

// ---------- 运行槽（每个 tab 独立结果，共享 selectedCode / watchMessages） ----------
function makeRunSlot() {
  const result = ref(null);
  const error = ref("");
  const running = ref(false);
  let seq = 0;
  async function run(payload) {
    const s = ++seq;
    running.value = true;
    error.value = "";
    result.value = null;
    try {
      const res = await runScreener(payload);
      if (s !== seq) return;
      result.value = res;
    } catch (e) {
      if (s === seq) error.value = e.message || String(e);
    } finally {
      if (s === seq) running.value = false;
    }
  }
  return { result, error, running, run };
}
const gallerySlot = makeRunSlot();
const builderSlot = makeRunSlot();
const mineSlot = makeRunSlot();

const activeStrategyId = ref(null);
const activePresetId = ref(null);
const builderSeed = ref(null);

function selectStrategy(s) {
  activeStrategyId.value = s.id;
  gallerySlot.run({ preset_id: s.id, limit: 100 });
}
function runCustom(payload) {
  builderSlot.run(payload);
}
const tdxFormula = ref("");
function runTdx() {
  if (!tdxFormula.value.trim()) return;
  builderSlot.run({ tdx: tdxFormula.value, limit: 100 });
}
const multifactorResult = ref(null);
const multifactorLoading = ref(false);
async function fetchMultifactor() {
  multifactorLoading.value = true;
  try {
    multifactorResult.value = await fetchJson("/api/screener/multifactor?topn=20");
  } catch (e) {
    alert(`多因子打分失败：${e.message || e}`);
  } finally {
    multifactorLoading.value = false;
  }
}
function runPreset(p) {
  activePresetId.value = p.id;
  mineSlot.run({ preset_id: p.id, limit: 100 });
}
async function cloneToBuilder(p) {
  try {
    const row = await fetchJson(`/api/screener/presets/${p.id}`);
    builderSeed.value = null; // 先清空再赋值，确保 ConditionBuilder 的 watch 触发
    await Promise.resolve();
    builderSeed.value = row;
    activeTab.value = "builder";
  } catch (e) {
    alert(`克隆失败：${e.message || e}`);
  }
}
async function removePreset(p) {
  if (!confirm(`删除预设「${p.name}」？`)) return;
  try {
    await deleteScreenerPreset(p.id);
    queryClient.invalidateQueries({ queryKey: ["screener-presets"] });
    queryClient.invalidateQueries({ queryKey: ["screener-strategies"] });
  } catch (e) {
    alert(`删除失败：${e.message || e}`);
  }
}
function onPresetSaved() {
  queryClient.invalidateQueries({ queryKey: ["screener-presets"] });
  queryClient.invalidateQueries({ queryKey: ["screener-strategies"] });
}

// ---------- 加自选 ----------
const watchMessages = ref({});
async function addToWatch(item) {
  try {
    const current = await fetchJson("/api/workspace");
    const stocks = current.watched_stocks || [];
    if (stocks.some((s) => s.stock_code === item.code)) {
      watchMessages.value[item.code] = `已在观察列表：${item.code}`;
      return;
    }
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: current.watched_sectors || [],
        watched_stocks: [...stocks, { stock_code: item.code, stock_name: item.name || item.code }],
      }),
    });
    watchMessages.value[item.code] = `✅ 已加入观察：${item.code}`;
  } catch (e) {
    watchMessages.value[item.code] = `加入失败：${e.message || e}`;
  }
}

// ---------- Stock Drawer ----------
const selectedCode = ref("");
function openStock(code) { selectedCode.value = code; }
function closeStock() { selectedCode.value = ""; }

// ---------- 默认载入：进来就跑第一个策略，立刻有结果 ----------
onMounted(async () => {
  await strategiesQuery.refetch();
  if (strategies.value.length) selectStrategy(strategies.value[0]);
});
onUnmounted(() => { /* slots 自带 seq 守卫，无需额外清理 */ });

// ---------- 展示辅助 ----------
const hasData = computed(() => (coverage.value?.stock_count || 0) > 0);
const isStale = computed(() => cache.value?.is_stale === true);
const coveragePctText = computed(() => {
  const pct = coverage.value?.coverage_pct;
  if (pct == null) return "-";
  return `${pct.toFixed(1)}%`;
});
const cacheAgeText = computed(() => {
  const m = cache.value?.cache_age_minutes;
  if (m == null) return "无缓存";
  if (m < 60) return `${m} 分钟前`;
  if (m < 24 * 60) return `${Math.floor(m / 60)} 小时前`;
  return `${Math.floor(m / (24 * 60))} 天前`;
});
const sourceLabelText = computed(() => {
  const label = source.value?.fund_flow || "akshare";
  const fallback = source.value?.fallback_used;
  if (label === "eastmoney") return "东方财富";
  if (label === "akshare") return fallback ? "东方财富(回落)" : "AKShare";
  if (label === "cache") return "本地缓存";
  return label;
});
const sourceStatus = computed(() => {
  if (source.value?.fallback_used) return "warning";
  if (source.value?.fund_flow === "eastmoney") return "info";
  return "success";
});

function slotView(slot) {
  const r = slot.result.value;
  return {
    results: r?.results || [],
    warnings: r?.warnings || [],
    total: r?.total || 0,
    dataDate: r?.data_date || coverage.value?.latest_date || "",
    showScore: (r?.results || []).some((x) => x.score != null),
    loading: slot.running.value,
  };
}
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">选股</p>
        <h2>选股器</h2>
        <p class="hero-copy">多因子筛选 · 8 套内置策略（量价 / 趋势 / 事件驱动）· 评分模式容忍数据缺失 · 策略命中历史可追溯</p>
      </div>
      <QueryState
        :is-loading="indicatorsQuery.isLoading.value"
        :is-fetching="statusQuery.isFetching.value"
        :updated-at="coverage.latest_date ? `数据日期 ${coverage.latest_date}` : ''"
      />
    </header>

    <!-- 数据状态条 -->
    <section class="status-bar">
      <div class="metric-cell">
        <span class="metric-label">覆盖股票</span>
        <strong>{{ coverage.stock_count ?? 0 }}</strong>
        <span class="metric-hint" v-if="coverage.universe_size">/ {{ coverage.universe_size }} universe</span>
      </div>
      <div class="metric-cell">
        <span class="metric-label">日线最新</span>
        <strong>{{ coverage.latest_date || "--" }}</strong>
        <span class="metric-hint">{{ cacheAgeText }}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-label">资金流</span>
        <strong>{{ coverage.flow_stock_count ?? 0 }}</strong>
        <span class="metric-hint">最新 {{ coverage.flow_latest_date || "--" }}</span>
      </div>
      <div class="metric-cell">
        <span class="metric-label">覆盖率</span>
        <strong>{{ coveragePctText }}</strong>
        <span class="metric-hint">bar / flow</span>
      </div>
      <div class="status-source">
        <StatusBadge :status="sourceStatus" size="sm">数据源 {{ sourceLabelText }}</StatusBadge>
      </div>
      <div class="status-actions">
        <button class="btn btn-primary" type="button" :disabled="backfillInFlight || isBackfilling" @click="triggerBackfill()">
          {{ isBackfilling ? "回补中…" : "更新数据" }}
        </button>
        <button class="btn btn-ghost" type="button" :disabled="backfillInFlight || isBackfilling" title="仅前 500 只（成交额 Top），用于冒烟" @click="triggerBackfill(500)">
          冒烟回补
        </button>
      </div>
    </section>

    <div v-if="isStale && hasData" class="stale-banner">
      ⚠ 缓存已陈旧（{{ cacheAgeText }}），点击右上「更新数据」拉取最新行情
    </div>

    <!-- 回补进度 -->
    <section v-if="isBackfilling || backfillMessage" class="backfill-progress">
      <div class="progress-info">
        <span class="progress-stage" :data-stage="progress.stage">{{ progress.stage || "idle" }}</span>
        <span class="progress-msg">{{ backfillMessage || "回补中…" }}</span>
        <span v-if="progress.total" class="progress-counts">{{ progress.done }} / {{ progress.total }}（{{ backfillProgressPct }}%）</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :data-stage="progress.stage" :style="{ width: backfillProgressPct + '%' }"></div>
      </div>
      <div v-if="progress.failed?.length" class="progress-failed">
        失败 {{ progress.failed.length }} 只
        <span class="breakdown" v-if="progress.failure_breakdown && Object.keys(progress.failure_breakdown).length">
          （<span v-for="(count, cat) in progress.failure_breakdown" :key="cat" class="bd-pill" :data-cat="cat">{{ cat }}:{{ count }}</span>）
        </span>
        <details v-if="progress.failed?.length <= 30" class="failed-list">
          <summary>看具体哪些股票</summary>
          <ul>
            <li v-for="(f, idx) in progress.failed" :key="idx">
              <code>{{ f.code }}</code>
              <span v-if="f.stage" class="stage-tag">{{ f.stage }}</span>
              <span v-if="f.category" class="cat-tag" :data-cat="f.category">{{ f.category }}</span>
              <span v-if="f.error" class="err-msg">{{ f.error }}</span>
            </li>
          </ul>
        </details>
        <span v-else class="muted">(失败超过 30 只，仅显示总数)</span>
      </div>
    </section>

    <p v-if="backfillError" class="inline-error">{{ backfillError }}</p>

    <EmptyState
      v-if="!hasData && !isBackfilling"
      title="尚无日线数据"
      description="选股器依赖本地日线库。点击「更新数据」开始首次回补（约 60-90 分钟），或用「冒烟回补」先试跑前 500 只。"
    />

    <template v-if="hasData || isBackfilling">
      <!-- Tab 条 -->
      <nav class="tab-bar">
        <button
          v-for="t in TABS"
          :key="t.key"
          class="tab-btn"
          :class="{ active: activeTab === t.key }"
          type="button"
          @click="activeTab = t.key"
        >{{ t.label }}</button>
      </nav>

      <!-- Tab 1: 策略库（master-detail） -->
      <section v-show="activeTab === 'gallery'" class="gallery-layout">
        <aside class="gallery-pane">
          <StrategyGallery
            :strategies="strategies"
            :active-id="activeStrategyId"
            @select="selectStrategy"
          />
        </aside>
        <div class="detail-pane">
          <div class="detail-toolbar">
            <button class="tb-btn" type="button" :disabled="!activeStrategyId || backtestInFlight" @click="triggerBacktest">
              {{ backtestInFlight ? "回测中…" : "刷新 T+N 胜率" }}
            </button>
            <span class="tb-hint">对最近 30 日执行策略，统计 T+1/3/5/10/20 胜率（后台跑，约 1-2 分钟后刷新）</span>
          </div>
          <p v-if="gallerySlot.error.value" class="inline-error">筛选失败：{{ gallerySlot.error.value }}</p>
          <ResultTable
            v-bind="slotView(gallerySlot)"
            :watch-messages="watchMessages"
            @select-stock="openStock"
            @add-watch="addToWatch"
          />
        </div>
      </section>

      <!-- Tab 2: 自由构建 -->
      <section v-show="activeTab === 'builder'" class="builder-layout">
        <div class="tdx-box">
          <div class="tdx-head">
            <span class="tdx-title">📐 通达信公式选股</span>
            <span class="tdx-hint">粘贴公式直接选股：C/O/H/L/V/CHANGE_PCT + REF/MA/CROSS/BARSLAST/COUNT/BETWEEN</span>
          </div>
          <textarea v-model="tdxFormula" class="tdx-input" rows="3" placeholder="T:=BARSLAST(CHANGE_PCT>=9.8); XG:T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92;"></textarea>
          <div class="tdx-actions">
            <button class="tb-btn" type="button" :disabled="!tdxFormula.trim() || builderSlot.running.value" @click="runTdx">
              {{ builderSlot.running.value ? "运行中…" : "运行公式" }}
            </button>
            <button class="tb-btn" type="button" :disabled="multifactorLoading" @click="fetchMultifactor" style="margin-left:auto">
              {{ multifactorLoading ? "计算中…" : "多因子 TopN" }}
            </button>
          </div>
          <div v-if="multifactorResult?.results?.length" class="mf-box">
            <table class="mf-table">
              <thead><tr><th>代码</th><th>得分</th><th v-for="f in multifactorResult.factors" :key="f">{{ f }}</th></tr></thead>
              <tbody>
                <tr v-for="r in multifactorResult.results" :key="r.stock_code" @click="openStock(r.stock_code)">
                  <td>{{ r.stock_code }}</td><td class="mf-score">{{ r.score }}</td>
                  <td v-for="f in multifactorResult.factors" :key="f">{{ r[f] ?? "-" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <ConditionBuilder
          :indicator-groups="indicatorGroups"
          :has-data="hasData"
          :running="builderSlot.running.value"
          :seed="builderSeed"
          @run="runCustom"
          @saved="onPresetSaved"
        />
        <p v-if="builderSlot.error.value" class="inline-error">筛选失败：{{ builderSlot.error.value }}</p>
        <ResultTable
          v-if="builderSlot.result.value || builderSlot.running.value"
          v-bind="slotView(builderSlot)"
          :watch-messages="watchMessages"
          @select-stock="openStock"
          @add-watch="addToWatch"
        />
        <EmptyState
          v-else
          title="搭建条件后点「开始筛选」"
          description="添加指标条件、选择匹配模式（评分模式可设权重与最低分），即可筛选全市场。"
        />
      </section>

      <!-- Tab 3: 我的预设 -->
      <section v-show="activeTab === 'mine'" class="mine-layout">
        <div class="mine-head">
          <h3>我的预设</h3>
          <p class="mine-hint">从「策略库」或「自由构建」克隆而来。点击运行，或克隆到自由构建继续编辑。</p>
        </div>
        <div v-if="customPresets.length" class="mine-grid">
          <div v-for="p in customPresets" :key="p.id" class="mine-card">
            <div class="mc-head">
              <span class="mc-name">{{ p.name }}</span>
              <StatusBadge v-if="p.match_mode === 'score'" status="info" size="sm">评分≥{{ p.min_score }}</StatusBadge>
            </div>
            <p class="mc-desc">{{ p.description || "（无说明）" }}</p>
            <div class="mc-meta">{{ (p.conditions || []).length }} 条 · {{ p.match_mode === "score" ? "评分" : p.match_mode === "any" ? "任一" : "全满足" }}</div>
            <div class="mc-actions">
              <button class="btn btn-primary btn-sm" type="button" @click="runPreset(p)">运行</button>
              <button class="btn btn-ghost btn-sm" type="button" @click="cloneToBuilder(p)">克隆编辑</button>
              <button class="btn btn-ghost btn-sm mc-del" type="button" @click="removePreset(p)">删除</button>
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="还没有自定义预设"
          description="去「策略库」克隆一个内置策略，或在「自由构建」里搭好条件后点「保存为预设」。"
        />
        <p v-if="mineSlot.error.value" class="inline-error">筛选失败：{{ mineSlot.error.value }}</p>
        <ResultTable
          v-if="mineSlot.result.value || mineSlot.running.value"
          v-bind="slotView(mineSlot)"
          :watch-messages="watchMessages"
          @select-stock="openStock"
          @add-watch="addToWatch"
        />
      </section>
    </template>

    <!-- 个股抽屉 -->
    <StockDrawer :code="selectedCode" @close="closeStock" />
  </section>
</template>

<style scoped>
/* ---------- 状态条 / metric cards ---------- */
.status-bar {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch;
  padding: 14px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 12px;
}
.metric-cell {
  display: flex; flex-direction: column; gap: 2px;
  min-width: 110px; padding: 8px 14px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
}
.metric-label { font-size: 11px; color: var(--text-muted, #94a3b8); text-transform: uppercase; letter-spacing: 0.04em; }
.metric-cell strong { font-size: 18px; font-weight: 700; color: var(--text, #e2e8f0); font-variant-numeric: tabular-nums; }
.metric-hint { font-size: 11px; color: var(--text-muted, #94a3b8); }
.status-source { display: flex; align-items: center; margin-left: auto; }
.status-actions { display: flex; gap: 8px; align-items: center; }

.stale-banner {
  padding: 10px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 8px;
  font-size: 13px; color: #fbbf24;
  margin-bottom: 12px;
}

/* ---------- 回补进度 ---------- */
.backfill-progress {
  padding: 12px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 12px;
}
.progress-info { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 8px; flex-wrap: wrap; align-items: center; }
.progress-stage { padding: 2px 10px; border-radius: 999px; font-weight: 600; background: rgba(56, 189, 248, 0.15); color: #38bdf8; text-transform: uppercase; font-size: 10px; letter-spacing: 0.06em; }
.progress-stage[data-stage="bars"] { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }
.progress-stage[data-stage="fund_flow"] { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.progress-stage[data-stage="done"] { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.progress-stage[data-stage="error"] { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.progress-bar { height: 6px; background: rgba(255, 255, 255, 0.06); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #38bdf8, #0ea5e9); transition: width 0.3s; }
.progress-fill[data-stage="fund_flow"] { background: linear-gradient(90deg, #c084fc, #a855f7); }
.progress-fill[data-stage="done"] { background: linear-gradient(90deg, #4ade80, #22c55e); }
.progress-fill[data-stage="error"] { background: linear-gradient(90deg, #f87171, #ef4444); }
.progress-failed { font-size: 11px; color: var(--danger, #f87171); margin-top: 6px; }
.progress-failed .breakdown { margin-left: 6px; }
.progress-failed .bd-pill { display: inline-block; padding: 1px 6px; margin: 0 3px; border-radius: 999px; background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.4); font-size: 10px; font-family: var(--mono, monospace); }
.progress-failed .failed-list { margin-top: 6px; }
.progress-failed .failed-list summary { cursor: pointer; user-select: none; color: var(--text-muted, #94a3b8); }
.progress-failed .failed-list ul { list-style: none; padding: 6px 0 0 0; max-height: 160px; overflow-y: auto; margin: 0; }
.progress-failed .failed-list li { display: flex; align-items: center; gap: 6px; padding: 2px 0; font-size: 11px; }
.progress-failed .failed-list code { color: var(--text, #e2e8f0); min-width: 56px; }
.progress-failed .failed-list .stage-tag { padding: 1px 5px; background: rgba(148,163,184,0.15); border-radius: 4px; color: var(--text-muted, #94a3b8); }
.progress-failed .failed-list .cat-tag { padding: 1px 5px; border-radius: 4px; font-size: 10px; font-family: var(--mono, monospace); }
.progress-failed .failed-list .cat-tag[data-cat="network"] { background: rgba(248,113,113,0.2); color: #fca5a5; }
.progress-failed .failed-list .cat-tag[data-cat="proxy"] { background: rgba(251,191,36,0.2); color: #fde68a; }
.progress-failed .failed-list .cat-tag[data-cat="parse"] { background: rgba(167,139,250,0.2); color: #c4b5fd; }
.progress-failed .failed-list .cat-tag[data-cat="empty"] { background: rgba(148,163,184,0.2); color: #cbd5e1; }
.progress-failed .failed-list .err-msg { color: var(--text-muted, #94a3b8); font-family: var(--mono, monospace); font-size: 10px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-failed .muted { color: var(--text-muted, #94a3b8); margin-left: 6px; }

.inline-error { color: var(--danger, #f87171); font-size: 13px; padding: 8px 0; margin: 0 0 8px; }

/* ---------- Tab 条 ---------- */
.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.08)); margin-bottom: 16px; }
.tab-btn { font: inherit; font-size: 14px; padding: 10px 18px; background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-muted, #94a3b8); cursor: pointer; transition: color 0.15s, border-color 0.15s; }
.tab-btn:hover { color: var(--text, #e2e8f0); }
.tab-btn.active { color: var(--accent, #06b6d4); border-bottom-color: var(--accent, #06b6d4); }

/* ---------- 策略库 master-detail ---------- */
.gallery-layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; align-items: start; }
.gallery-pane { position: sticky; top: 12px; max-height: calc(100vh - 140px); overflow-y: auto; }
.detail-pane { min-width: 0; }
.detail-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.tb-btn {
  font: inherit; font-size: 12px; cursor: pointer;
  padding: 5px 12px; border-radius: 6px;
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(6, 182, 212, 0.4);
  color: var(--accent, #06b6d4);
}
.tb-btn:hover:not(:disabled) { background: rgba(6, 182, 212, 0.2); }
.tb-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.tb-hint { font-size: 11px; color: var(--text-muted, #64748b); }
.tdx-box { margin-bottom: 14px; padding: 12px; background: rgba(6, 182, 212, 0.04); border: 1px solid rgba(6, 182, 212, 0.15); border-radius: 10px; }
.tdx-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.tdx-title { font-size: 13px; font-weight: 600; color: var(--accent, #06b6d4); }
.tdx-input { width: 100%; font: inherit; font-size: 12px; font-family: ui-monospace, monospace; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--border, rgba(255,255,255,0.1)); color: var(--text, #e2e8f0); resize: vertical; box-sizing: border-box; }
.tdx-input:focus { outline: none; border-color: var(--accent, #06b6d4); }
.tdx-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.mf-box { margin-top: 10px; overflow-x: auto; }
.mf-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.mf-table th, .mf-table td { padding: 5px 8px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.06); }
.mf-table th { color: var(--text-muted, #64748b); font-weight: 600; text-align: right; }
.mf-table td:first-child, .mf-table th:first-child { text-align: left; cursor: pointer; color: var(--accent, #06b6d4); }
.mf-score { font-weight: 700; color: #4ade80; }

/* ---------- 自由构建 ---------- */
.builder-layout { display: flex; flex-direction: column; gap: 16px; }

/* ---------- 我的预设 ---------- */
.mine-head { margin-bottom: 14px; }
.mine-head h3 { margin: 0 0 4px; font-size: 16px; color: var(--text, #e2e8f0); }
.mine-hint { margin: 0; font-size: 12px; color: var(--text-muted, #94a3b8); }
.mine-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-bottom: 16px; }
.mine-card { padding: 14px; background: var(--panel-bg, rgba(15, 23, 42, 0.5)); border: 1px solid var(--border, rgba(255, 255, 255, 0.08)); border-radius: var(--radius-md, 10px); display: flex; flex-direction: column; gap: 8px; }
.mc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.mc-name { font-weight: 600; font-size: 15px; color: var(--text, #e2e8f0); }
.mc-desc { margin: 0; font-size: 12px; color: var(--text-muted, #94a3b8); min-height: 16px; }
.mc-meta { font-size: 11px; color: var(--text-muted, #64748b); }
.mc-actions { display: flex; gap: 6px; margin-top: 4px; }
.mc-del:hover { color: var(--danger, #f87171); border-color: var(--danger, #f87171); }

/* ---------- 通用按钮（与全局对齐，scoped 兜底） ---------- */
.btn { font: inherit; cursor: pointer; border-radius: 8px; transition: all 0.15s; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-ghost { background: transparent; border: 1px solid var(--border, rgba(255, 255, 255, 0.12)); color: var(--text-secondary, #cbd5e1); padding: 7px 12px; font-size: 13px; }
.btn-ghost:hover { border-color: var(--accent, #06b6d4); color: var(--accent, #06b6d4); }
.btn-primary { background: var(--accent, #06b6d4); border: 1px solid var(--accent, #06b6d4); color: #0f172a; font-weight: 600; padding: 8px 16px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 860px) {
  .gallery-layout { grid-template-columns: 1fr; }
  .gallery-pane { position: static; max-height: none; }
}
</style>
