<script setup>
import { computed, ref, watch } from "vue";
import DataPanel from "../ui/DataPanel.vue";
import UiSelect from "../ui/UiSelect.vue";
import { saveScreenerPreset } from "../../lib/api";

const props = defineProps({
  indicatorGroups: { type: Array, default: () => [] },
  hasData: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  // seed: 传入预设对象时，加载其条件到构建器（克隆到自由编辑用）
  seed: { type: Object, default: null },
});
const emit = defineEmits(["run", "saved"]);

const indicatorByName = computed(() => {
  const map = {};
  for (const g of props.indicatorGroups) {
    for (const ind of g.indicators) map[ind.name] = ind;
  }
  return map;
});
const indicatorUiOptions = computed(() =>
  props.indicatorGroups.map((g) => ({
    label: g.name,
    options: g.indicators.map((ind) => ({
      value: ind.name,
      label: ind.label,
      hint: ind.unit === "0/1" ? "布尔" : ind.unit || "",
    })),
  })),
);

// ---------- 构建器状态 ----------
const conditions = ref([]);
const universe = ref({ exclude_st: true, boards: ["main", "cyb", "kcb"], min_amount: 50_000_000 });
const orderBy = ref("change_pct");
const orderDir = ref("desc");
const limit = ref(100);
const matchMode = ref("all");
const minScore = ref(0);

const BOARD_OPTIONS = [
  { value: "main", label: "主板" },
  { value: "cyb", label: "创业板" },
  { value: "kcb", label: "科创板" },
];
const AMOUNT_OPTIONS = [
  { value: 50_000_000, label: "≥ 5000 万" },
  { value: 200_000_000, label: "≥ 2 亿" },
  { value: 500_000_000, label: "≥ 5 亿" },
  { value: 1_000_000_000, label: "≥ 10 亿" },
];
const ORDER_UI_OPTIONS = [{ label: "方向", options: [{ value: "desc", label: "降序" }, { value: "asc", label: "升序" }] }];
const LIMIT_UI_OPTIONS = [{ label: "条数", options: [50, 100, 200, 500].map((v) => ({ value: v, label: `${v} 条` })) }];
const MATCH_MODE_OPTIONS = [
  { value: "all", label: "全满足 (AND)" },
  { value: "any", label: "任一满足 (OR)" },
  { value: "score", label: "评分模式 (按权重计分)" },
];

const BOOLEAN_OP_OPTIONS = [{ value: "==", label: "等于" }];
const NUMERIC_OP_OPTIONS = [
  { value: ">=", label: "≥" }, { value: ">", label: ">" },
  { value: "<=", label: "≤" }, { value: "<", label: "<" },
  { value: "==", label: "=" }, { value: "!=", label: "≠" },
  { value: "between", label: "区间" },
];

function isBooleanIndicator(name) { return indicatorByName.value[name]?.unit === "0/1"; }
function opOptionsFor(cond) { return isBooleanIndicator(cond.indicator) ? BOOLEAN_OP_OPTIONS : NUMERIC_OP_OPTIONS; }
function isBetweenOp(op) { return op === "between"; }
function unitHint(name) { return indicatorByName.value[name]?.unit || ""; }

function newCondition() { return { indicator: "consecutive_up_days", op: ">=", value: 3, weight: 1 }; }
function addCondition() { conditions.value.push(newCondition()); }
function removeCondition(idx) { conditions.value.splice(idx, 1); }
function indicatorChanged(cond) {
  const meta = indicatorByName.value[cond.indicator];
  if (!meta) return;
  if (meta.unit === "0/1") { cond.op = "=="; cond.value = 1; }
  else { cond.op = meta.default_op || ">="; cond.value = meta.default_value ?? 0; }
  if (!cond.weight) cond.weight = 1;
}
function toggleBoard(value) {
  const list = universe.value.boards;
  const idx = list.indexOf(value);
  if (idx >= 0) list.splice(idx, 1); else list.push(value);
  if (!list.length) list.push("main");
  universe.value = { ...universe.value, boards: [...list] };
}

// 加载 seed（克隆预设到自由编辑）
watch(() => props.seed, (s) => {
  if (!s) return;
  conditions.value = structuredClone(s.conditions || []);
  if (s.order_by) orderBy.value = s.order_by;
  if (s.order) orderDir.value = s.order;
  matchMode.value = s.match_mode || "all";
  minScore.value = s.min_score || 0;
  if (s.universe) {
    universe.value = {
      exclude_st: s.universe.exclude_st ?? true,
      boards: s.universe.boards ?? ["main", "cyb", "kcb"],
      min_amount: s.universe.min_amount ?? 50_000_000,
    };
  }
}, { immediate: true });

// ---------- 执行 / 保存 ----------
// 执行交由父组件（共享 ResultTable + Drawer）；本组件只发出 payload
function runScreener() {
  emit("run", {
    conditions: conditions.value,
    universe: universe.value,
    order_by: orderBy.value,
    order: orderDir.value,
    limit: limit.value,
    match_mode: matchMode.value,
    min_score: matchMode.value === "score" ? minScore.value : 0,
  });
}

// 保存对话框
const showSave = ref(false);
const saveName = ref("");
const saveDesc = ref("");
async function saveAsPreset() {
  if (!saveName.value.trim()) { alert("请输入预设名称"); return; }
  try {
    await saveScreenerPreset({
      name: saveName.value.trim(),
      description: saveDesc.value.trim(),
      conditions: conditions.value,
      universe: universe.value,
      order_by: orderBy.value,
      order: orderDir.value,
      category: "自定义",
      match_mode: matchMode.value,
      min_score: matchMode.value === "score" ? minScore.value : 0,
    });
    showSave.value = false;
    saveName.value = "";
    saveDesc.value = "";
    emit("saved");
  } catch (e) {
    alert(`保存失败：${e.message || e}`);
  }
}

// 暴露给父组件：外部可读取当前条件（如切换 tab 前保存草稿）
defineExpose({ conditions });
</script>


<template>
  <DataPanel title="条件构建器" :subtitle="conditions.length ? `${conditions.length} 条` : '空'">
    <template #actions>
      <button class="btn btn-ghost" type="button" @click="addCondition">＋ 添加条件</button>
      <button class="btn btn-ghost" type="button" @click="showSave = true">保存为预设</button>
    </template>

    <!-- 匹配模式 -->
    <div class="ctrl-row">
      <div class="ctrl-group ctrl-grow">
        <span class="ctrl-label">匹配模式</span>
        <UiSelect v-model="matchMode" :options="MATCH_MODE_OPTIONS" size="sm" />
      </div>
      <div v-if="matchMode === 'score'" class="ctrl-group">
        <span class="ctrl-label">最低分</span>
        <input v-model.number="minScore" type="number" min="0" class="score-input" />
      </div>
      <div v-if="matchMode === 'score'" class="mode-hint">评分模式：每条满足按权重计分，总分 ≥ 最低分即命中，容忍部分条件缺失</div>
    </div>

    <div v-if="!conditions.length" class="empty-hint">暂无条件，点击「添加条件」。评分模式下可调每条权重。</div>

    <div class="condition-list">
      <div v-for="(cond, idx) in conditions" :key="idx" class="condition-row">
        <span class="cond-idx">{{ idx + 1 }}</span>
        <div class="cond-grid">
          <div class="cond-field">
            <label>指标</label>
            <UiSelect :model-value="cond.indicator" :options="indicatorUiOptions" size="sm"
              @update:model-value="(v) => { cond.indicator = v; indicatorChanged(cond); }" />
          </div>
          <div class="cond-field cond-op">
            <label>操作符</label>
            <UiSelect :model-value="cond.op" :options="opOptionsFor(cond)" :disabled="isBooleanIndicator(cond.indicator)" size="sm"
              @update:model-value="(v) => { cond.op = v; if (v === 'between' && !Array.isArray(cond.value)) cond.value = [cond.value, cond.value]; }" />
          </div>
          <div class="cond-field cond-val">
            <label>值</label>
            <template v-if="isBooleanIndicator(cond.indicator)">
              <div class="bool-chips">
                <button type="button" class="bool-chip" :class="{ active: cond.value === 1 }" @click="cond.value = 1">是</button>
                <button type="button" class="bool-chip" :class="{ active: cond.value === 0 }" @click="cond.value = 0">否</button>
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
              <input v-model.number="cond.value" type="number" :placeholder="unitHint(cond.indicator) || '数值'" />
            </template>
          </div>
          <div v-if="matchMode === 'score'" class="cond-field cond-weight">
            <label>权重</label>
            <input v-model.number="cond.weight" type="number" min="1" step="1" />
          </div>
          <button class="c-remove" type="button" @click="removeCondition(idx)" title="删除">×</button>
        </div>
      </div>
    </div>

    <!-- 股票池 -->
    <div class="ctrl-row">
      <div class="ctrl-group">
        <span class="ctrl-label">股票池</span>
        <label class="check"><input v-model="universe.exclude_st" type="checkbox" /> 排除 ST</label>
      </div>
      <div class="ctrl-group">
        <span class="ctrl-label">板块</span>
        <label v-for="b in BOARD_OPTIONS" :key="b.value" class="check">
          <input type="checkbox" :checked="universe.boards.includes(b.value)" @change="toggleBoard(b.value)" /> {{ b.label }}
        </label>
      </div>
      <div class="ctrl-group ctrl-grow">
        <span class="ctrl-label">最低成交额</span>
        <UiSelect v-model="universe.min_amount" :options="AMOUNT_OPTIONS" size="sm" />
      </div>
    </div>

    <!-- 排序 + 执行 -->
    <div class="ctrl-row">
      <div class="ctrl-group ctrl-grow">
        <span class="ctrl-label">排序</span>
        <UiSelect v-model="orderBy" :options="indicatorUiOptions" size="sm" />
      </div>
      <div class="ctrl-group"><UiSelect v-model="orderDir" :options="ORDER_UI_OPTIONS" size="sm" /></div>
      <div class="ctrl-group"><UiSelect v-model="limit" :options="LIMIT_UI_OPTIONS" size="sm" /></div>
      <button class="btn btn-primary run-btn" type="button" :disabled="running || !hasData" @click="runScreener">
        {{ running ? "筛选中…" : "开始筛选" }}
      </button>
    </div>

    <!-- 保存对话框 -->
    <Teleport to="body">
      <div v-if="showSave" class="modal-mask" @click.self="showSave = false">
        <div class="modal" role="dialog" aria-modal="true">
          <h3>保存为预设</h3>
          <p class="modal-hint">{{ conditions.length }} 条条件 · {{ universe.boards.length }} 个板块 · {{ matchMode === "score" ? `评分≥${minScore}` : matchMode }}</p>
          <label>名称<input v-model="saveName" type="text" placeholder="如：我的突破策略" /></label>
          <label>说明<input v-model="saveDesc" type="text" placeholder="可选" /></label>
          <div class="modal-actions">
            <button class="btn btn-ghost" type="button" @click="showSave = false">取消</button>
            <button class="btn btn-primary" type="button" @click="saveAsPreset">保存</button>
          </div>
        </div>
      </div>
    </Teleport>
  </DataPanel>
</template>

<style scoped>
.ctrl-row { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: flex-end; padding: 10px 0; border-top: 1px dashed rgba(255, 255, 255, 0.05); }
.ctrl-row:first-of-type { border-top: none; }
.ctrl-group { display: flex; flex-direction: column; gap: 4px; }
.ctrl-grow { flex: 1 1 160px; min-width: 140px; }
.ctrl-label { font-size: 11px; color: var(--text-muted, #94a3b8); text-transform: uppercase; letter-spacing: 0.04em; }
.ctrl-group :deep(.check) { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-secondary, #cbd5e1); cursor: pointer; }
.mode-hint { font-size: 11px; color: var(--text-muted, #64748b); align-self: center; max-width: 280px; }
.score-input { width: 70px; }

.empty-hint { padding: 14px; color: var(--text-muted, #64748b); font-size: 13px; text-align: center; }
.condition-list { display: flex; flex-direction: column; gap: 8px; padding: 8px 0; }
.condition-row { display: flex; gap: 8px; align-items: flex-start; }
.cond-idx { font-size: 12px; color: var(--text-muted, #64748b); padding-top: 26px; width: 16px; }
.cond-grid { flex: 1; display: grid; grid-template-columns: 1.4fr 0.9fr 1fr auto auto; gap: 8px; align-items: end; }
.cond-field { display: flex; flex-direction: column; gap: 3px; }
.cond-field label { font-size: 10px; color: var(--text-muted, #64748b); }
.cond-field input { font: inherit; padding: 6px 8px; background: rgba(255,255,255,0.03); border: 1px solid var(--border, rgba(255,255,255,0.1)); border-radius: 6px; color: var(--text, #e2e8f0); width: 100%; box-sizing: border-box; }
.cond-weight { max-width: 80px; }
.cond-weight input { padding: 6px 6px; }
.bool-chips { display: flex; gap: 4px; }
.bool-chip { font: inherit; font-size: 12px; padding: 5px 12px; border-radius: 6px; background: rgba(255,255,255,0.03); border: 1px solid var(--border, rgba(255,255,255,0.1)); color: var(--text-muted, #94a3b8); cursor: pointer; }
.bool-chip.active { background: rgba(6,182,212,0.12); border-color: var(--accent, #06b6d4); color: var(--accent, #06b6d4); }
.between-inputs { display: flex; align-items: center; gap: 4px; }
.between-inputs input { flex: 1; }
.c-sep { color: var(--text-muted, #64748b); }
.c-remove { background: none; border: none; color: var(--text-muted, #64748b); font-size: 18px; cursor: pointer; padding: 6px 8px; align-self: end; }
.c-remove:hover { color: var(--danger, #f87171); }

.inline-error { color: var(--danger, #f87171); font-size: 13px; padding: 8px 0; }

.btn { font: inherit; cursor: pointer; border-radius: 8px; transition: all 0.15s; }
.btn-sm { padding: 3px 8px; font-size: 11px; }
.btn-ghost { background: transparent; border: 1px solid var(--border, rgba(255,255,255,0.12)); color: var(--text-secondary, #cbd5e1); padding: 6px 12px; font-size: 13px; }
.btn-ghost:hover { border-color: var(--accent, #06b6d4); color: var(--accent, #06b6d4); }
.btn-primary { background: var(--accent, #06b6d4); border: 1px solid var(--accent, #06b6d4); color: #0f172a; font-weight: 600; padding: 8px 18px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.run-btn { margin-left: auto; }

.modal-mask { position: fixed; inset: 0; background: rgba(2,6,23,0.6); display: flex; align-items: center; justify-content: center; z-index: 1100; }
.modal { background: var(--surface, #0f172a); border: 1px solid var(--border, rgba(255,255,255,0.1)); border-radius: 12px; padding: 20px; width: min(380px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.modal h3 { margin: 0 0 4px; color: var(--text, #e2e8f0); }
.modal-hint { font-size: 12px; color: var(--text-muted, #94a3b8); margin: 0; }
.modal label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-muted, #94a3b8); }
.modal input { font: inherit; padding: 8px; background: rgba(255,255,255,0.03); border: 1px solid var(--border, rgba(255,255,255,0.1)); border-radius: 6px; color: var(--text, #e2e8f0); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px; }

@media (max-width: 640px) {
  .cond-grid { grid-template-columns: 1fr 1fr; }
  .cond-weight { max-width: none; }
  .run-btn { margin-left: 0; width: 100%; }
}
</style>
