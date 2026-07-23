<script setup>
import { computed, ref } from "vue";
import EmptyState from "../ui/EmptyState.vue";
import LoadingSkeleton from "../ui/LoadingSkeleton.vue";
import { formatAmount, formatNumber, formatPercent } from "../../lib/formatters";

const props = defineProps({
  results: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  warnings: { type: Array, default: () => [] },
  dataDate: { type: String, default: "" },
  total: { type: Number, default: 0 },
  showScore: { type: Boolean, default: false },
  watchMessages: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["selectStock", "addWatch"]);

// 列定义：key/label/format/sortable。A 股红涨绿跌。
const COLUMNS = [
  { key: "code", label: "代码", sortable: true, format: (v) => v },
  { key: "name", label: "名称", sortable: false, format: (v) => v || "--" },
  { key: "change_pct", label: "涨跌幅", sortable: true, format: (v) => formatPercent(v), cls: true },
  { key: "close", label: "现价", sortable: true, format: (v) => formatNumber(v) },
  { key: "turnover_rate", label: "换手率", sortable: true, format: (v) => `${formatNumber(v)}%` },
  { key: "pe_dynamic", label: "PE", sortable: true, format: (v) => formatNumber(v) },
  { key: "total_mv", label: "总市值", sortable: true, format: (v) => formatAmount(v) },
  { key: "volume_ratio", label: "量比", sortable: true, format: (v) => formatNumber(v) },
  { key: "amount", label: "成交额", sortable: true, format: (v) => formatAmount(v) },
  { key: "main_net_inflow", label: "当日主力", sortable: true, format: (v) => formatAmount(v), cls: true },
  { key: "main_net_inflow_3d", label: "3日主力", sortable: true, format: (v) => formatAmount(v), cls: true },
  { key: "main_net_inflow_5d", label: "5日主力", sortable: true, format: (v) => formatAmount(v), cls: true },
  { key: "main_net_inflow_10d", label: "10日主力", sortable: true, format: (v) => formatAmount(v), cls: true },
];
const SCORE_COL = { key: "score", label: "评分", sortable: true, format: (v) => formatNumber(v, 0) };
const columns = computed(() => (props.showScore ? [...COLUMNS, SCORE_COL] : COLUMNS));

const sortKey = ref("");
const sortDir = ref("desc");
function toggleSort(col) {
  if (!col.sortable) return;
  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === "desc" ? "asc" : "desc";
  } else {
    sortKey.value = col.key;
    sortDir.value = "desc";
  }
}
const sorted = computed(() => {
  if (!sortKey.value) return props.results;
  const key = sortKey.value;
  const dir = sortDir.value === "asc" ? 1 : -1;
  return [...props.results].sort((a, b) => {
    const va = a[key], vb = b[key];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return (Number(va) - Number(vb)) * dir;
  });
});

function changeClass(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return "";
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "";
}
</script>

<template>
  <div class="result-wrap">
    <div v-if="warnings.length" class="warnings">
      <div v-for="(w, i) in warnings" :key="i" class="warn-item">⚠ {{ w }}</div>
    </div>

    <div v-if="dataDate" class="result-meta">数据日期 {{ dataDate }} · 共 {{ total }} 条</div>

    <LoadingSkeleton v-if="loading" type="table" :rows="8" />

    <div v-else-if="results.length" class="rtable">
      <div class="rrow rhead" :class="{ 'show-score': showScore }">
        <div
          v-for="col in columns"
          :key="col.key"
          class="rcell"
          :class="[`c-${col.key}`, { sortable: col.sortable, active: sortKey === col.key }]"
          @click="toggleSort(col)"
        >
          {{ col.label }}
          <span v-if="col.sortable" class="sort-arrow">{{ sortKey === col.key ? (sortDir === 'desc' ? '▾' : '▴') : '↕' }}</span>
        </div>
        <div class="rcell c-act">操作</div>
      </div>
      <div v-for="item in sorted" :key="item.code" class="rrow rbody" :class="{ 'show-score': showScore }">
        <div class="rcell c-code"><code>{{ item.code }}</code></div>
        <div class="rcell c-name" :title="item.name">{{ item.name }}</div>
        <div class="rcell c-change" :class="changeClass(item.change_pct)">{{ formatPercent(item.change_pct) }}</div>
        <div class="rcell c-close">{{ formatNumber(item.close) }}</div>
        <div class="rcell c-turnover">{{ formatNumber(item.turnover_rate) }}%</div>
        <div class="rcell c-pe">{{ formatNumber(item.pe_dynamic) }}</div>
        <div class="rcell c-mv">{{ formatAmount(item.total_mv) }}</div>
        <div class="rcell c-vr">{{ formatNumber(item.volume_ratio) }}</div>
        <div class="rcell c-amount">{{ formatAmount(item.amount) }}</div>
        <div class="rcell c-inflow" :class="changeClass(item.main_net_inflow)">{{ formatAmount(item.main_net_inflow) }}</div>
        <div class="rcell c-inflow3" :class="changeClass(item.main_net_inflow_3d)">{{ formatAmount(item.main_net_inflow_3d) }}</div>
        <div class="rcell c-inflow5" :class="changeClass(item.main_net_inflow_5d)">{{ formatAmount(item.main_net_inflow_5d) }}</div>
        <div class="rcell c-inflow10" :class="changeClass(item.main_net_inflow_10d)">{{ formatAmount(item.main_net_inflow_10d) }}</div>
        <div v-if="showScore" class="rcell c-score">{{ formatNumber(item.score, 0) }}</div>
        <div class="rcell c-act">
          <button class="btn btn-ghost btn-sm" type="button" @click="emit('selectStock', item.code)" title="查看详情/K线">详情</button>
          <button class="btn btn-ghost btn-sm" type="button" @click="emit('addWatch', item)">＋自选</button>
          <small v-if="watchMessages[item.code]" class="watch-msg">{{ watchMessages[item.code] }}</small>
        </div>
      </div>
    </div>

    <EmptyState
      v-else
      title="无匹配结果"
      description="放宽条件或更换策略后再试；也可查看该策略近 5 日命中数判断是否当日确实无票。"
    />
  </div>
</template>

<style scoped>
.result-wrap { width: 100%; }
.result-meta {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  margin-bottom: 8px;
}
.warnings {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.warn-item {
  padding: 6px 12px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 6px;
  font-size: 12px;
  color: #fbbf24;
}
.rtable {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-md, 10px);
  overflow-x: auto;
}
.rrow {
  display: grid;
  /* 14 列：code name change close turnover pe mv vr amount 当日 3日 5日 10日 act */
  grid-template-columns: 64px 1fr 64px 60px 60px 72px 84px 48px 80px 72px 72px 72px 72px 108px;
  align-items: center;
  gap: 4px;
}
.rrow.show-score {
  /* 15 列：在 act 前插入 score(52px) */
  grid-template-columns: 64px 1fr 64px 60px 60px 72px 84px 48px 80px 72px 72px 72px 72px 52px 108px;
}
.rhead {
  background: rgba(255, 255, 255, 0.03);
  font-size: 11px;
  color: var(--text-muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  position: sticky;
  top: 0;
  z-index: 1;
}
.rhead .rcell { padding: 8px 6px; }
.rhead .sortable { cursor: pointer; user-select: none; }
.rhead .sortable:hover { color: var(--text, #e2e8f0); }
.rhead .active { color: var(--accent, #06b6d4); }
.sort-arrow { margin-left: 2px; font-size: 9px; opacity: 0.7; }

.rbody {
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.rbody:hover { background: rgba(255, 255, 255, 0.02); }
.rcell { padding: 9px 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-code code { font-family: var(--mono, monospace); color: var(--accent, #06b6d4); cursor: pointer; }
.c-name { color: var(--text, #e2e8f0); }
.c-change, .c-inflow { font-weight: 600; }
.pos { color: var(--up, #f87171); }
.neg { color: var(--down, #34d399); }
.c-act { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.watch-msg { width: 100%; font-size: 10px; color: var(--text-muted, #94a3b8); }

.btn { font: inherit; cursor: pointer; border-radius: 6px; transition: all 0.15s; }
.btn-sm { padding: 3px 8px; font-size: 11px; }
.btn-ghost {
  background: transparent;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
  color: var(--text-secondary, #cbd5e1);
}
.btn-ghost:hover { border-color: var(--accent, #06b6d4); color: var(--accent, #06b6d4); }

@media (max-width: 900px) {
  .rrow { min-width: 760px; }
  .rrow.show-score { min-width: 820px; }
  .c-name { min-width: 80px; }
}
</style>
