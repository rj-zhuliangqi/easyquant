<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import StatusBadge from "../components/ui/StatusBadge.vue";
import UiSelect from "../components/ui/UiSelect.vue";
import QueryState from "../components/QueryState.vue";
import { fetchJson } from "../lib/api";
import { formatAmount, formatPercent, formatNumber } from "../lib/formatters";

defineOptions({ name: "screener" });

const queryClient = useQueryClient();

// ---------- 指标注册表 ----------
const indicatorsQuery = useQuery({
  queryKey: ["screener-indicators"],
  queryFn: () => fetchJson("/api/screener/indicators"),
  staleTime: 10 * 60 * 1000,
});
const indicatorGroups = computed(() => indicatorsQuery.data.value?.groups || []);
const indicatorByName = computed(() => {
  const map = {};
  for (const g of indicatorGroups.value) {
    for (const ind of g.indicators) map[ind.name] = ind;
  }
  return map;
});
const indicatorUiOptions = computed(() =>
  indicatorGroups.value.map((g) => ({
    label: g.name,
    options: g.indicators.map((ind) => ({
      value: ind.name,
      label: ind.label,
      hint: ind.unit === "0/1" ? "布尔" : (ind.unit || ""),
    })),
  })),
);

// ---------- 预设 ----------
const presetsQuery = useQuery({
  queryKey: ["screener-presets"],
  queryFn: () => fetchJson("/api/screener/presets"),
  staleTime: 60 * 1000,
});
const presets = computed(() => presetsQuery.data.value || []);

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
    if (res?.already_running) {
      backfillError.value = "已有回补任务在运行";
    }
    queryClient.invalidateQueries({ queryKey: ["screener-status"] });
  } catch (e) {
    backfillError.value = e.message || String(e);
  } finally {
    backfillInFlight.value = false;
  }
}

// ---------- 条件构建器 ----------
const conditions = ref([]);
const universe = ref({
  exclude_st: true,
  boards: ["main", "cyb", "kcb"],
  min_amount: 50_000_000,
});
const orderBy = ref("change_pct");
const orderDir = ref("desc");
const limit = ref(100);

const BOARD_OPTIONS = [
  { value: "main", label: "主板" },
  { value: "cyb", label: "创业板" },
  { value: "kcb", label: "科创板" },
];
const AMOUNT_TIERS = [
  { value: 50_000_000, label: "≥ 5000 万" },
  { value: 200_000_000, label: "≥ 2 亿" },
  { value: 500_000_000, label: "≥ 5 亿" },
  { value: 1_000_000_000, label: "≥ 10 亿" },
];
const AMOUNT_OPTIONS = AMOUNT_TIERS.map((t) => ({ value: t.value, label: t.label }));
const BOARD_UI_OPTIONS = [
  { label: "板块", options: BOARD_OPTIONS },
];
const AMOUNT_UI_OPTIONS = [{ label: "门槛", options: AMOUNT_OPTIONS }];
const ORDER_UI_OPTIONS = [
  { label: "方向", options: [{ value: "desc", label: "降序" }, { value: "asc", label: "升序" }] },
];
const LIMIT_UI_OPTIONS = [
  { label: "条数", options: [50, 100, 200, 500].map((v) => ({ value: v, label: `${v} 条` })) },
];

function newCondition() {
  return { indicator: "consecutive_up_days", op: ">=", value: 3 };
}
function addCondition() {
  conditions.value.push(newCondition());
}
function removeCondition(index) {
  conditions.value.splice(index, 1);
}

function isBooleanIndicator(name) {
  return indicatorByName.value[name]?.unit === "0/1";
}
function isNumericIndicator(name) {
  return !isBooleanIndicator(name);
}

const BOOLEAN_OP_OPTIONS = [{ value: "==", label: "等于" }];
const NUMERIC_OP_OPTIONS = [
  { value: ">=", label: "≥" },
  { value: ">", label: ">" },
  { value: "<=", label: "≤" },
  { value: "<", label: "<" },
  { value: "==", label: "=" },
  { value: "!=", label: "≠" },
  { value: "between", label: "区间" },
];

function opOptionsFor(cond) {
  if (isBooleanIndicator(cond.indicator)) return BOOLEAN_OP_OPTIONS;
  return NUMERIC_OP_OPTIONS;
}

function indicatorChanged(cond) {
  const meta = indicatorByName.value[cond.indicator];
  if (!meta) return;
  if (meta.unit === "0/1") {
    cond.op = "==";
    cond.value = 1;
  } else {
    cond.op = meta.default_op || ">=";
    cond.value = meta.default_value ?? 0;
  }
}

function isBetweenOp(op) {
  return op === "between";
}

function unitHint(name) {
  return indicatorByName.value[name]?.unit || "";
}

// ---------- 预设应用 ----------
const activePresetId = ref(null);
function applyPreset(preset) {
  activePresetId.value = preset.id;
  // 深拷贝避免引用 preset 对象
  conditions.value = structuredClone(preset.conditions || []);
  if (preset.order_by) orderBy.value = preset.order_by;
  if (preset.order) orderDir.value = preset.order;
  if (preset.universe) {
    universe.value = {
      exclude_st: preset.universe.exclude_st ?? true,
      boards: preset.universe.boards ?? ["main", "cyb", "kcb"],
      min_amount: preset.universe.min_amount ?? 50_000_000,
    };
  }
}

async function deletePreset(preset) {
  if (!confirm(`删除预设「${preset.name}」？`)) return;
  try {
    await fetchJson(`/api/screener/presets/${preset.id}`, { method: "DELETE" });
    queryClient.invalidateQueries({ queryKey: ["screener-presets"] });
  } catch (e) {
    alert(`删除失败：${e.message || e}`);
  }
}

// ---------- 保存为预设 ----------
const showSaveDialog = ref(false);
const saveName = ref("");
const saveDesc = ref("");
async function saveAsPreset() {
  if (!saveName.value.trim()) {
    alert("请输入预设名称");
    return;
  }
  try {
    await fetchJson("/api/screener/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: saveName.value.trim(),
        description: saveDesc.value.trim(),
        conditions: conditions.value,
        universe: universe.value,
        order_by: orderBy.value,
        order: orderDir.value,
      }),
    });
    showSaveDialog.value = false;
    saveName.value = "";
    saveDesc.value = "";
    queryClient.invalidateQueries({ queryKey: ["screener-presets"] });
  } catch (e) {
    alert(`保存失败：${e.message || e}`);
  }
}

// ---------- 执行筛选 ----------
const runResult = ref(null);
const runError = ref("");
const running = ref(false);
let runSeq = 0;

async function runScreener() {
  const seq = ++runSeq;
  running.value = true;
  runError.value = "";
  runResult.value = null;
  try {
    const payload = await fetchJson("/api/screener/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conditions: conditions.value,
        universe: universe.value,
        order_by: orderBy.value,
        order: orderDir.value,
        limit: limit.value,
        preset_id: activePresetId.value,
      }),
    });
    if (seq !== runSeq) return;
    runResult.value = payload;
  } catch (e) {
    if (seq === runSeq) runError.value = e.message || String(e);
  } finally {
    if (seq === runSeq) running.value = false;
  }
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

// ---------- 默认载入第一个预设 ----------
onMounted(async () => {
  await presetsQuery.refetch();
  if (presets.value.length && !conditions.value.length) {
    applyPreset(presets.value[0]);
  }
});

onUnmounted(() => {
  runSeq = -1; // 防止卸载后回调
});

// ---------- 展示辅助 ----------
const results = computed(() => runResult.value?.results || []);
const warnings = computed(() => runResult.value?.warnings || []);
const dataDate = computed(() => runResult.value?.data_date || coverage.value?.latest_date || "");
const hasData = computed(() => (coverage.value?.stock_count || 0) > 0);
const isStale = computed(() => cache.value?.is_stale === true);

const coveragePctText = computed(() => {
  const pct = coverage.value?.coverage_pct;
  if (pct == null) return "—";
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

// 结果行展示的字段顺序
const RESULT_COLUMNS = [
  { key: "close", label: "现价", format: (v) => formatNumber(v) },
  { key: "change_pct", label: "涨跌幅", format: (v) => formatPercent(v) },
  { key: "turnover_rate", label: "换手率", format: (v) => `${formatNumber(v)}%` },
  { key: "volume_ratio", label: "量比", format: (v) => formatNumber(v) },
  { key: "amount", label: "成交额", format: (v) => formatAmount(v) },
  { key: "main_net_inflow_5d", label: "5日主力", format: (v) => formatAmount(v) },
];

function changeClass(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return "";
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "";
}

function toggleBoard(value) {
  const list = universe.value.boards;
  const idx = list.indexOf(value);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(value);
  // 至少保留一个板块
  if (!list.length) list.push("main");
  universe.value = { ...universe.value, boards: [...list] };
}
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">选股</p>
        <h2>选股器</h2>
        <p class="hero-copy">基于最近完整交易日收盘数据的多因子筛选；6 套内置策略 + 自定义条件。</p>
      </div>
      <QueryState
        :is-loading="indicatorsQuery.isLoading.value"
        :is-fetching="statusQuery.isFetching.value"
        :updated-at="dataDate ? `数据日期 ${dataDate}` : ''"
      />
    </header>

    <!-- 数据状态条（拆成 metric cards + 数据源 + 缓存陈旧提示） -->
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
        <button
          class="btn btn-primary"
          type="button"
          :disabled="backfillInFlight || isBackfilling"
          @click="triggerBackfill()"
        >{{ isBackfilling ? "回补中…" : "更新数据" }}</button>
        <button
          class="btn btn-ghost"
          type="button"
          :disabled="backfillInFlight || isBackfilling"
          @click="triggerBackfill(500)"
          title="仅前 500 只（成交额 Top），用于冒烟"
        >冒烟回补</button>
      </div>
    </section>

    <div v-if="isStale && hasData" class="stale-banner">
      ⚠ 缓存已陈旧（{{ cacheAgeText }}），点击右上「更新数据」拉取最新行情
    </div>

    <!-- 回补进度（按 stage 分段着色） -->
    <section v-if="isBackfilling || backfillMessage" class="backfill-progress">
      <div class="progress-info">
        <span class="progress-stage" :data-stage="progress.stage">{{ progress.stage || "idle" }}</span>
        <span class="progress-msg">{{ backfillMessage || "回补中…" }}</span>
        <span v-if="progress.total" class="progress-counts">
          {{ progress.done }} / {{ progress.total }}（{{ backfillProgressPct }}%）
        </span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :data-stage="progress.stage" :style="{ width: backfillProgressPct + '%' }"></div>
      </div>
      <div v-if="progress.failed?.length" class="progress-failed">
        失败 {{ progress.failed.length }} 只（详见后端日志）
      </div>
    </section>

    <p v-if="backfillError" class="inline-error">{{ backfillError }}</p>

    <EmptyState
      v-if="!hasData && !isBackfilling"
      title="尚无日线数据"
      description="选股器依赖本地日线库。点击「更新数据」开始首次回补（约 60-90 分钟），或用「冒烟回补」先试跑前 500 只。"
    />

    <!-- 预设条 -->
    <section class="preset-bar">
      <div class="preset-label">策略预设：</div>
      <div class="preset-chips">
        <button
          v-for="preset in presets"
          :key="preset.id"
          class="preset-chip"
          :class="{ active: activePresetId === preset.id }"
          :title="preset.description || ''"
          @click="applyPreset(preset)"
        >{{ preset.name }}</button>
      </div>
    </section>

    <!-- 条件构建器 -->
    <DataPanel title="条件构建器" :subtitle="conditions.length ? `${conditions.length} 条` : '空'">
      <template #actions>
        <button class="btn btn-ghost" type="button" @click="addCondition">＋ 添加条件</button>
        <button class="btn btn-ghost" type="button" @click="showSaveDialog = true">保存为预设</button>
      </template>

      <div v-if="!conditions.length" class="empty-hint">暂无条件，点击「添加条件」或选择上方预设。</div>

      <div class="condition-list">
        <div v-for="(cond, idx) in conditions" :key="idx" class="condition-row">
          <span class="cond-idx">{{ idx + 1 }}</span>
          <div class="cond-grid">
            <div class="cond-field">
              <label>指标</label>
              <UiSelect
                :model-value="cond.indicator"
                :options="indicatorUiOptions"
                size="sm"
                @update:model-value="(v) => { cond.indicator = v; indicatorChanged(cond); }"
              />
            </div>
            <div class="cond-field cond-op">
              <label>操作符</label>
              <UiSelect
                :model-value="cond.op"
                :options="opOptionsFor(cond)"
                :disabled="isBooleanIndicator(cond.indicator)"
                size="sm"
                @update:model-value="(v) => { cond.op = v; if (v === 'between' && !Array.isArray(cond.value)) cond.value = [cond.value, cond.value]; }"
              />
            </div>
            <div class="cond-field cond-val">
              <label>值</label>
              <template v-if="isBooleanIndicator(cond.indicator)">
                <div class="bool-chips">
                  <button
                    type="button"
                    class="bool-chip"
                    :class="{ active: cond.value === 1 }"
                    @click="cond.value = 1"
                  >是</button>
                  <button
                    type="button"
                    class="bool-chip"
                    :class="{ active: cond.value === 0 }"
                    @click="cond.value = 0"
                  >否</button>
                </div>
              </template>
              <template v-else-if="isBetweenOp(cond.op)">
                <div class="between-inputs">
                  <input v-model.number="cond.value[0]" type="number" placeholder="下限" />
                  <span class="c-sep">~</span>
                  <input v-model.number="cond.value[1]" type="number" placeholder="上限" />
                </div>
              </template>
              <template v-else>
                <input
                  v-model.number="cond.value"
                  type="number"
                  :placeholder="unitHint(cond.indicator) || '数值'"
                />
              </template>
            </div>
            <button class="c-remove" type="button" @click="removeCondition(idx)" title="删除">×</button>
          </div>
        </div>
      </div>

      <!-- 股票池 -->
      <div class="ctrl-row">
        <div class="ctrl-group">
          <span class="ctrl-label">股票池</span>
          <label class="check">
            <input v-model="universe.exclude_st" type="checkbox" /> 排除 ST
          </label>
        </div>
        <div class="ctrl-group">
          <span class="ctrl-label">板块</span>
          <label v-for="b in BOARD_OPTIONS" :key="b.value" class="check">
            <input
              type="checkbox"
              :checked="universe.boards.includes(b.value)"
              @change="toggleBoard(b.value)"
            /> {{ b.label }}
          </label>
        </div>
        <div class="ctrl-group ctrl-grow">
          <span class="ctrl-label">最低成交额</span>
          <UiSelect
            v-model="universe.min_amount"
            :options="AMOUNT_UI_OPTIONS"
            size="sm"
          />
        </div>
      </div>

      <!-- 排序 + 限数 + 执行 -->
      <div class="ctrl-row">
        <div class="ctrl-group ctrl-grow">
          <span class="ctrl-label">排序</span>
          <UiSelect
            v-model="orderBy"
            :options="indicatorUiOptions"
            size="sm"
          />
        </div>
        <div class="ctrl-group">
          <UiSelect v-model="orderDir" :options="ORDER_UI_OPTIONS" size="sm" />
        </div>
        <div class="ctrl-group">
          <UiSelect v-model="limit" :options="LIMIT_UI_OPTIONS" size="sm" />
        </div>
        <button
          class="btn btn-primary run-btn"
          type="button"
          :disabled="running || !hasData"
          @click="runScreener"
        >{{ running ? "筛选中…" : "开始筛选" }}</button>
      </div>
    </DataPanel>

    <!-- 保存预设对话框（Teleport 避免遮挡） -->
    <Teleport to="body">
      <div v-if="showSaveDialog" class="modal-mask" @click.self="showSaveDialog = false">
        <div class="modal" role="dialog" aria-modal="true">
          <h3>保存为预设</h3>
          <p class="modal-hint">{{ conditions.length }} 条条件 · {{ universe.boards.length }} 个板块</p>
          <label>名称<input v-model="saveName" type="text" placeholder="如：我的突破策略" /></label>
          <label>说明<input v-model="saveDesc" type="text" placeholder="可选" /></label>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" @click="showSaveDialog = false">取消</button>
            <button class="btn btn-primary" type="button" @click="saveAsPreset">保存</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 结果 -->
    <DataPanel title="筛选结果" :subtitle="runResult ? `共 ${runResult.total} 条` : ''">
      <template #actions>
        <QueryState :is-loading="running" />
      </template>

      <p v-if="runError" class="inline-error">筛选失败：{{ runError }}</p>

      <div v-if="warnings.length" class="warnings">
        <div v-for="(w, i) in warnings" :key="i" class="warn-item">⚠ {{ w }}</div>
      </div>

      <div v-if="results.length" class="result-list">
        <div v-for="item in results" :key="item.code" class="result-card">
          <div class="rc-head">
            <span class="rc-code">{{ item.code }}</span>
            <span class="rc-name">{{ item.name }}</span>
            <span class="rc-change" :class="changeClass(item.change_pct)">{{ formatPercent(item.change_pct) }}</span>
          </div>
          <div class="rc-metrics">
            <div v-for="col in RESULT_COLUMNS" :key="col.key" class="rc-metric">
              <span class="rc-metric-label">{{ col.label }}</span>
              <span class="rc-metric-value">{{ col.format(item[col.key]) }}</span>
            </div>
          </div>
          <div class="rc-actions">
            <button class="btn btn-ghost btn-sm" type="button" @click="addToWatch(item)">＋ 加自选</button>
            <small v-if="watchMessages[item.code]" class="rc-watch-msg">{{ watchMessages[item.code] }}</small>
          </div>
        </div>
      </div>

      <EmptyState
        v-else-if="!running && runResult"
        title="无匹配结果"
        description="放宽条件或更换预设后再试"
      />
      <EmptyState
        v-else-if="!running && !runResult"
        title="点击「开始筛选」"
        description="选择预设或自定义条件后执行"
      />
    </DataPanel>
  </section>
</template>

<style scoped>
/* ---------- 状态条 / metric cards ---------- */
.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: stretch;
  padding: 14px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 12px;
}
.metric-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 110px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
}
.metric-label {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.metric-cell strong {
  font-size: 18px;
  font-weight: 700;
  color: var(--text, #e2e8f0);
  font-variant-numeric: tabular-nums;
}
.metric-hint {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}
.status-source {
  display: flex;
  align-items: center;
  margin-left: auto;
}
.status-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.stale-banner {
  padding: 10px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 8px;
  font-size: 13px;
  color: #fbbf24;
  margin-bottom: 12px;
}

/* ---------- 回补进度（按 stage 分色） ---------- */
.backfill-progress {
  padding: 12px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 12px;
}
.progress-info {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  margin-bottom: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.progress-stage {
  padding: 2px 10px;
  border-radius: 999px;
  font-weight: 600;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.06em;
}
.progress-stage[data-stage="bars"] { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }
.progress-stage[data-stage="fund_flow"] { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.progress-stage[data-stage="done"] { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.progress-stage[data-stage="error"] { background: rgba(248, 113, 113, 0.15); color: #f87171; }

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #0ea5e9);
  transition: width 0.3s;
}
.progress-fill[data-stage="fund_flow"] {
  background: linear-gradient(90deg, #c084fc, #a855f7);
}
.progress-fill[data-stage="done"] {
  background: linear-gradient(90deg, #4ade80, #22c55e);
}
.progress-fill[data-stage="error"] {
  background: linear-gradient(90deg, #f87171, #ef4444);
}
.progress-failed {
  font-size: 11px;
  color: var(--danger, #f87171);
  margin-top: 6px;
}

/* ---------- 预设条 ---------- */
.preset-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.preset-label {
  font-size: 13px;
  color: var(--text-muted, #94a3b8);
}
.preset-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.preset-chip {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  background: transparent;
  color: var(--text-secondary, #cbd5e1);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.preset-chip:hover {
  border-color: var(--accent, #06b6d4);
  color: var(--text, #e2e8f0);
}
.preset-chip.active {
  background: var(--accent-soft, rgba(6, 182, 212, 0.15));
  border-color: var(--accent, #06b6d4);
  color: var(--accent, #06b6d4);
}

/* ---------- 条件构建器（每条单独一行） ---------- */
.empty-hint {
  padding: 16px;
  color: var(--text-muted, #94a3b8);
  font-size: 13px;
  text-align: center;
}
.condition-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.condition-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
}
.cond-idx {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent-soft, rgba(56, 189, 248, 0.15));
  color: var(--accent, #38bdf8);
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
  align-self: center;
}
.cond-grid {
  display: grid;
  grid-template-columns: 1.5fr 0.8fr 1.2fr auto;
  gap: 10px;
  flex: 1;
  align-items: end;
}
.cond-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.cond-field label {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.cond-field input[type="number"] {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  background: var(--surface, rgba(15, 23, 42, 0.6));
  color: var(--text, #e2e8f0);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.cond-field input[type="number"]:focus {
  outline: none;
  border-color: var(--accent, #06b6d4);
}
.between-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.between-inputs input {
  flex: 1;
  min-width: 60px;
}
.c-sep {
  color: var(--text-muted, #94a3b8);
  font-weight: 600;
}
.bool-chips {
  display: flex;
  gap: 6px;
}
.bool-chip {
  flex: 1;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  background: transparent;
  color: var(--text-secondary, #cbd5e1);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.bool-chip:hover {
  border-color: var(--accent, #06b6d4);
}
.bool-chip.active {
  background: var(--accent-soft, rgba(56, 189, 248, 0.15));
  border-color: var(--accent, #38bdf8);
  color: var(--accent, #38bdf8);
  font-weight: 600;
}
.c-remove {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.08);
  color: var(--danger, #f87171);
  cursor: pointer;
  font-size: 18px;
  flex-shrink: 0;
  align-self: center;
  transition: all 0.15s;
}
.c-remove:hover {
  background: rgba(248, 113, 113, 0.2);
}

/* ---------- 控件行（股票池/排序） ---------- */
.ctrl-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 10px 0;
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  font-size: 13px;
}
.ctrl-row:first-of-type {
  border-top: none;
}
.ctrl-group {
  display: flex;
  gap: 10px;
  align-items: center;
}
.ctrl-grow {
  flex: 1;
  min-width: 180px;
}
.ctrl-label {
  color: var(--text-muted, #94a3b8);
  font-size: 12px;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
}
.run-btn {
  margin-left: auto;
}

/* ---------- 按钮 ---------- */
.btn {
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  font-family: inherit;
}
.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn-primary {
  background: var(--accent, #06b6d4);
  color: #fff;
  border: none;
}
.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}
.btn-ghost {
  background: transparent;
  color: var(--text-secondary, #cbd5e1);
  border-color: var(--border, rgba(255, 255, 255, 0.1));
}
.btn-ghost:hover:not(:disabled) {
  border-color: var(--accent, #06b6d4);
  color: var(--text, #e2e8f0);
}
.btn-sm {
  padding: 3px 10px;
  font-size: 12px;
}

/* ---------- 对话框 ---------- */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  display: grid;
  place-items: center;
  z-index: 1000;
}
.modal {
  background: var(--panel-bg, #0f172a);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  border-radius: 12px;
  padding: 22px;
  width: 380px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
}
.modal h3 {
  margin: 0;
  font-size: 16px;
}
.modal-hint {
  margin: -4px 0 4px;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}
.modal label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}
.modal input {
  padding: 9px 10px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  background: var(--surface, rgba(0, 0, 0, 0.2));
  color: var(--text, #e2e8f0);
  font-size: 13px;
  font-family: inherit;
}
.modal input:focus {
  outline: none;
  border-color: var(--accent, #06b6d4);
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 4px;
}

/* ---------- 警告 ---------- */
.warnings {
  margin-bottom: 12px;
}
.warn-item {
  padding: 8px 12px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: #fbbf24;
  margin-bottom: 4px;
}

.inline-error {
  color: var(--danger, #f87171);
  font-size: 13px;
  margin: 8px 0;
}

/* ---------- 结果列表 ---------- */
.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-card {
  padding: 12px 14px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
}
.rc-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.rc-code {
  font-weight: 700;
  font-size: 15px;
}
.rc-name {
  color: var(--text-secondary, #cbd5e1);
  font-size: 13px;
}
.rc-change {
  margin-left: auto;
  font-weight: 600;
  font-size: 14px;
}
.rc-change.pos {
  color: var(--up, #f87171);
}
.rc-change.neg {
  color: var(--down, #34d399);
}
.rc-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 8px;
}
.rc-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rc-metric-label {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}
.rc-metric-value {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.rc-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.rc-watch-msg {
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
}

/* ---------- 响应式 ---------- */
@media (max-width: 900px) {
  .cond-grid {
    grid-template-columns: 1fr 1fr;
  }
  .cond-field.cond-val {
    grid-column: 1 / -1;
  }
  .ctrl-grow {
    min-width: 100%;
  }
}

@media (max-width: 640px) {
  .status-actions {
    margin-left: 0;
    width: 100%;
  }
  .run-btn {
    margin-left: 0;
  }
  .rc-metrics {
    grid-template-columns: repeat(3, 1fr);
  }
  .cond-grid {
    grid-template-columns: 1fr;
  }
}
</style>