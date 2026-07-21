<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
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
  min_amount: 50000000,
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

function newCondition() {
  return { indicator: "consecutive_up_days", op: ">=", value: 3 };
}

function addCondition() {
  conditions.value.push(newCondition());
}

function removeCondition(index) {
  conditions.value.splice(index, 1);
}

function onIndicatorChange(cond) {
  const meta = indicatorByName.value[cond.indicator];
  if (!meta) return;
  // 布尔指标固定 == 1
  if (meta.unit === "0/1") {
    cond.op = "==";
    cond.value = meta.default_value ?? 1;
  } else {
    cond.op = meta.default_op || ">=";
    cond.value = meta.default_value ?? 0;
  }
}

function isBooleanIndicator(name) {
  const meta = indicatorByName.value[name];
  return meta?.unit === "0/1";
}

function isBetweenOp(op) {
  return op === "between";
}

// ---------- 预设应用 ----------
const activePresetId = ref(null);
function applyPreset(preset) {
  activePresetId.value = preset.id;
  conditions.value = JSON.parse(JSON.stringify(preset.conditions || []));
  if (preset.order_by) orderBy.value = preset.order_by;
  if (preset.order) orderDir.value = preset.order;
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

    <!-- 数据状态条 -->
    <section class="status-bar">
      <div class="status-cell">
        <span class="status-label">覆盖股票</span>
        <strong>{{ coverage.stock_count ?? 0 }}</strong>
      </div>
      <div class="status-cell">
        <span class="status-label">数据日期</span>
        <strong>{{ coverage.latest_date || "--" }}</strong>
      </div>
      <div class="status-cell">
        <span class="status-label">日线行数</span>
        <strong>{{ formatNumber(coverage.bar_rows ?? 0, 0) }}</strong>
      </div>
      <div class="status-cell">
        <span class="status-label">资金流股票</span>
        <strong>{{ coverage.flow_stock_count ?? 0 }}</strong>
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

    <!-- 回补进度 -->
    <section v-if="isBackfilling || backfillMessage" class="backfill-progress">
      <div class="progress-info">
        <span>{{ backfillMessage || "回补中…" }}</span>
        <span v-if="progress.stage">阶段：{{ progress.stage }}</span>
        <span v-if="progress.total">{{ progress.done }} / {{ progress.total }}（{{ backfillProgressPct }}%）</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: backfillProgressPct + '%' }"></div>
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
    <DataPanel title="条件构建器">
      <template #actions>
        <button class="btn btn-ghost" type="button" @click="addCondition">＋ 添加条件</button>
        <button class="btn btn-ghost" type="button" @click="showSaveDialog = true">保存为预设</button>
      </template>

      <div v-if="!conditions.length" class="empty-hint">暂无条件，点击「添加条件」或选择上方预设。</div>

      <div class="condition-list">
        <div v-for="(cond, idx) in conditions" :key="idx" class="condition-row">
          <select v-model="cond.indicator" class="c-indicator" @change="onIndicatorChange(cond)">
            <optgroup v-for="g in indicatorGroups" :key="g.name" :label="g.name">
              <option v-for="ind in g.indicators" :key="ind.name" :value="ind.name">{{ ind.label }}</option>
            </optgroup>
          </select>

          <select v-model="cond.op" class="c-op" :disabled="isBooleanIndicator(cond.indicator)">
            <option v-if="isBooleanIndicator(cond.indicator)" value="==">==</option>
            <template v-else>
              <option value=">=">≥</option>
              <option value=">">&gt;</option>
              <option value="<=">≤</option>
              <option value="<">&lt;</option>
              <option value="==">==</option>
              <option value="between">区间</option>
            </template>
          </select>

          <template v-if="isBetweenOp(cond.op)">
            <input
              v-model.number="cond.value[0]"
              type="number"
              class="c-value"
              placeholder="下限"
            />
            <span class="c-sep">~</span>
            <input
              v-model.number="cond.value[1]"
              type="number"
              class="c-value"
              placeholder="上限"
            />
          </template>
          <template v-else>
            <input
              v-model.number="cond.value"
              type="number"
              class="c-value"
              :disabled="isBooleanIndicator(cond.indicator)"
            />
          </template>

          <button class="c-remove" type="button" @click="removeCondition(idx)" title="删除">×</button>
        </div>
      </div>

      <!-- 股票池 -->
      <div class="universe-row">
        <span class="universe-label">股票池：</span>
        <label class="check"><input v-model="universe.exclude_st" type="checkbox" /> 排除 ST</label>
        <span class="universe-label">板块：</span>
        <label v-for="b in BOARD_OPTIONS" :key="b.value" class="check">
          <input :value="b.value" v-model="universe.boards" type="checkbox" /> {{ b.label }}
        </label>
        <span class="universe-label">最低成交额：</span>
        <select v-model.number="universe.min_amount">
          <option v-for="t in AMOUNT_TIERS" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </div>

      <!-- 排序与限数 -->
      <div class="universe-row">
        <span class="universe-label">排序：</span>
        <select v-model="orderBy">
          <optgroup v-for="g in indicatorGroups" :key="g.name" :label="g.name">
            <option v-for="ind in g.indicators" :key="ind.name" :value="ind.name">{{ ind.label }}</option>
          </optgroup>
        </select>
        <select v-model="orderDir">
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </select>
        <span class="universe-label">返回条数：</span>
        <select v-model.number="limit">
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
        <button
          class="btn btn-primary run-btn"
          type="button"
          :disabled="running || !hasData"
          @click="runScreener"
        >{{ running ? "筛选中…" : "开始筛选" }}</button>
      </div>
    </DataPanel>

    <!-- 保存预设对话框 -->
    <div v-if="showSaveDialog" class="modal-mask" @click.self="showSaveDialog = false">
      <div class="modal">
        <h3>保存为预设</h3>
        <label>名称<input v-model="saveName" type="text" placeholder="如：我的突破策略" /></label>
        <label>说明<input v-model="saveDesc" type="text" placeholder="可选" /></label>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" @click="showSaveDialog = false">取消</button>
          <button class="btn btn-primary" type="button" @click="saveAsPreset">保存</button>
        </div>
      </div>
    </div>

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
/* 状态条 */
.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  padding: 12px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 16px;
}
.status-cell { display: flex; flex-direction: column; gap: 2px; }
.status-label { font-size: 11px; color: var(--text-muted, #94a3b8); }
.status-cell strong { font-size: 16px; font-weight: 700; }
.status-actions { margin-left: auto; display: flex; gap: 8px; }

/* 回补进度 */
.backfill-progress {
  padding: 12px 16px;
  background: var(--panel-bg, rgba(15, 23, 42, 0.5));
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  margin-bottom: 16px;
}
.progress-info { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted, #94a3b8); margin-bottom: 8px; flex-wrap: wrap; }
.progress-bar { height: 6px; background: rgba(255, 255, 255, 0.06); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent, #06b6d4), #0891b2); transition: width 0.3s; }
.progress-failed { font-size: 11px; color: var(--danger, #f87171); margin-top: 6px; }

/* 预设条 */
.preset-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.preset-label { font-size: 13px; color: var(--text-muted, #94a3b8); }
.preset-chips { display: flex; gap: 8px; flex-wrap: wrap; }
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
.preset-chip:hover { border-color: var(--accent, #06b6d4); color: var(--text, #e2e8f0); }
.preset-chip.active { background: var(--accent-soft, rgba(6, 182, 212, 0.15)); border-color: var(--accent, #06b6d4); color: var(--accent, #06b6d4); }

/* 条件构建器 */
.empty-hint { padding: 16px; color: var(--text-muted, #94a3b8); font-size: 13px; text-align: center; }
.condition-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.condition-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.c-indicator { flex: 1 1 200px; min-width: 160px; }
.c-op { width: 80px; }
.c-value { width: 100px; }
.c-sep { color: var(--text-muted, #94a3b8); }
.c-remove {
  width: 28px; height: 28px;
  border-radius: 6px; border: none;
  background: rgba(248, 113, 113, 0.1);
  color: var(--danger, #f87171);
  cursor: pointer; font-size: 16px;
  flex-shrink: 0;
}
.c-remove:hover { background: rgba(248, 113, 113, 0.2); }

.universe-row {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding: 10px 0;
  border-top: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  font-size: 13px;
}
.universe-row:first-of-type { border-top: none; }
.universe-label { color: var(--text-muted, #94a3b8); }
.check { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.run-btn { margin-left: auto; }

/* 通用按钮 */
.btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background: var(--accent, #06b6d4); color: #fff; border: none; }
.btn-primary:hover:not(:disabled) { opacity: 0.9; }
.btn-ghost { background: transparent; color: var(--text-secondary, #cbd5e1); border-color: var(--border, rgba(255, 255, 255, 0.1)); }
.btn-ghost:hover:not(:disabled) { border-color: var(--accent, #06b6d4); color: var(--text, #e2e8f0); }
.btn-sm { padding: 3px 10px; font-size: 12px; }

/* 对话框 */
.modal-mask {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: grid; place-items: center;
  z-index: 1000;
}
.modal {
  background: var(--panel-bg, #0f172a);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  border-radius: 12px;
  padding: 20px;
  width: 360px;
  display: flex; flex-direction: column; gap: 12px;
}
.modal h3 { margin: 0 0 4px; }
.modal label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text-muted, #94a3b8); }
.modal input { padding: 8px; border-radius: 6px; border: 1px solid var(--border, rgba(255, 255, 255, 0.1)); background: transparent; color: var(--text, #e2e8f0); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* 警告 */
.warnings { margin-bottom: 12px; }
.warn-item {
  padding: 6px 12px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: #fbbf24;
  margin-bottom: 4px;
}

.inline-error { color: var(--danger, #f87171); font-size: 13px; margin: 8px 0; }

/* 结果列表 */
.result-list { display: flex; flex-direction: column; gap: 8px; }
.result-card {
  padding: 12px 14px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
}
.rc-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.rc-code { font-weight: 700; font-size: 15px; }
.rc-name { color: var(--text-secondary, #cbd5e1); font-size: 13px; }
.rc-change { margin-left: auto; font-weight: 600; font-size: 14px; }
.rc-change.pos { color: var(--up, #f87171); }
.rc-change.neg { color: var(--down, #34d399); }
.rc-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; }
.rc-metric { display: flex; flex-direction: column; gap: 2px; }
.rc-metric-label { font-size: 11px; color: var(--text-muted, #94a3b8); }
.rc-metric-value { font-size: 13px; font-weight: 600; }
.rc-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.rc-watch-msg { font-size: 11px; color: var(--text-muted, #94a3b8); }

select, input[type="number"], input[type="text"] {
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  background: transparent;
  color: var(--text, #e2e8f0);
  font-size: 13px;
}
select:focus, input:focus { outline: none; border-color: var(--accent, #06b6d4); }

@media (max-width: 640px) {
  .status-actions { margin-left: 0; width: 100%; }
  .run-btn { margin-left: 0; }
  .rc-metrics { grid-template-columns: repeat(3, 1fr); }
}
</style>
