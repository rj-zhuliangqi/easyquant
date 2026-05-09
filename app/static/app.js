const storageKey = "sector-fund-monitor-settings";

const persisted = (() => {
  try {
    return JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    return {};
  }
})();

const state = {
  sectorType: "industry",
  metric: "net_strength",
  granularity: "minute",
  lookbackDays: 1,
  limit: 8,
  selectedSector: null,
  selectedTradingDate: null,
  availableDates: [],
  watchlistFormType: "industry",
  sectorOptions: { industry: [], concept: [] },
  deltaThreshold: persisted.deltaThreshold ?? 1.5,
  rankThreshold: persisted.rankThreshold ?? 2,
  watchlist: normalizeWatchlist(persisted.watchlist),
  latestOverview: null,
  latestAlerts: null,
  latestStatus: null,
  latestIndividuals: null,
  latestWorkspace: null,
  tradingDateApiEnabled: true,
  tables: {
    sectorStocks: {
      sortBy: persisted.sectorStocksSortBy ?? "net_amount",
      sortOrder: persisted.sectorStocksSortOrder ?? "desc",
      page: 1,
      pageSize: persisted.sectorStocksPageSize ?? 10,
      total: 0,
    },
    individuals: {
      sortBy: persisted.individualSortBy ?? "net_amount",
      sortOrder: persisted.individualSortOrder ?? "desc",
      page: 1,
      pageSize: persisted.individualPageSize ?? 15,
      total: 0,
      fetchLimit: 0,
    },
  },
};

const comparisonChart = echarts.init(document.getElementById("comparison-chart"));
const detailChart = echarts.init(document.getElementById("detail-chart"));

const sectorStockFields = [
  { key: "代码" },
  { key: "名称" },
  { key: "最新价", format: (value) => formatNumber(value) },
  { key: "今日涨跌幅", format: (value) => formatPercent(value), cls: pickClass },
  { key: "今日主力净流入-净额", format: (value) => formatAmountCompact(value), cls: pickClass },
];

const individualStockFields = [
  { key: "股票代码" },
  { key: "股票简称" },
  { key: "最新价", format: (value) => formatNumber(value) },
  { key: "涨跌幅", format: (value) => formatPercent(value), cls: pickClass },
  { key: "净额", format: (value) => formatAmountCompact(value), cls: pickClass },
];

function normalizeWatchlist(raw) {
  if (!Array.isArray(raw)) return [];
  const seen = new Set();
  return raw
    .map((item) => {
      if (typeof item === "string") {
        return { sectorType: "industry", sectorName: item.trim() };
      }
      if (!item || typeof item !== "object") return null;
      const sectorName = String(item.sectorName || item.name || "").trim();
      if (!sectorName) return null;
      return {
        sectorType: item.sectorType === "concept" ? "concept" : "industry",
        sectorName,
      };
    })
    .filter(Boolean)
    .filter((item) => {
      const key = `${item.sectorType}:${item.sectorName}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function saveSettings() {
  localStorage.setItem(
    storageKey,
    JSON.stringify({
      deltaThreshold: state.deltaThreshold,
      rankThreshold: state.rankThreshold,
      watchlist: state.watchlist,
      sectorStocksSortBy: state.tables.sectorStocks.sortBy,
      sectorStocksSortOrder: state.tables.sectorStocks.sortOrder,
      sectorStocksPageSize: state.tables.sectorStocks.pageSize,
      individualSortBy: state.tables.individuals.sortBy,
      individualSortOrder: state.tables.individuals.sortOrder,
      individualPageSize: state.tables.individuals.pageSize,
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
    } catch {
      detail = "";
    }
    throw new Error(`Request failed: ${response.status}${detail}`);
  }
  return response.json();
}

function toNumeric(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value ?? "").replace(/,/g, "").replace(/\s+/g, "").trim();
  if (!text || text === "--") return null;
  const match = text.match(/^([+-]?\d+(?:\.\d+)?)(万|亿|%)?$/);
  if (!match) return null;
  let numeric = Number(match[1]);
  if (!Number.isFinite(numeric)) return null;
  if (match[2] === "万") numeric *= 10000;
  if (match[2] === "亿") numeric *= 100000000;
  return numeric;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  if (numeric === null) return String(value);
  return numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatPercent(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  if (numeric === null) return String(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits })}%`;
}

function formatAmountCompact(value, options = {}) {
  const { signed = false, assumeYi = false } = options;
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  if (numeric === null) return String(value);

  const prefix = signed && numeric > 0 ? "+" : "";
  if (assumeYi) {
    return `${prefix}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}亿`;
  }

  const abs = Math.abs(numeric);
  if (abs >= 100000000) {
    return `${prefix}${(numeric / 100000000).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}亿`;
  }
  if (abs >= 10000) {
    return `${prefix}${(numeric / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}万`;
  }
  return `${prefix}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
}

function formatMetric(value) {
  return state.metric === "net_strength"
    ? formatPercent(Number(value) * 100)
    : formatAmountCompact(value, { signed: true, assumeYi: true });
}

function pickClass(value) {
  const numeric = toNumeric(value);
  if (numeric === null) return "neutral";
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

function metricLabel() {
  return state.metric === "net_strength" ? "净流入强度" : "净流入绝对值";
}

function metricUnitLabel() {
  return state.metric === "net_strength" ? "%" : "亿元";
}

function sectorTypeLabel(sectorType) {
  return sectorType === "concept" ? "概念" : "行业";
}

function currentWatchlist() {
  return state.watchlist.filter((item) => item.sectorType === state.sectorType);
}

function tradingDateQuery() {
  if (state.granularity !== "minute" || !state.tradingDateApiEnabled || !state.selectedTradingDate) {
    return "";
  }
  return `&trading_date=${encodeURIComponent(state.selectedTradingDate)}`;
}

function syncSectorTabs() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.sectorType === state.sectorType);
  });
}

function syncGranularityControls() {
  document.getElementById("trading-date-control").classList.toggle("hidden", state.granularity !== "minute" || !state.tradingDateApiEnabled);
  document.getElementById("lookback-control").classList.toggle("hidden", state.granularity === "minute");
}

function renderTradingDateOptions() {
  const select = document.getElementById("trading-date-select");
  if (!state.availableDates.length) {
    select.innerHTML = '<option value="">暂无历史日期</option>';
    return;
  }
  select.innerHTML = state.availableDates.map((item) => `<option value="${item}">${item}</option>`).join("");
  if (!state.selectedTradingDate || !state.availableDates.includes(state.selectedTradingDate)) {
    state.selectedTradingDate = state.availableDates[0];
  }
  select.value = state.selectedTradingDate;
}

function setStatusText() {
  const marketLabel = state.latestStatus?.market_open ? "交易时段" : "非交易时段";
  const snapshotLabel = state.latestOverview?.updated_at ? state.latestOverview.updated_at.replace("T", " ").slice(0, 16) : "--";
  const scopeLabel =
    state.granularity === "minute" ? `交易日 ${state.selectedTradingDate || "--"}` : `近 ${state.lookbackDays} 个交易日`;
  document.getElementById("status-text").textContent = `${marketLabel} | 最近采样 ${snapshotLabel} | ${scopeLabel}`;
}

function renderWatchlistControls() {
  const typeSelect = document.getElementById("watchlist-type-select");
  const sectorSelect = document.getElementById("watchlist-sector-select");
  typeSelect.value = state.watchlistFormType;
  const options = state.sectorOptions[state.watchlistFormType] || [];
  if (!options.length) {
    sectorSelect.innerHTML = '<option value="">暂无可选板块</option>';
    return;
  }
  sectorSelect.innerHTML = options.map((item) => `<option value="${item}">${item}</option>`).join("");
}

function renderWatchlist() {
  const container = document.getElementById("watchlist-chips");
  if (!state.watchlist.length) {
    container.innerHTML = '<div class="empty-state">暂无自选板块</div>';
    return;
  }

  container.innerHTML = state.watchlist
    .map(
      (item) => `
        <div class="chip">
          <button class="chip-select" data-sector-type="${item.sectorType}" data-sector-name="${item.sectorName}">
            <span class="chip-tag">${sectorTypeLabel(item.sectorType)}</span>
            <span>${item.sectorName}</span>
          </button>
          <button class="chip-remove" data-remove-key="${item.sectorType}:${item.sectorName}">×</button>
        </div>
      `
    )
    .join("");

  container.querySelectorAll(".chip-select").forEach((button) => {
    button.addEventListener("click", async () => {
      await setSectorType(button.dataset.sectorType, button.dataset.sectorName);
    });
  });

  container.querySelectorAll(".chip-remove").forEach((button) => {
    button.addEventListener("click", async () => {
      state.watchlist = state.watchlist.filter((item) => `${item.sectorType}:${item.sectorName}` !== button.dataset.removeKey);
      saveSettings();
      renderWatchlist();
      await loadComparisonSection();
    });
  });
}

function renderRankList(elementId, rows) {
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
            <div class="${pickClass(row.metric_value)}">${formatMetric(row.metric_value)}</div>
          </div>
          <div class="rank-item-subtitle">净额 ${formatAmountCompact(row.net_amount, { signed: true, assumeYi: true })} / 涨跌幅 ${formatPercent(row.change_percent)}</div>
        </button>
      `
    )
    .join("");

  container.querySelectorAll(".rank-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedSector = button.dataset.sectorName;
      state.tables.sectorStocks.page = 1;
      highlightSelection();
      await loadWorkspaceSection();
    });
  });
}

function renderAlerts(items) {
  const container = document.getElementById("alerts-list");
  const filtered = items.filter(
    (item) => Math.abs(Number(item.delta_value) * 100) >= state.deltaThreshold && Math.abs(Number(item.rank_change)) >= state.rankThreshold
  );

  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">当前阈值下暂无明显异动</div>';
    return;
  }

  container.innerHTML = filtered
    .map(
      (item) => `
        <button class="rank-item ${item.sector_name === state.selectedSector ? "active" : ""}" data-sector-name="${item.sector_name}">
          <div class="rank-item-header">
            <div class="rank-item-title">${item.sector_name}</div>
            <div class="${pickClass(item.delta_value)}">${formatPercent(Number(item.delta_value) * 100)}</div>
          </div>
          <div class="rank-item-subtitle">排名变化 ${item.rank_change > 0 ? "+" : ""}${item.rank_change}</div>
        </button>
      `
    )
    .join("");

  container.querySelectorAll(".rank-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedSector = button.dataset.sectorName;
      state.tables.sectorStocks.page = 1;
      highlightSelection();
      await loadWorkspaceSection();
    });
  });
}

function highlightSelection() {
  if (state.latestOverview) {
    renderRankList("leaders-list", state.latestOverview.leaders);
    renderRankList("laggards-list", state.latestOverview.laggards);
  }
  if (state.latestAlerts) {
    renderAlerts(state.latestAlerts.items);
  }
}

function comparisonValueFormatter(point) {
  if (state.metric === "net_strength") {
    return formatPercent(Number(point.value) * 100);
  }
  return formatAmountCompact(point.value, { signed: true, assumeYi: true });
}

function renderComparisonChart(payload) {
  document.getElementById("comparison-title").textContent = `板块${metricLabel()}对比走势`;
  document.getElementById("comparison-subtitle").textContent =
    state.granularity === "minute" ? "分钟线仅保留交易时段数据，并以当日首个采样点归一化到 0。" : `展示近 ${state.lookbackDays} 个交易日的板块走势。`;

  document.getElementById("comparison-badges").innerHTML = `
    <span class="badge">口径 ${metricLabel()}</span>
    <span class="badge">单位 ${metricUnitLabel()}</span>
    <span class="badge">粒度 ${state.granularity === "minute" ? "分钟" : "天级"}</span>
    <span class="badge">${state.granularity === "minute" ? `交易日 ${state.selectedTradingDate || "--"}` : `近 ${state.lookbackDays} 日`}</span>
    <span class="badge">显示 ${state.limit === 0 ? "全部" : state.limit} 个板块</span>
  `;

  const labels = [...new Set(payload.series.flatMap((series) => series.points.map((point) => point.label)))];
  const watchlistNames = currentWatchlist().map((item) => item.sectorName);

  comparisonChart.setOption(
    {
      tooltip: {
        trigger: "axis",
        formatter(params) {
          if (!params.length) return "";
          const title = params[0].axisValueLabel;
          const lines = params.map((item) => `${item.marker}${item.seriesName} ${comparisonValueFormatter({ value: item.data })}`);
          return [title, ...lines].join("<br/>");
        },
      },
      legend: { top: 0 },
      grid: { left: 64, right: 26, top: 46, bottom: 36 },
      xAxis: { type: "category", data: labels },
      yAxis: {
        type: "value",
        name: state.metric === "net_strength" ? "相对强度 (%)" : "净流入绝对值 (亿元)",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${(value * 100).toFixed(0)}%` : `${value.toFixed(0)}亿`;
          },
        },
      },
      series: payload.series.map((series) => {
        const pointMap = new Map(series.points.map((point) => [point.label, point.value]));
        const active = state.selectedSector === series.sector_name || watchlistNames.includes(series.sector_name);
        return {
          name: series.sector_name,
          type: "line",
          smooth: false,
          connectNulls: false,
          showSymbol: state.selectedSector === series.sector_name,
          lineStyle: {
            width: active ? 4 : 2,
            opacity: state.selectedSector && !active ? 0.35 : 1,
          },
          emphasis: { focus: "series" },
          data: labels.map((label) => (pointMap.has(label) ? pointMap.get(label) : null)),
        };
      }),
    },
    true
  );

  comparisonChart.off("click");
  comparisonChart.on("click", async (params) => {
    if (!params.seriesName) return;
    state.selectedSector = params.seriesName;
    state.tables.sectorStocks.page = 1;
    highlightSelection();
    await loadWorkspaceSection();
  });
}

function renderSummaryCards(detail) {
  const container = document.getElementById("summary-cards");
  if (!detail) {
    container.innerHTML = '<div class="empty-state">请选择左侧板块查看工作区</div>';
    return;
  }

  const cards = [
    {
      label: "板块名称",
      value: detail.sector_name,
      subvalue: detail.captured_at ? detail.captured_at.replace("T", " ").slice(0, 16) : "暂无时间",
    },
    {
      label: "净流入强度",
      value: formatPercent(detail.net_strength * 100),
      cls: pickClass(detail.net_strength),
      subvalue: `净额 ${formatAmountCompact(detail.net_amount, { signed: true, assumeYi: true })}`,
    },
    {
      label: "涨跌幅",
      value: formatPercent(detail.change_percent),
      cls: pickClass(detail.change_percent),
      subvalue: `流入 ${formatAmountCompact(detail.inflow, { assumeYi: true })} / 流出 ${formatAmountCompact(detail.outflow, { assumeYi: true })}`,
    },
    {
      label: "领涨股",
      value: detail.leading_stock || "--",
      subvalue: `成分股数量 ${formatNumber(detail.company_count, 0)}`,
    },
  ];

  container.innerHTML = cards
    .map(
      (card) => `
        <div class="summary-card">
          <span class="summary-card-label">${card.label}</span>
          <div class="summary-card-value ${card.cls || ""}">${card.value}</div>
          <div class="summary-card-subvalue">${card.subvalue}</div>
        </div>
      `
    )
    .join("");
}

function renderHistoryChart(history) {
  document.getElementById("history-title").textContent = history?.sector_name ? `${history.sector_name} 历史曲线` : "历史曲线";
  document.getElementById("history-subtitle").textContent =
    state.granularity === "minute" ? "分钟线只保留交易时段，并从首个采样点开始归一化。" : `天级走势，展示最近 ${state.lookbackDays} 个交易日。`;

  detailChart.setOption(
    {
      tooltip: {
        trigger: "axis",
        formatter(params) {
          if (!params.length) return "";
          const title = params[0].axisValueLabel;
          const lines = params.map((item) => `${item.marker}${item.seriesName} ${comparisonValueFormatter({ value: item.data })}`);
          return [title, ...lines].join("<br/>");
        },
      },
      grid: { left: 64, right: 24, top: 24, bottom: 36 },
      xAxis: { type: "category", data: (history?.points || []).map((point) => point.label) },
      yAxis: {
        type: "value",
        name: state.metric === "net_strength" ? "相对强度 (%)" : "净流入绝对值 (亿元)",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${(value * 100).toFixed(0)}%` : `${value.toFixed(0)}亿`;
          },
        },
      },
      series: [
        {
          name: history?.sector_name || "走势",
          type: "line",
          smooth: false,
          connectNulls: false,
          areaStyle: { opacity: 0.08 },
          data: (history?.points || []).map((point) => point.value),
        },
      ],
    },
    true
  );
}

function renderStocks(elementId, rows, fields, message = "暂无数据") {
  const body = document.getElementById(elementId);
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty-state">${message}</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map(
      (row) =>
        `<tr>${fields
          .map((field) => {
            const value = row[field.key];
            const cls = field.cls ? field.cls(value) : "";
            const text = field.format ? field.format(value) : value ?? "--";
            return `<td class="${cls}">${text}</td>`;
          })
          .join("")}</tr>`
    )
    .join("");
}

function renderWorkspaceLoading() {
  document.getElementById("detail-title").textContent = "板块工作区";
  document.getElementById("detail-subtitle").textContent = "正在读取板块详情与历史曲线...";
  document.getElementById("summary-cards").innerHTML = '<div class="loading-state">正在加载板块详情...</div>';
  renderHistoryChart({ sector_name: state.selectedSector || "", points: [] });
}

function renderSectorStocksMeta(payload) {
  const meta = document.getElementById("sector-stocks-meta");
  if (!payload) {
    meta.textContent = "优先读取缓存，抓取失败时会明确提示状态。";
    return;
  }

  const statusMap = {
    cache_hit: "读取缓存",
    fetched: "实时抓取后入库",
    stale_cache: "使用历史缓存回退",
    unavailable: "当前不可用",
  };
  const prefix = statusMap[payload.source_status] || "状态未知";
  if (payload.updated_at) {
    meta.textContent = `${prefix} | 更新时间 ${payload.updated_at.replace("T", " ").slice(0, 16)}${payload.message ? ` | ${payload.message}` : ""}`;
  } else {
    meta.textContent = `${prefix}${payload.message ? ` | ${payload.message}` : ""}`;
  }
}

function renderIndividualMeta(payload) {
  const meta = document.getElementById("individual-meta");
  if (!payload || !payload.updated_at) {
    meta.textContent = "该榜单独立于板块切换，仅反映全市场最新缓存。";
    return;
  }
  const sourceText = payload.source_status === "fetched" ? "刚完成采样" : "读取缓存";
  meta.textContent = `${sourceText} | 更新时间 ${payload.updated_at.replace("T", " ").slice(0, 16)} | 净额按亿/万自动换算`;
}

function renderTableSummary(tableKey, payload, fallbackText) {
  const countElement = document.getElementById(tableKey === "sectorStocks" ? "sector-stocks-count" : "individual-count");
  const pageInfoElement = document.getElementById(tableKey === "sectorStocks" ? "sector-stocks-page-info" : "individual-page-info");
  const total = Number(payload?.total || 0);
  const page = Number(payload?.page || 1);
  const pageSize = Number(payload?.page_size || 1);
  const totalPages = Math.max(1, Math.ceil(total / Math.max(pageSize, 1)));

  countElement.textContent = total
    ? `共 ${total} 只，当前按${payload.sort_by === "change_percent" ? "涨跌幅" : "净流入"}排序`
    : fallbackText;
  pageInfoElement.textContent = `第 ${Math.min(page, totalPages)} / ${totalPages} 页`;

  const prevButton = document.getElementById(tableKey === "sectorStocks" ? "sector-stocks-prev" : "individual-prev");
  const nextButton = document.getElementById(tableKey === "sectorStocks" ? "sector-stocks-next" : "individual-next");
  prevButton.disabled = page <= 1;
  nextButton.disabled = page >= totalPages;
}

function renderSectorOptions(type, options) {
  state.sectorOptions[type] = options;
  renderWatchlistControls();
}

function extractSectorNamesFromOverview(overview) {
  return [...new Set([...(overview?.leaders || []), ...(overview?.laggards || [])].map((item) => item.sector_name).filter(Boolean))];
}

function normalizeSectorOptions(items) {
  return [...new Set((items || []).map((item) => String(item || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

async function loadTradingDates() {
  try {
    const payload = await fetchJson(`/api/trading-dates?sector_type=${state.sectorType}`);
    state.tradingDateApiEnabled = true;
    state.availableDates = payload.dates || [];
    if (!state.selectedTradingDate || !state.availableDates.includes(state.selectedTradingDate)) {
      state.selectedTradingDate = state.availableDates[0] || null;
    }
  } catch (error) {
    console.error(error);
    state.tradingDateApiEnabled = false;
    state.availableDates = [];
    state.selectedTradingDate = null;
  }
  renderTradingDateOptions();
  syncGranularityControls();
}

async function loadSectorOptions(sectorType, force = false) {
  if (!force && state.sectorOptions[sectorType]?.length) {
    renderWatchlistControls();
    return;
  }

  let options = [];
  try {
    const catalog = await fetchJson(`/api/sector-catalog?sector_type=${sectorType}`);
    options = normalizeSectorOptions(catalog.sectors || []);
  } catch (error) {
    console.error(error);
  }

  if (!options.length) {
    try {
      const fallback = await fetchJson(`/api/sectors?sector_type=${sectorType}`);
      options = normalizeSectorOptions(fallback.sectors || []);
    } catch (error) {
      console.error(error);
    }
  }

  if (!options.length && sectorType === state.sectorType && state.latestOverview) {
    options = normalizeSectorOptions(extractSectorNamesFromOverview(state.latestOverview));
  }

  renderSectorOptions(sectorType, options);
}

async function loadOverviewSection() {
  const [overview, alerts, status] = await Promise.all([
    fetchJson(`/api/overview?sector_type=${state.sectorType}&metric=${state.metric}&limit=${state.limit}${tradingDateQuery()}`),
    fetchJson(`/api/alerts?sector_type=${state.sectorType}&metric=${state.metric}&limit=20${tradingDateQuery()}`),
    fetchJson("/api/status"),
  ]);

  state.latestOverview = overview;
  state.latestAlerts = alerts;
  state.latestStatus = status;

  const overviewNames = extractSectorNamesFromOverview(overview);
  if (!state.selectedSector || !overviewNames.includes(state.selectedSector)) {
    state.selectedSector = overview.leaders[0]?.sector_name || overview.laggards[0]?.sector_name || null;
    state.tables.sectorStocks.page = 1;
  }

  renderRankList("leaders-list", overview.leaders);
  renderRankList("laggards-list", overview.laggards);
  renderAlerts(alerts.items);
  setStatusText();
}

async function loadComparisonSection() {
  const include = currentWatchlist().map((item) => item.sectorName).join(",");
  const payload = await fetchJson(
    `/api/comparison?sector_type=${state.sectorType}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}&limit=${state.limit}&include_sectors=${encodeURIComponent(include)}${tradingDateQuery()}`
  );
  renderComparisonChart(payload);
}

async function loadWorkspaceSection() {
  if (!state.selectedSector) {
    renderSummaryCards(null);
    renderHistoryChart({ sector_name: "", points: [] });
    renderStocks("sector-stocks-body", [], sectorStockFields, "请选择板块");
    renderSectorStocksMeta(null);
    renderTableSummary("sectorStocks", null, "等待选择板块");
    return;
  }

  renderWorkspaceLoading();
  renderStocks("sector-stocks-body", [], sectorStockFields, "正在加载成分股资金流...");

  const stocksTable = state.tables.sectorStocks;
  const workspaceRequest = fetchJson(
    `/api/sector-workspace?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}${tradingDateQuery()}`
  );
  const stocksRequest = fetchJson(
    `/api/sector-stocks?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&sort_by=${stocksTable.sortBy}&sort_order=${stocksTable.sortOrder}&page=${stocksTable.page}&page_size=${stocksTable.pageSize}${tradingDateQuery()}`
  );

  try {
    const workspace = await workspaceRequest;
    state.latestWorkspace = workspace;
    document.getElementById("detail-title").textContent = `${workspace.detail.sector_name} 工作区`;
    document.getElementById("detail-subtitle").textContent = "详情与历史优先从本地库快速读取，成分股列表独立刷新。";
    renderSummaryCards(workspace.detail);
    renderHistoryChart(workspace.history);
  } catch (error) {
    console.error(error);
    document.getElementById("detail-title").textContent = "板块工作区";
    document.getElementById("detail-subtitle").textContent = "板块详情读取失败，请检查数据是否存在。";
    renderSummaryCards(null);
    renderHistoryChart({ sector_name: state.selectedSector, points: [] });
  }

  try {
    const stocksPayload = await stocksRequest;
    state.tables.sectorStocks.total = stocksPayload.total || 0;
    renderStocks("sector-stocks-body", stocksPayload.stocks || [], sectorStockFields, stocksPayload.message || "暂无成分股资金流数据");
    renderSectorStocksMeta(stocksPayload);
    renderTableSummary("sectorStocks", stocksPayload, "暂无成分股资金流数据");
  } catch (error) {
    console.error(error);
    renderStocks("sector-stocks-body", [], sectorStockFields, "成分股资金流加载失败");
    renderSectorStocksMeta({ source_status: "unavailable", message: "接口请求失败，请稍后重试。" });
    renderTableSummary("sectorStocks", null, "成分股资金流加载失败");
  }
}

async function loadIndividualSection() {
  const table = state.tables.individuals;
  try {
    const payload = await fetchJson(
      `/api/individual-rankings?limit=${table.fetchLimit}&sort_by=${table.sortBy}&sort_order=${table.sortOrder}&page=${table.page}&page_size=${table.pageSize}${tradingDateQuery()}`
    );
    state.latestIndividuals = payload;
    state.tables.individuals.total = payload.total || 0;
    renderStocks("individual-body", payload.stocks || [], individualStockFields, "暂无全市场资金榜");
    renderIndividualMeta(payload);
    renderTableSummary("individuals", payload, "暂无全市场资金榜");
  } catch (error) {
    console.error(error);
    renderStocks("individual-body", [], individualStockFields, "全市场资金榜加载失败");
    renderIndividualMeta(null);
    renderTableSummary("individuals", null, "全市场资金榜加载失败");
  }
}

async function refreshAll() {
  await loadOverviewSection();
  await loadComparisonSection();
  await Promise.all([loadWorkspaceSection(), loadIndividualSection()]);
}

async function refreshNow() {
  const button = document.getElementById("refresh-button");
  button.disabled = true;
  button.textContent = "采样中...";
  try {
    await fetchJson("/api/refresh", { method: "POST" });
    if (state.granularity === "minute") {
      await loadTradingDates();
    }
    await Promise.all([loadSectorOptions("industry", true), loadSectorOptions("concept", true)]);
    await refreshAll();
  } finally {
    button.disabled = false;
    button.textContent = "立即采样";
  }
}

async function setSectorType(sectorType, selectedSector = null) {
  state.sectorType = sectorType;
  state.selectedSector = selectedSector;
  state.tables.sectorStocks.page = 1;
  syncSectorTabs();
  if (state.granularity === "minute") {
    await loadTradingDates();
  }
  await loadSectorOptions(state.watchlistFormType, true);
  await refreshAll();
}

async function addWatchlist() {
  const sectorName = document.getElementById("watchlist-sector-select").value;
  if (!sectorName) return;
  const nextItem = { sectorType: state.watchlistFormType, sectorName };
  if (state.watchlist.some((item) => item.sectorType === nextItem.sectorType && item.sectorName === nextItem.sectorName)) {
    return;
  }
  state.watchlist.push(nextItem);
  saveSettings();
  renderWatchlist();
  if (nextItem.sectorType === state.sectorType) {
    await loadComparisonSection();
  }
}

function bindTableControls() {
  const sectorSortField = document.getElementById("sector-stocks-sort-field");
  const sectorSortOrder = document.getElementById("sector-stocks-sort-order");
  const sectorPageSize = document.getElementById("sector-stocks-page-size");
  const individualSortField = document.getElementById("individual-sort-field");
  const individualSortOrder = document.getElementById("individual-sort-order");
  const individualPageSize = document.getElementById("individual-page-size");

  sectorSortField.value = state.tables.sectorStocks.sortBy;
  sectorSortOrder.value = state.tables.sectorStocks.sortOrder;
  sectorPageSize.value = String(state.tables.sectorStocks.pageSize);
  individualSortField.value = state.tables.individuals.sortBy;
  individualSortOrder.value = state.tables.individuals.sortOrder;
  individualPageSize.value = String(state.tables.individuals.pageSize);

  sectorSortField.addEventListener("change", async (event) => {
    state.tables.sectorStocks.sortBy = event.target.value;
    state.tables.sectorStocks.page = 1;
    saveSettings();
    await loadWorkspaceSection();
  });

  sectorSortOrder.addEventListener("change", async (event) => {
    state.tables.sectorStocks.sortOrder = event.target.value;
    state.tables.sectorStocks.page = 1;
    saveSettings();
    await loadWorkspaceSection();
  });

  sectorPageSize.addEventListener("change", async (event) => {
    state.tables.sectorStocks.pageSize = Number(event.target.value);
    state.tables.sectorStocks.page = 1;
    saveSettings();
    await loadWorkspaceSection();
  });

  individualSortField.addEventListener("change", async (event) => {
    state.tables.individuals.sortBy = event.target.value;
    state.tables.individuals.page = 1;
    saveSettings();
    await loadIndividualSection();
  });

  individualSortOrder.addEventListener("change", async (event) => {
    state.tables.individuals.sortOrder = event.target.value;
    state.tables.individuals.page = 1;
    saveSettings();
    await loadIndividualSection();
  });

  individualPageSize.addEventListener("change", async (event) => {
    state.tables.individuals.pageSize = Number(event.target.value);
    state.tables.individuals.page = 1;
    saveSettings();
    await loadIndividualSection();
  });

  document.getElementById("sector-stocks-prev").addEventListener("click", async () => {
    if (state.tables.sectorStocks.page <= 1) return;
    state.tables.sectorStocks.page -= 1;
    await loadWorkspaceSection();
  });

  document.getElementById("sector-stocks-next").addEventListener("click", async () => {
    state.tables.sectorStocks.page += 1;
    await loadWorkspaceSection();
  });

  document.getElementById("individual-prev").addEventListener("click", async () => {
    if (state.tables.individuals.page <= 1) return;
    state.tables.individuals.page -= 1;
    await loadIndividualSection();
  });

  document.getElementById("individual-next").addEventListener("click", async () => {
    state.tables.individuals.page += 1;
    await loadIndividualSection();
  });
}

function bindControls() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.addEventListener("click", async () => {
      await setSectorType(button.dataset.sectorType, null);
    });
  });

  document.getElementById("granularity-select").addEventListener("change", async (event) => {
    state.granularity = event.target.value;
    syncGranularityControls();
    if (state.granularity === "minute") {
      await loadTradingDates();
    }
    await refreshAll();
  });

  document.getElementById("trading-date-select").addEventListener("change", async (event) => {
    state.selectedTradingDate = event.target.value || null;
    state.tables.sectorStocks.page = 1;
    state.tables.individuals.page = 1;
    await refreshAll();
  });

  document.getElementById("lookback-select").addEventListener("change", async (event) => {
    state.lookbackDays = Number(event.target.value);
    await refreshAll();
  });

  document.getElementById("metric-select").addEventListener("change", async (event) => {
    state.metric = event.target.value;
    await refreshAll();
  });

  document.getElementById("limit-select").addEventListener("change", async (event) => {
    state.limit = Number(event.target.value);
    await refreshAll();
  });

  document.getElementById("refresh-button").addEventListener("click", refreshNow);

  const deltaInput = document.getElementById("delta-threshold-input");
  const rankInput = document.getElementById("rank-threshold-input");
  deltaInput.value = String(state.deltaThreshold);
  rankInput.value = String(state.rankThreshold);

  deltaInput.addEventListener("change", () => {
    state.deltaThreshold = Number(deltaInput.value || 0);
    saveSettings();
    if (state.latestAlerts) renderAlerts(state.latestAlerts.items);
  });

  rankInput.addEventListener("change", () => {
    state.rankThreshold = Number(rankInput.value || 0);
    saveSettings();
    if (state.latestAlerts) renderAlerts(state.latestAlerts.items);
  });

  document.getElementById("watchlist-type-select").addEventListener("change", async (event) => {
    state.watchlistFormType = event.target.value;
    await loadSectorOptions(state.watchlistFormType, true);
  });

  document.getElementById("watchlist-add-button").addEventListener("click", addWatchlist);

  bindTableControls();
}

async function boot() {
  bindControls();
  syncSectorTabs();
  syncGranularityControls();
  renderWatchlist();

  try {
    await loadTradingDates();
    await refreshAll();
    await Promise.all([loadSectorOptions("industry", true), loadSectorOptions("concept", true)]);
  } catch (error) {
    console.error(error);
    document.getElementById("status-text").textContent = "加载失败，请检查后端服务日志。";
  }

  setInterval(async () => {
    try {
      if (state.granularity === "minute") {
        await loadTradingDates();
      }
      await loadOverviewSection();
      await Promise.all([loadComparisonSection(), loadWorkspaceSection(), loadIndividualSection()]);
    } catch (error) {
      console.error(error);
      document.getElementById("status-text").textContent = "自动刷新失败，请检查后端服务日志。";
    }
  }, 60000);
}

window.addEventListener("resize", () => {
  comparisonChart.resize();
  detailChart.resize();
});

boot().catch((error) => {
  console.error(error);
  document.getElementById("status-text").textContent = "加载失败，请检查后端服务日志。";
});
