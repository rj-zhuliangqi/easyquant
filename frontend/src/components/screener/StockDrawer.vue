<script setup>
import { computed, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import EChartPanel from "../EChartPanel.vue";
import EmptyState from "../ui/EmptyState.vue";
import LoadingSkeleton from "../ui/LoadingSkeleton.vue";
import StatusBadge from "../ui/StatusBadge.vue";
import { fetchScreenerStock } from "../../lib/api";
import { formatAmount, formatNumber, formatPercent } from "../../lib/formatters";

const props = defineProps({
  code: { type: String, default: "" },
});
const emit = defineEmits(["close"]);

const enabled = computed(() => !!props.code);
const detailQuery = useQuery({
  queryKey: computed(() => ["screener-stock", props.code]),
  queryFn: () => fetchScreenerStock(props.code),
  enabled,
  staleTime: 60 * 1000,
});
const detail = computed(() => detailQuery.data.value || null);

// K 线 option：candlestick + 成交量副图。A 股红涨绿跌。
const klineOption = computed(() => {
  const kline = detail.value?.kline || [];
  if (!kline.length) return null;
  const dates = kline.map((k) => k.date);
  // ECharts candlestick: [open, close, low, high]
  const ohlc = kline.map((k) => [k.open, k.close, k.low, k.high]);
  const vols = kline.map((k) => k.volume);
  return {
    animation: false,
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    grid: [
      { left: 50, right: 16, top: 16, height: "58%" },
      { left: 50, right: 16, top: "72%", height: "20%" },
    ],
    xAxis: [
      { type: "category", data: dates, scale: true, boundaryGap: false, splitLine: { show: false }, min: "dataMin", max: "dataMax" },
      { type: "category", gridIndex: 1, data: dates, show: false },
    ],
    yAxis: [
      { scale: true, splitLine: { show: false } },
      { gridIndex: 1, splitNumber: 2, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 40, end: 100 },
      { type: "slider", xAxisIndex: [0, 1], start: 40, end: 100, height: 16, bottom: 4 },
    ],
    series: [
      {
        type: "candlestick",
        data: ohlc,
        itemStyle: {
          color: "#f87171",        // 阳线(涨) 红
          color0: "#34d399",       // 阴线(跌) 绿
          borderColor: "#f87171",
          borderColor0: "#34d399",
        },
      },
      {
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: vols,
        itemStyle: { color: "rgba(148, 163, 184, 0.35)" },
      },
    ],
  };
});

const basics = computed(() => {
  const b = detail.value?.basics || {};
  return [
    { label: "现价", value: formatNumber(b.latest_price) },
    { label: "涨跌幅", value: formatPercent(b.change_pct), cls: changeClass(b.change_pct) },
    { label: "换手率", value: b.turnover_rate != null ? `${formatNumber(b.turnover_rate)}%` : "--" },
    { label: "市盈率", value: formatNumber(b.pe_dynamic) },
    { label: "市净率", value: formatNumber(b.pb) },
    { label: "总市值", value: formatAmount(b.total_mv) },
    { label: "流通市值", value: formatAmount(b.float_mv) },
  ];
});
const indicators = computed(() => {
  const i = detail.value?.indicators || {};
  return [
    { label: "MA20", value: formatNumber(i.ma20) },
    { label: "收盘/MA20", value: formatPercent(i.close_vs_ma20) },
    { label: "5日涨幅", value: formatPercent(i.change_5d), cls: changeClass(i.change_5d) },
    { label: "20日涨幅", value: formatPercent(i.change_20d), cls: changeClass(i.change_20d) },
    { label: "量比", value: formatNumber(i.volume_ratio) },
    { label: "RSI14", value: formatNumber(i.rsi14) },
    { label: "MACD柱", value: formatNumber(i.macd_hist), cls: changeClass(i.macd_hist) },
    { label: "5日主力", value: formatAmount(i.main_net_inflow_5d), cls: changeClass(i.main_net_inflow_5d) },
    { label: "连续流入", value: i.main_net_inflow_days != null ? `${i.main_net_inflow_days}日` : "--" },
    { label: "均线多头", value: i.ma_bullish === 1 ? "是" : i.ma_bullish === 0 ? "否" : "--" },
  ];
});

function changeClass(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return "";
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "";
}

// ESC 关闭
function onKey(e) {
  if (e.key === "Escape") emit("close");
}
watch(
  () => props.code,
  (v) => {
    if (v) window.addEventListener("keydown", onKey);
    else window.removeEventListener("keydown", onKey);
  },
  { immediate: true },
);
</script>

<template>
  <Teleport to="body">
    <transition name="drawer">
      <div v-if="code" class="drawer-mask" @click.self="emit('close')">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-head">
            <div class="dh-title">
              <code>{{ detail?.code || code }}</code>
              <span class="dh-name">{{ detail?.name || "加载中" }}</span>
              <StatusBadge v-if="detail?.basics?.change_pct != null" :status="changeClass(detail.basics.change_pct) === 'neg' ? 'success' : 'danger'" size="sm">
                {{ formatPercent(detail.basics.change_pct) }}
              </StatusBadge>
            </div>
            <button class="dh-close" type="button" @click="emit('close')" aria-label="关闭">×</button>
          </header>

          <div class="drawer-body">
            <LoadingSkeleton v-if="detailQuery.isLoading.value" type="card" :rows="4" />

            <template v-else-if="detail">
              <section class="dsec">
                <h4>近 60 日 K 线</h4>
                <EChartPanel v-if="klineOption" :option="klineOption" />
                <EmptyState v-else title="无 K 线数据" description="该股票尚无日线" />
              </section>

              <section class="dsec">
                <h4>基础面 <small v-if="detail.basics?.data_date">· {{ detail.basics.data_date }}</small></h4>
                <div class="metric-grid">
                  <div v-for="m in basics" :key="m.label" class="metric">
                    <span class="m-label">{{ m.label }}</span>
                    <span class="m-value" :class="m.cls">{{ m.value }}</span>
                  </div>
                </div>
              </section>

              <section class="dsec">
                <h4>关键指标 <small v-if="detail.indicators?.data_date">· {{ detail.indicators.data_date }}</small></h4>
                <div class="metric-grid">
                  <div v-for="m in indicators" :key="m.label" class="metric">
                    <span class="m-label">{{ m.label }}</span>
                    <span class="m-value" :class="m.cls">{{ m.value }}</span>
                  </div>
                </div>
              </section>

              <section class="dsec">
                <h4>近 10 日资金流</h4>
                <div v-if="detail.fund_flow?.length" class="mini-list">
                  <div v-for="f in detail.fund_flow" :key="f.date" class="mini-row">
                    <span class="mr-date">{{ f.date }}</span>
                    <span class="mr-val" :class="changeClass(f.main_net)">{{ formatAmount(f.main_net) }}</span>
                    <span class="mr-sub">{{ formatNumber(f.main_net_ratio) }}%</span>
                  </div>
                </div>
                <EmptyState v-else title="无资金流数据" />
              </section>

              <section class="dsec">
                <h4>近期龙虎榜</h4>
                <div v-if="detail.lhb?.length" class="lhb-list">
                  <div v-for="(l, i) in detail.lhb" :key="i" class="lhb-row">
                    <div class="lr-main">
                      <span class="lr-date">{{ l.date }}</span>
                      <span class="lr-reason">{{ l.reason }}</span>
                    </div>
                    <div class="lr-meta">
                      <span class="lr-net" :class="changeClass(l.net_buy)">{{ formatAmount(l.net_buy) }}</span>
                      <span v-if="l.inst_net_count !== 0" class="lr-inst" :class="changeClass(l.inst_net_count)">
                        机构{{ l.inst_net_count > 0 ? "净买" : "净卖" }} {{ Math.abs(l.inst_net_count) }} 席
                      </span>
                      <span v-if="l.interpretation" class="lr-interp">{{ l.interpretation }}</span>
                    </div>
                  </div>
                </div>
                <EmptyState v-else title="近期未上榜" description="该股票近 30 日无龙虎榜记录" />
              </section>
            </template>
          </div>
        </aside>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(2px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}
.drawer {
  width: min(560px, 92vw);
  height: 100%;
  background: var(--surface, #0f172a);
  border-left: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.4);
}
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s; }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform 0.25s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(40px); }

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.08));
}
.dh-title { display: flex; align-items: center; gap: 10px; }
.dh-title code { font-family: var(--mono, monospace); color: var(--accent, #06b6d4); font-size: 15px; }
.dh-name { font-weight: 600; color: var(--text, #e2e8f0); }
.dh-close {
  background: none; border: none; color: var(--text-muted, #94a3b8);
  font-size: 22px; cursor: pointer; line-height: 1; padding: 4px 8px;
}
.dh-close:hover { color: var(--text, #e2e8f0); }

.drawer-body { flex: 1; overflow-y: auto; padding: 16px 18px 32px; }
.dsec { margin-bottom: 22px; }
.dsec h4 {
  font-size: 13px; color: var(--text-muted, #94a3b8); text-transform: uppercase;
  letter-spacing: 0.05em; margin: 0 0 10px; font-weight: 600;
}
.dsec h4 small { text-transform: none; letter-spacing: 0; color: var(--text-muted, #64748b); font-weight: 400; }

.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; }
.metric {
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04); border-radius: 8px;
}
.m-label { font-size: 11px; color: var(--text-muted, #94a3b8); }
.m-value { font-size: 14px; font-weight: 600; color: var(--text, #e2e8f0); font-variant-numeric: tabular-nums; }

.mini-list, .lhb-list { display: flex; flex-direction: column; gap: 6px; }
.mini-row {
  display: flex; gap: 12px; align-items: center; font-size: 12px;
  padding: 6px 10px; background: rgba(255, 255, 255, 0.02); border-radius: 6px;
}
.mr-date { color: var(--text-muted, #94a3b8); width: 88px; }
.mr-val { font-weight: 600; font-variant-numeric: tabular-nums; margin-left: auto; }
.mr-sub { color: var(--text-muted, #94a3b8); width: 56px; text-align: right; }

.lhb-row {
  padding: 8px 10px; background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04); border-radius: 8px;
}
.lr-main { display: flex; gap: 10px; align-items: center; font-size: 12px; margin-bottom: 4px; }
.lr-date { color: var(--text-muted, #94a3b8); width: 88px; }
.lr-reason { color: var(--text, #e2e8f0); }
.lr-meta { display: flex; gap: 12px; align-items: center; font-size: 11px; flex-wrap: wrap; }
.lr-net { font-weight: 600; font-variant-numeric: tabular-nums; }
.lr-inst { padding: 1px 6px; border-radius: 4px; background: rgba(56, 189, 248, 0.1); }
.lr-interp { color: var(--text-muted, #94a3b8); }

.pos { color: var(--up, #f87171); }
.neg { color: var(--down, #34d399); }
</style>
