const storageKey = "sector-fund-monitor-settings";

const persisted = (() => {
  try {
    return JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    return {};
  }
})();

const state = {
  sectorType: persisted.sectorType === "concept" ? "concept" : "industry",
  metric: persisted.metric === "net_amount" ? "net_amount" : "net_strength",
  granularity: persisted.granularity === "day" ? "day" : "minute",
  lookbackDays: Number(persisted.lookbackDays || 1),
  limit: Number(persisted.limit || 8),
  selectedSector: persisted.selectedSector || null,
  selectedTradingDate: persisted.selectedTradingDate || null,
  availableDates: [],
  watchlistFormType: persisted.watchlistFormType === "concept" ? "concept" : "industry",
  sectorOptions: { industry: [], concept: [] },
  watchlist: [],
  invalidWatchlist: [],
  latestOverview: null,
  comparisonPayload: null,
  signalsPayload: null,
  sectorStocks: { sortBy: "net_amount", sortOrder: "desc", page: 1, pageSize: 10, payload: null, refreshKey: null },
  individual: { sortBy: "net_amount", sortOrder: "desc", page: 1, pageSize: 15, payload: null, refreshKey: null },
};

const comparisonChart = echarts.init(document.getElementById("comparison-chart"));
const detailChart = echarts.init(document.getElementById("detail-chart"));

function saveSettings() {
  localStorage.setItem(
    storageKey,
    JSON.stringify({
      sectorType: state.sectorType,
      metric: state.metric,
      granularity: state.granularity,
      lookbackDays: state.lookbackDays,
      limit: state.limit,
      selectedSector: state.selectedSector,
      selectedTradingDate: state.selectedTradingDate,
      watchlistFormType: state.watchlistFormType,
    })
  );
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail = payload.detail ? ` ${payload.detail}` : "";
    } catch {}
    throw new Error(`Request failed: ${response.status}${detail}`);
  }
  return response.json();
}

function toNumeric(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value ?? "").replace(/,/g, "").replace(/\s+/g, "").trim();
  if (!text) return null;
  const match = text.match(/^([+-]?\d+(?:\.\d+)?)(亿|万|%)?$/);
  if (!match) return null;
  let numeric = Number(match[1]);
  if (!Number.isFinite(numeric)) return null;
  if (match[2] === "万") numeric *= 10000;
  if (match[2] === "亿") numeric *= 100000000;
  return numeric;
}

function formatNumber(value, digits = 2) {
  const numeric = toNumeric(value);
  if (numeric === null) return "--";
  return numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatAmount(value, digits = 2) {
  const numeric = toNumeric(value);
  if (numeric === null) return "--";
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  const abs = Math.abs(numeric);
  if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(digits)}亿`;
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(digits)}万`;
  return `${sign}${abs.toFixed(digits)}`;
}

function formatPercent(value, digits = 2) {
  const numeric = toNumeric(value);
  if (numeric === null) return "--";
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(digits)}%`;
}

function formatMetric(value) {
  if (state.metric === "net_strength") {
    const numeric = typeof value === "number" ? value : toNumeric(value);
    if (numeric === null) return "--";
    return `${numeric > 0 ? "+" : ""}${(numeric * 100).toFixed(2)}%`;
  }
  return formatAmount(value);
}

function pickClass(value) {
  const numeric = typeof value === "number" ? value : toNumeric(value);
  if (numeric === null) return "neutral";
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

function metricLabel() {
  return state.metric === "net_strength" ? "净流入强度" : "净流入绝对值";
}

function metricUnitLabel() {
  return state.metric === "net_strength" ? "%" : "元";
}

function setStatus(text) {
  document.getElementById("status-text").textContent = text;
}

function updatePanelState(elementId, label, kind = "neutral") {
  const node = document.getElementById(elementId);
  node.textContent = label;
  node.dataset.kind = kind;
}

function currentWatchlist() {
  return state.watchlist.filter((item) => item.sectorType === state.sectorType);
}

function isNotFoundError(error) {
  return String(error?.message || "").includes("404");
}

function tradingDateQuery() {
  if (state.granularity !== "minute" || !state.selectedTradingDate) return "";
  return `&trading_date=${encodeURIComponent(state.selectedTradingDate)}`;
}

function syncSectorTabs() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.sectorType === state.sectorType);
  });
}

function syncGranularityControls() {
  document.getElementById("trading-date-control").classList.toggle("hidden", state.granularity !== "minute");
  document.getElementById("lookback-control").classList.toggle("hidden", state.granularity === "minute");
}

function renderTradingDateOptions() {
  const select = document.getElementById("trading-date-select");
  if (!state.availableDates.length) {
    select.innerHTML = '<option value="">暂无历史日期</option>';
    select.value = "";
    return;
  }
  select.innerHTML = state.availableDates.map((item) => `<option value="${item}">${item}</option>`).join("");
  if (!state.selectedTradingDate || !state.availableDates.includes(state.selectedTradingDate)) {
    state.selectedTradingDate = state.availableDates[0];
  }
  select.value = state.selectedTradingDate;
}

function renderWatchlistControls() {
  const typeSelect = document.getElementById("watchlist-type-select");
  const sectorSelect = document.getElementById("watchlist-sector-select");
  typeSelect.value = state.watchlistFormType;
  const options = state.sectorOptions[state.watchlistFormType] || [];
  if (!options.length) {
    sectorSelect.innerHTML = '<option value="">暂无可选板块</option>';
    sectorSelect.value = "";
    return;
  }
  sectorSelect.innerHTML = options.map((item) => `<option value="${item}">${item}</option>`).join("");
}

function renderRankList(elementId, rows, formatter = (row) => formatMetric(row.metric_value)) {
  const container = document.getElementById(elementId);
  if (!rows.length) {
    container.innerHTML = '<div class="empty-state">暂无数据</div>';
    return;
  }
  container.innerHTML = rows
    .map(
      (row) => `
        <button class="rank-item ${row.sector_name === state.selectedSector ? "active" : ""}" data-sector-name="${row.sector_name}">
          <div class="rank-item-header">
            <div class="rank-item-title">${row.sector_name}</div>
            <div class="${pickClass(row.metric_value ?? row.acceleration_1)}">${formatter(row)}</div>
          </div>
          <div class="rank-item-subtitle">${row.net_amount !== undefined ? `净额 ${formatAmount(row.net_amount)} / ` : ""}涨跌幅 ${formatPercent(row.change_percent)}</div>
        </button>
      `
    )
    .join("");

  container.querySelectorAll(".rank-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedSector = button.dataset.sectorName;
      saveSettings();
      highlightSelection();
      await loadSelectedSectorPanels();
    });
  });
}

function renderSignals(items) {
  renderRankList("signals-list", items, (item) => `1分加速度 ${formatMetric(item.acceleration_1)}`);
}

function renderWatchlist() {
  const container = document.getElementById("watchlist-chips");
  if (!state.watchlist.length) {
    container.innerHTML = '<div class="empty-state">暂无自选板块</div>';
    return;
  }

  container.innerHTML = state.watchlist
    .map((item) => {
      const invalid = state.invalidWatchlist.includes(item.sectorName);
      return `
        <div class="chip ${invalid ? "chip-invalid" : ""}">
          <button class="chip-select" data-sector-type="${item.sectorType}" data-sector-name="${item.sectorName}">
            <span class="chip-tag">${item.sectorType === "concept" ? "概念" : "行业"}</span>
            <span>${item.sectorName}</span>
          </button>
          <button class="chip-remove" data-remove-key="${item.sectorType}:${item.sectorName}">×</button>
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".chip-select").forEach((button) => {
    button.addEventListener("click", async () => {
      state.sectorType = button.dataset.sectorType;
      state.selectedSector = button.dataset.sectorName;
      syncSectorTabs();
      saveSettings();
      if (state.granularity === "minute") await loadTradingDates();
      await refreshAll();
    });
  });

  container.querySelectorAll(".chip-remove").forEach((button) => {
    button.addEventListener("click", async () => {
      state.watchlist = state.watchlist.filter((item) => `${item.sectorType}:${item.sectorName}` !== button.dataset.removeKey);
      await persistWatchlist();
      renderWatchlist();
      await loadComparisonSection();
    });
  });
}

function highlightSelection() {
  if (state.latestOverview) {
    renderRankList("leaders-list", state.latestOverview.leaders);
    renderRankList("laggards-list", state.latestOverview.laggards);
  }
  if (state.signalsPayload) {
    renderSignals(state.signalsPayload.items || []);
  }
}

function renderComparisonChart(payload) {
  state.comparisonPayload = payload;
  state.invalidWatchlist = payload.invalid_watchlist || [];
  renderWatchlist();

  document.getElementById("comparison-title").textContent = `全板块${metricLabel()}对比走势`;
  document.getElementById("comparison-subtitle").textContent =
    state.granularity === "minute"
      ? "分钟线按当日首个采样点归一到 0，短缺口会用上一笔有效值补齐。"
      : `最近 ${state.lookbackDays} 个交易日的日级走势。`;

  const badges = [
    `比较口径 ${metricLabel()}`,
    `单位 ${metricUnitLabel()}`,
    state.granularity === "minute" ? `交易日 ${state.selectedTradingDate || "--"}` : `范围 ${state.lookbackDays} 日`,
    `展示 ${payload.series.length} 个板块`,
  ];
  if (payload.missing_labels_count > 0) badges.push(`补齐缺口 ${payload.missing_labels_count} 分钟`);
  document.getElementById("comparison-badges").innerHTML = badges.map((item) => `<span class="badge">${item}</span>`).join("");

  const labels = payload.series[0]?.points.map((point) => point.label) || [];
  const watchlistNames = new Set(currentWatchlist().map((item) => item.sectorName));
  comparisonChart.setOption(
    {
      tooltip: {
        trigger: "axis",
        valueFormatter(value) {
          if (value === null || value === undefined) return "--";
          return state.metric === "net_strength" ? `${(Number(value) * 100).toFixed(2)}%` : formatAmount(value);
        },
      },
      legend: { top: 0 },
      grid: { left: 56, right: 24, top: 52, bottom: 36 },
      xAxis: { type: "category", data: labels },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${(value * 100).toFixed(0)}%` : formatAmount(value);
          },
        },
      },
      series: payload.series.map((series) => {
        const highlighted = series.sector_name === state.selectedSector || watchlistNames.has(series.sector_name);
        return {
          name: series.sector_name,
          type: "line",
          smooth: false,
          connectNulls: false,
          showSymbol: series.sector_name === state.selectedSector,
          lineStyle: { width: highlighted ? 3 : 2, opacity: state.selectedSector && !highlighted ? 0.45 : 0.92 },
          data: series.points.map((point) => point.value),
        };
      }),
    },
    true
  );

  comparisonChart.off("click");
  comparisonChart.on("click", async (params) => {
    if (!params.seriesName) return;
    state.selectedSector = params.seriesName;
    saveSettings();
    highlightSelection();
    await loadSelectedSectorPanels();
  });

  updatePanelState(
    "comparison-state",
    payload.updated_at ? `更新于 ${payload.updated_at.replace("T", " ").slice(0, 16)}` : "暂无数据",
    payload.updated_at ? "fresh" : "warning"
  );
}

function findSelectedSignal() {
  return (state.signalsPayload?.items || []).find((item) => item.sector_name === state.selectedSector) || null;
}

function renderMetricGrid(elementId, items, emptyText) {
  const container = document.getElementById(elementId);
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">${emptyText}</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="metric-tile">
          <div class="metric-label">${item.label}</div>
          <div class="metric-value ${item.className || ""}">${item.value}</div>
        </div>
      `
    )
    .join("");
}

function renderSignalStack(elementId, items, emptyText) {
  const container = document.getElementById(elementId);
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">${emptyText}</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="signal-pill ${item.kind || "neutral"}">
          <div class="signal-title">${item.title}</div>
          <div class="signal-text">${item.text}</div>
        </div>
      `
    )
    .join("");
}

function buildStructureMetrics(payload) {
  const rows = payload?.stocks || [];
  const validNet = rows.map((row) => toNumeric(row["今日主力净流入-净额"])).filter((value) => value !== null);
  const validChange = rows.map((row) => toNumeric(row["今日涨跌幅"])).filter((value) => value !== null);
  const positiveCount = validNet.filter((value) => value > 0).length;
  const negativeCount = validNet.filter((value) => value < 0).length;
  const risingCount = validChange.filter((value) => value > 0).length;
  const top3 = validNet.slice(0, 3).reduce((sum, value) => sum + value, 0);
  const totalPositive = validNet.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const concentration = totalPositive > 0 ? top3 / totalPositive : 0;

  const metrics = [
    { label: "已缓存成分股", value: `${payload?.total || 0} 只` },
    { label: "净流入为正", value: `${positiveCount} 只`, className: positiveCount > negativeCount ? "positive" : "neutral" },
    { label: "净流出为负", value: `${negativeCount} 只`, className: negativeCount > positiveCount ? "negative" : "neutral" },
    { label: "上涨家数", value: `${risingCount} 只`, className: risingCount > 0 ? "positive" : "neutral" },
    { label: "前3集中度", value: `${(concentration * 100).toFixed(1)}%`, className: concentration >= 0.6 ? "warning-text" : "" },
    { label: "缓存状态", value: payload?.source_status || "--" },
  ];

  const notes = [];
  if (concentration >= 0.7) {
    notes.push({ title: "龙头集中", text: "前3只成分股占了大部分主力净流入，说明更像龙头单拉。", kind: "warning" });
  } else if (positiveCount >= 5) {
    notes.push({ title: "板块共振", text: "净流入为正的成分股较多，说明板块内部扩散更充分。", kind: "good" });
  } else {
    notes.push({ title: "结构一般", text: "当前成分股的扩散度一般，建议结合分钟趋势一起看。", kind: "neutral" });
  }

  return { metrics, notes };
}

function renderAnalysisPanel(payload) {
  const detail = payload.detail;
  const history = payload.history || { points: [] };
  const signal = findSelectedSignal();

  if (!detail) {
    document.getElementById("analysis-title").textContent = "板块分析区";
    document.getElementById("analysis-subtitle").textContent = "当前板块没有命中有效快照。";
    document.getElementById("analysis-summary-meta").textContent = "未命中结构化快照";
    document.getElementById("analysis-signal-meta").textContent = "暂无信号";
    document.getElementById("analysis-structure-meta").textContent = "暂无结构数据";
    renderMetricGrid("analysis-summary", [], "未找到该板块的结构化快照");
    renderSignalStack("analysis-signals", [], "先从左侧选择一个有数据的板块");
    renderMetricGrid("analysis-structure", [], "等待成分股缓存");
    renderSignalStack("analysis-structure-notes", [], "暂无说明");
    updatePanelState("detail-state", "不可用", "warning");
  } else {
    document.getElementById("analysis-title").textContent = `${detail.sector_name} 分析区`;
    document.getElementById("analysis-subtitle").textContent = "把摘要、信号、趋势和成分股结构放在一起，减少重复信息。";
    document.getElementById("analysis-summary-meta").textContent = `采样于 ${detail.captured_at ? detail.captured_at.replace("T", " ").slice(0, 16) : "--"}`;
    document.getElementById("analysis-signal-meta").textContent = signal ? "已命中实时信号" : "暂无独立信号";

    renderMetricGrid(
      "analysis-summary",
      [
        { label: "净流入", value: formatAmount(detail.net_amount), className: pickClass(detail.net_amount) },
        { label: "净流入强度", value: formatPercent(Number(detail.net_strength) * 100), className: pickClass(detail.net_strength) },
        { label: "涨跌幅", value: formatPercent(detail.change_percent), className: pickClass(detail.change_percent) },
        { label: "流入资金", value: formatAmount(detail.inflow) },
        { label: "流出资金", value: formatAmount(detail.outflow) },
        { label: "领涨股", value: detail.leading_stock || "--" },
      ],
      "暂无摘要"
    );

    const signalCards = [];
    if (signal) {
      signalCards.push(
        { title: "1分钟加速度", text: formatMetric(signal.acceleration_1), kind: pickClass(signal.acceleration_1) === "positive" ? "good" : pickClass(signal.acceleration_1) === "negative" ? "warning" : "neutral" },
        { title: "3分钟加速度", text: formatMetric(signal.acceleration_3), kind: pickClass(signal.acceleration_3) === "positive" ? "good" : pickClass(signal.acceleration_3) === "negative" ? "warning" : "neutral" },
        { title: "持续性", text: `连续 ${signal.persistence} 个采样点`, kind: "neutral" },
        {
          title: "资金/价格关系",
          text: signal.divergence === "aligned" ? "资金和价格方向一致" : signal.divergence === "bullish_flow_vs_price" ? "资金偏强但价格偏弱" : "价格偏强但资金偏弱",
          kind: signal.divergence === "aligned" ? "good" : "warning",
        }
      );
    }
    renderSignalStack("analysis-signals", signalCards, "当前没有独立信号，先看分钟趋势和成分股结构。");
    updatePanelState("detail-state", `更新于 ${detail.captured_at.replace("T", " ").slice(0, 16)}`, "fresh");
  }

  document.getElementById("history-title").textContent = `${payload.resolved_sector_name || state.selectedSector || "板块"} 分钟趋势`;
  document.getElementById("history-subtitle").textContent =
    state.granularity === "minute"
      ? `分钟级 ${metricLabel()}，交易日 ${state.selectedTradingDate || "--"}。`
      : `日级 ${metricLabel()}，范围 ${state.lookbackDays} 日。`;

  detailChart.setOption(
    {
      tooltip: {
        trigger: "axis",
        valueFormatter(value) {
          if (value === null || value === undefined) return "--";
          return state.metric === "net_strength" ? `${(Number(value) * 100).toFixed(2)}%` : formatAmount(value);
        },
      },
      grid: { left: 56, right: 24, top: 24, bottom: 32 },
      xAxis: { type: "category", data: history.points.map((point) => point.label) },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${(value * 100).toFixed(0)}%` : formatAmount(value);
          },
        },
      },
      series: [
        {
          type: "line",
          smooth: false,
          connectNulls: false,
          areaStyle: { opacity: 0.08 },
          data: history.points.map((point) => point.value),
        },
      ],
    },
    true
  );
  updatePanelState("history-state", history.points.length ? `共 ${history.points.length} 个点` : "暂无曲线", history.points.length ? "fresh" : "warning");
}

function renderTableRows(elementId, rows, fields) {
  const body = document.getElementById(elementId);
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">暂无数据</td></tr>';
    return;
  }
  body.innerHTML = rows
    .map(
      (row) => `
        <tr>
          ${fields
            .map((field) => {
              const value = row[field.key];
              const cls = field.className ? field.className(value) : "";
              const text = field.format ? field.format(value) : value ?? "--";
              return `<td class="${cls}">${text}</td>`;
            })
            .join("")}
        </tr>
      `
    )
    .join("");
}

function updatePagination(prefix, payload) {
  const totalPages = Math.max(Math.ceil((payload.total || 0) / (payload.page_size || 1)), 1);
  document.getElementById(`${prefix}-pagination`).textContent = `共 ${payload.total || 0} 条，第 ${payload.page || 1} / ${totalPages} 页`;
  document.getElementById(`${prefix}-prev`).disabled = (payload.page || 1) <= 1;
  document.getElementById(`${prefix}-next`).disabled = (payload.page || 1) >= totalPages;
}

async function loadOverviewSection() {
  const [overview, status] = await Promise.all([
    fetchJson(`/api/overview?sector_type=${state.sectorType}&metric=${state.metric}&limit=${state.limit}${tradingDateQuery()}`),
    fetchJson("/api/status"),
  ]);
  state.latestOverview = overview;
  if (!state.selectedSector) {
    state.selectedSector = overview.leaders[0]?.sector_name || overview.laggards[0]?.sector_name || null;
  }
  renderRankList("leaders-list", overview.leaders);
  renderRankList("laggards-list", overview.laggards);
  const marketLabel = status.market_open ? "交易中" : "非交易时段";
  const snapshotLabel = overview.updated_at ? overview.updated_at.replace("T", " ").slice(0, 16) : "暂无";
  setStatus(`${marketLabel} | 最近采样 ${snapshotLabel} | 自选预采样 ${status.watched_sector_count} 个`);
}

async function loadSignalsSection() {
  const payload = await fetchJson(`/api/monitor-signals?sector_type=${state.sectorType}&metric=${state.metric}&limit=8${tradingDateQuery()}`);
  state.signalsPayload = payload;
  renderSignals(payload.items || []);
}

async function loadComparisonSection() {
  const include = currentWatchlist()
    .map((item) => item.sectorName)
    .join(",");
  const payload = await fetchJson(
    `/api/comparison?sector_type=${state.sectorType}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}&limit=${state.limit}&include_sectors=${encodeURIComponent(include)}${tradingDateQuery()}`
  );
  renderComparisonChart(payload);
}

async function loadWorkspaceSection() {
  if (!state.selectedSector) {
    renderAnalysisPanel({ detail: null, history: { points: [] }, resolved_sector_name: null });
    return;
  }
  updatePanelState("detail-state", "加载中", "neutral");
  updatePanelState("history-state", "加载中", "neutral");
  try {
    const payload = await fetchJson(
      `/api/sector-workspace?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}${tradingDateQuery()}`
    );
    renderAnalysisPanel(payload);
  } catch (error) {
    renderAnalysisPanel({ detail: null, history: { points: [] }, resolved_sector_name: null });
    updatePanelState("detail-state", "读取失败", "warning");
    updatePanelState("history-state", "读取失败", "warning");
  }
}

function refreshAnalysisStructure() {
  const structure = buildStructureMetrics(state.sectorStocks.payload);
  document.getElementById("analysis-structure-meta").textContent = state.sectorStocks.payload?.updated_at
    ? `更新于 ${state.sectorStocks.payload.updated_at.replace("T", " ").slice(0, 16)}`
    : "暂无成分股结构";
  renderMetricGrid("analysis-structure", structure.metrics, "等待成分股缓存");
  renderSignalStack("analysis-structure-notes", structure.notes, "暂无说明");
}

async function loadSectorStocksSection(forceRefresh = false) {
  if (!state.selectedSector) {
    renderTableRows("sector-stocks-body", [], []);
    state.sectorStocks.payload = null;
    refreshAnalysisStructure();
    updatePanelState("sector-stocks-state", "未选择", "neutral");
    return;
  }
  updatePanelState("sector-stocks-state", forceRefresh ? "刷新中" : "加载中", "neutral");
  const query = new URLSearchParams({
    sector_type: state.sectorType,
    sector_name: state.selectedSector,
    force_refresh: String(forceRefresh),
    sort_by: state.sectorStocks.sortBy,
    sort_order: state.sectorStocks.sortOrder,
    page: String(state.sectorStocks.page),
    page_size: String(state.sectorStocks.pageSize),
  });
  if (state.granularity === "minute" && state.selectedTradingDate) {
    query.set("trading_date", state.selectedTradingDate);
  }
  const payload = await fetchJson(`/api/sector-stocks?${query.toString()}`);
  state.sectorStocks.payload = payload;
  document.getElementById("sector-stocks-meta").textContent = `${payload.source_status === "stale_cache" ? "读取旧缓存" : payload.source_status === "fetched" ? "刷新成功" : payload.source_status === "cache_hit" ? "读取缓存" : "当前不可用"} | 更新时间 ${payload.updated_at ? payload.updated_at.replace("T", " ").slice(0, 16) : "--"}`;
  const fields = [
    { key: "代码" },
    { key: "名称" },
    { key: "最新价", format: formatNumber },
    { key: "今日涨跌幅", format: formatPercent, className: pickClass },
    { key: "今日主力净流入-净额", format: formatAmount, className: pickClass },
  ];
  renderTableRows("sector-stocks-body", payload.stocks || [], fields);
  updatePagination("sector-stocks", payload);
  updatePanelState("sector-stocks-state", payload.source_status === "unavailable" ? "不可用" : payload.source_status, payload.source_status === "unavailable" ? "warning" : "fresh");
  refreshAnalysisStructure();
  if (payload.refresh_recommended && !forceRefresh && state.granularity === "minute") {
    triggerSectorStocksBackgroundRefresh();
  }
}

async function loadIndividualSection(forceRefresh = false) {
  updatePanelState("individual-state", forceRefresh ? "刷新中" : "加载中", "neutral");
  const query = new URLSearchParams({
    limit: "0",
    force_refresh: String(forceRefresh),
    sort_by: state.individual.sortBy,
    sort_order: state.individual.sortOrder,
    page: String(state.individual.page),
    page_size: String(state.individual.pageSize),
  });
  if (state.granularity === "minute" && state.selectedTradingDate) {
    query.set("trading_date", state.selectedTradingDate);
  }
  const payload = await fetchJson(`/api/individual-rankings?${query.toString()}`);
  state.individual.payload = payload;
  document.getElementById("individual-meta").textContent = `${payload.source_status === "stale_cache" ? "读取旧缓存" : payload.source_status === "fetched" ? "刷新成功" : payload.source_status === "cache_hit" ? "读取缓存" : "当前不可用"} | 更新时间 ${payload.updated_at ? payload.updated_at.replace("T", " ").slice(0, 16) : "--"}`;
  const fields = [
    { key: "股票代码" },
    { key: "股票简称" },
    { key: "最新价", format: formatNumber },
    { key: "涨跌幅", format: formatPercent, className: pickClass },
    { key: "净额", format: formatAmount, className: pickClass },
  ];
  renderTableRows("individual-body", payload.stocks || [], fields);
  updatePagination("individual", payload);
  updatePanelState("individual-state", payload.source_status === "unavailable" ? "不可用" : payload.source_status, payload.source_status === "unavailable" ? "warning" : "fresh");
  if (payload.refresh_recommended && !forceRefresh && state.granularity === "minute") {
    triggerIndividualBackgroundRefresh();
  }
}

async function loadTradingDates() {
  try {
    const payload = await fetchJson(`/api/trading-dates?sector_type=${state.sectorType}`);
    state.availableDates = payload.dates || [];
    if (!state.selectedTradingDate || !state.availableDates.includes(state.selectedTradingDate)) {
      state.selectedTradingDate = state.availableDates[0] || null;
    }
  } catch (error) {
    if (!isNotFoundError(error)) throw error;
    state.availableDates = [];
    state.selectedTradingDate = null;
  }
  renderTradingDateOptions();
}

async function loadSectorOptions(sectorType, force = false) {
  if (!force && state.sectorOptions[sectorType]?.length) {
    renderWatchlistControls();
    return;
  }
  const normalize = (items) => [...new Set((items || []).map((item) => String(item || "").trim()).filter(Boolean))];
  try {
    const payload = await fetchJson(`/api/sector-catalog?sector_type=${sectorType}`);
    state.sectorOptions[sectorType] = normalize(payload.sectors || []);
  } catch (error) {
    if (!isNotFoundError(error)) throw error;
    const payload = await fetchJson(`/api/sectors?sector_type=${sectorType}`).catch(() => ({ sectors: [] }));
    state.sectorOptions[sectorType] = normalize(payload.sectors || []);
  }
  renderWatchlistControls();
}

async function persistWatchlist() {
  const payload = state.watchlist.map((item) => ({ sector_type: item.sectorType, sector_name: item.sectorName }));
  try {
    const response = await fetchJson("/api/watchlist", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.watchlist = (response.items || []).map((item) => ({ sectorType: item.sector_type, sectorName: item.sector_name }));
  } catch (error) {
    console.error(error);
  }
}

async function loadWatchlist() {
  try {
    const payload = await fetchJson("/api/watchlist");
    state.watchlist = (payload.items || []).map((item) => ({ sectorType: item.sector_type, sectorName: item.sector_name }));
  } catch (error) {
    console.error(error);
    state.watchlist = [];
  }
  renderWatchlist();
}

async function refreshNow() {
  const button = document.getElementById("refresh-button");
  button.disabled = true;
  button.textContent = "采样中...";
  try {
    await fetchJson("/api/refresh", { method: "POST" });
    if (state.granularity === "minute") await loadTradingDates();
    await refreshAll();
  } finally {
    button.disabled = false;
    button.textContent = "立即采样";
  }
}

async function refreshAll() {
  await Promise.all([loadOverviewSection(), loadSignalsSection(), loadComparisonSection()]);
  await Promise.all([loadWorkspaceSection(), loadSectorStocksSection(), loadIndividualSection()]);
}

async function loadSelectedSectorPanels() {
  await Promise.allSettled([loadWorkspaceSection(), loadSectorStocksSection()]);
}

function triggerSectorStocksBackgroundRefresh() {
  const refreshKey = `${state.sectorType}:${state.selectedSector}:${state.selectedTradingDate || "latest"}:${state.sectorStocks.page}:${state.sectorStocks.pageSize}:${state.sectorStocks.sortBy}:${state.sectorStocks.sortOrder}`;
  if (state.sectorStocks.refreshKey === refreshKey) return;
  state.sectorStocks.refreshKey = refreshKey;
  loadSectorStocksSection(true)
    .catch(console.error)
    .finally(() => {
      if (state.sectorStocks.refreshKey === refreshKey) state.sectorStocks.refreshKey = null;
    });
}

function triggerIndividualBackgroundRefresh() {
  const refreshKey = `${state.selectedTradingDate || "latest"}:${state.individual.page}:${state.individual.pageSize}:${state.individual.sortBy}:${state.individual.sortOrder}`;
  if (state.individual.refreshKey === refreshKey) return;
  state.individual.refreshKey = refreshKey;
  loadIndividualSection(true)
    .catch(console.error)
    .finally(() => {
      if (state.individual.refreshKey === refreshKey) state.individual.refreshKey = null;
    });
}

async function addWatchlist() {
  const sectorName = document.getElementById("watchlist-sector-select").value;
  if (!sectorName) return;
  const next = { sectorType: state.watchlistFormType, sectorName };
  if (!state.watchlist.some((item) => item.sectorType === next.sectorType && item.sectorName === next.sectorName)) {
    state.watchlist.push(next);
    await persistWatchlist();
    renderWatchlist();
    if (state.sectorType === next.sectorType) await loadComparisonSection();
  }
}

function bindControls() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.sectorType = button.dataset.sectorType;
      syncSectorTabs();
      saveSettings();
      if (state.granularity === "minute") await loadTradingDates();
      await refreshAll();
    });
  });

  document.getElementById("granularity-select").value = state.granularity;
  document.getElementById("metric-select").value = state.metric;
  document.getElementById("limit-select").value = String(state.limit);
  document.getElementById("lookback-select").value = String(state.lookbackDays);
  document.getElementById("granularity-select").addEventListener("change", async (event) => {
    state.granularity = event.target.value;
    syncGranularityControls();
    saveSettings();
    if (state.granularity === "minute") await loadTradingDates();
    await refreshAll();
  });
  document.getElementById("trading-date-select").addEventListener("change", async (event) => {
    state.selectedTradingDate = event.target.value || null;
    saveSettings();
    await refreshAll();
  });
  document.getElementById("lookback-select").addEventListener("change", async (event) => {
    state.lookbackDays = Number(event.target.value);
    saveSettings();
    await refreshAll();
  });
  document.getElementById("metric-select").addEventListener("change", async (event) => {
    state.metric = event.target.value;
    saveSettings();
    await refreshAll();
  });
  document.getElementById("limit-select").addEventListener("change", async (event) => {
    state.limit = Number(event.target.value);
    saveSettings();
    await refreshAll();
  });

  document.getElementById("watchlist-type-select").addEventListener("change", async (event) => {
    state.watchlistFormType = event.target.value;
    saveSettings();
    await loadSectorOptions(state.watchlistFormType, true);
  });
  document.getElementById("watchlist-add-button").addEventListener("click", addWatchlist);
  document.getElementById("refresh-button").addEventListener("click", refreshNow);

  document.getElementById("sector-stocks-sort-by").addEventListener("change", async (event) => {
    state.sectorStocks.sortBy = event.target.value;
    state.sectorStocks.page = 1;
    await loadSectorStocksSection();
  });
  document.getElementById("sector-stocks-sort-order").addEventListener("change", async (event) => {
    state.sectorStocks.sortOrder = event.target.value;
    state.sectorStocks.page = 1;
    await loadSectorStocksSection();
  });
  document.getElementById("sector-stocks-page-size").addEventListener("change", async (event) => {
    state.sectorStocks.pageSize = Number(event.target.value);
    state.sectorStocks.page = 1;
    await loadSectorStocksSection();
  });
  document.getElementById("sector-stocks-prev").addEventListener("click", async () => {
    state.sectorStocks.page = Math.max(1, state.sectorStocks.page - 1);
    await loadSectorStocksSection();
  });
  document.getElementById("sector-stocks-next").addEventListener("click", async () => {
    state.sectorStocks.page += 1;
    await loadSectorStocksSection();
  });

  document.getElementById("individual-sort-by").addEventListener("change", async (event) => {
    state.individual.sortBy = event.target.value;
    state.individual.page = 1;
    await loadIndividualSection();
  });
  document.getElementById("individual-sort-order").addEventListener("change", async (event) => {
    state.individual.sortOrder = event.target.value;
    state.individual.page = 1;
    await loadIndividualSection();
  });
  document.getElementById("individual-page-size").addEventListener("change", async (event) => {
    state.individual.pageSize = Number(event.target.value);
    state.individual.page = 1;
    await loadIndividualSection();
  });
  document.getElementById("individual-prev").addEventListener("click", async () => {
    state.individual.page = Math.max(1, state.individual.page - 1);
    await loadIndividualSection();
  });
  document.getElementById("individual-next").addEventListener("click", async () => {
    state.individual.page += 1;
    await loadIndividualSection();
  });
}

async function boot() {
  bindControls();
  syncSectorTabs();
  syncGranularityControls();
  await loadWatchlist();
  await loadTradingDates().catch(console.error);
  await Promise.all([loadSectorOptions("industry", true), loadSectorOptions("concept", true)]);
  await refreshAll();
  setInterval(async () => {
    try {
      if (state.granularity === "minute") await loadTradingDates();
      await refreshAll();
    } catch (error) {
      console.error(error);
      setStatus("自动刷新失败，请检查后端服务。");
    }
  }, 60000);
}

boot().catch((error) => {
  console.error(error);
  setStatus("加载失败，请检查后端服务。");
});
