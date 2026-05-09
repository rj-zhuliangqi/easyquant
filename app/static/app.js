const storageKey = "sector-fund-monitor-settings";

const persisted = (() => {
  try {
    return JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    return {};
  }
})();

function normalizeWatchlist(raw) {
  if (!Array.isArray(raw)) return [];

  const items = raw
    .map((item) => {
      if (typeof item === "string") {
        return { sectorType: "industry", sectorName: item.trim() };
      }
      if (!item || typeof item !== "object") {
        return null;
      }

      const sectorName = String(item.sectorName || item.name || "").trim();
      if (!sectorName) {
        return null;
      }

      return {
        sectorType: item.sectorType === "concept" ? "concept" : "industry",
        sectorName,
      };
    })
    .filter(Boolean);

  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.sectorType}:${item.sectorName}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

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
  tradingDateApiEnabled: true,
  sectorListApiEnabled: true,
};

const comparisonChart = echarts.init(document.getElementById("comparison-chart"));
const detailChart = echarts.init(document.getElementById("detail-chart"));

const sectorStockFields = [
  { key: "代码" },
  { key: "名称" },
  { key: "最新价", format: formatNumber },
  { key: "今天涨跌幅", format: formatPercent, cls: pickClass },
  { key: "今日主力净流入-净额", format: formatNumber, cls: pickClass },
];

const individualStockFields = [
  { key: "股票代码" },
  { key: "股票简称" },
  { key: "最新价", format: formatNumber },
  { key: "涨跌幅", format: formatPercent, cls: pickClass },
  { key: "净额", format: formatNumber, cls: pickClass },
];

function saveSettings() {
  localStorage.setItem(
    storageKey,
    JSON.stringify({
      deltaThreshold: state.deltaThreshold,
      rankThreshold: state.rankThreshold,
      watchlist: state.watchlist,
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

  const text = String(value ?? "")
    .replace(/,/g, "")
    .replace(/\s+/g, "")
    .trim();
  if (!text) return null;

  const match = text.match(/^([+-]?\d+(?:\.\d+)?)(亿|万)?%?$/);
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

function formatSigned(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  if (numeric === null) return String(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits })}`;
}

function formatPercent(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  if (numeric === null) return String(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits })}%`;
}

function formatMetric(value) {
  return state.metric === "net_strength" ? `${formatSigned(Number(value) * 100, 2)}%` : formatSigned(value);
}

function pickClass(value) {
  const numeric = toNumeric(value);
  if (numeric === null) return "neutral";
  if (numeric > 0) return "positive";
  if (numeric < 0) return "negative";
  return "neutral";
}

function setStatus(text) {
  document.getElementById("status-text").textContent = text;
}

function metricLabel() {
  return state.metric === "net_strength" ? "净流入强度" : "净流入绝对值";
}

function sectorTypeLabel(sectorType) {
  return sectorType === "concept" ? "概念" : "行业";
}

function currentWatchlist() {
  return state.watchlist.filter((item) => item.sectorType === state.sectorType);
}

function syncSectorTabs() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.sectorType === state.sectorType);
  });
}

function syncGranularityControls() {
  document
    .getElementById("trading-date-control")
    .classList.toggle("hidden", state.granularity !== "minute" || !state.tradingDateApiEnabled);
  document.getElementById("lookback-control").classList.toggle("hidden", state.granularity === "minute");
}

function tradingDateQuery() {
  if (state.granularity !== "minute" || !state.tradingDateApiEnabled || !state.selectedTradingDate) {
    return "";
  }
  return `&trading_date=${encodeURIComponent(state.selectedTradingDate)}`;
}

function isNotFoundError(error) {
  return String(error?.message || "").includes("404");
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
          <div class="rank-item-subtitle">净额 ${formatSigned(row.net_amount)} / 涨跌幅 ${formatPercent(row.change_percent)}</div>
        </button>
      `
    )
    .join("");
  container.querySelectorAll(".rank-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedSector = button.dataset.sectorName;
      highlightSelection();
      await loadDetailSection();
    });
  });
}

function renderAlerts(items) {
  const filtered = items.filter(
    (item) =>
      Math.abs(Number(item.delta_value) * 100) >= state.deltaThreshold &&
      Math.abs(Number(item.rank_change)) >= state.rankThreshold
  );
  const container = document.getElementById("alerts-list");
  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">当前阈值下暂无异动</div>';
    return;
  }
  container.innerHTML = filtered
    .map(
      (item) => `
        <button class="rank-item ${item.sector_name === state.selectedSector ? "active" : ""}" data-sector-name="${item.sector_name}">
          <div class="rank-item-header">
            <div class="rank-item-title">${item.sector_name}</div>
            <div class="${pickClass(item.delta_value)}">${formatSigned(Number(item.delta_value) * 100)}%</div>
          </div>
          <div class="rank-item-subtitle">排名变化 ${item.rank_change > 0 ? "+" : ""}${item.rank_change}</div>
        </button>
      `
    )
    .join("");
  container.querySelectorAll(".rank-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedSector = button.dataset.sectorName;
      highlightSelection();
      await loadDetailSection();
    });
  });
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
      const nextType = button.dataset.sectorType;
      const nextName = button.dataset.sectorName;
      await setSectorType(nextType, nextName);
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

function highlightSelection() {
  if (state.latestOverview) {
    renderRankList("leaders-list", state.latestOverview.leaders);
    renderRankList("laggards-list", state.latestOverview.laggards);
  }
  if (state.latestAlerts) {
    renderAlerts(state.latestAlerts.items);
  }
}

function renderComparisonChart(payload) {
  const badges = document.getElementById("comparison-badges");
  const subtitle = document.getElementById("comparison-subtitle");
  document.getElementById("comparison-title").textContent = `全板块${metricLabel()}对比`;

  if (state.granularity === "minute") {
    subtitle.textContent = `分钟级，展示 ${state.selectedTradingDate || "最新交易日"} 的本地采样数据。`;
  } else {
    subtitle.textContent = `天级，最近 ${state.lookbackDays} 个交易日，支持拉长到 30 日。`;
  }

  badges.innerHTML = `
    <span class="badge">比较口径 ${metricLabel()}</span>
    <span class="badge">时间粒度 ${state.granularity === "minute" ? "分钟" : "天级"}</span>
    <span class="badge">${state.granularity === "minute" ? `交易日 ${state.selectedTradingDate || "--"}` : `最近交易日 ${state.lookbackDays}`}</span>
    <span class="badge">展示数量 ${state.limit === 0 ? "全部" : state.limit}</span>
    <span class="badge">当前类型自选 ${currentWatchlist().length}</span>
  `;

  const labels = [...new Set(payload.series.flatMap((series) => series.points.map((point) => point.label)))];
  const currentWatchlistNames = currentWatchlist().map((item) => item.sectorName);
  comparisonChart.setOption(
    {
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 52, right: 24, top: 40, bottom: 36 },
      xAxis: { type: "category", data: labels },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${value * 100}%` : value;
          },
        },
      },
      series: payload.series.map((series) => {
        const pointMap = new Map(series.points.map((point) => [point.label, point.value]));
        const highlighted = state.selectedSector === series.sector_name || currentWatchlistNames.includes(series.sector_name);
        return {
          name: series.sector_name,
          type: "line",
          smooth: true,
          showSymbol: state.selectedSector === series.sector_name,
          emphasis: { focus: "series" },
          lineStyle: {
            width: highlighted ? 4 : 2,
            opacity: state.selectedSector && !highlighted ? 0.45 : 1,
          },
          data: labels.map((label) => (pointMap.has(label) ? pointMap.get(label) : null)),
        };
      }),
    },
    true
  );
  comparisonChart.off("click");
  comparisonChart.on("click", async (params) => {
    if (params.seriesName) {
      state.selectedSector = params.seriesName;
      highlightSelection();
      await loadDetailSection();
    }
  });
}

function renderDetail(detail) {
  const container = document.getElementById("sector-detail");
  if (!detail) {
    document.getElementById("detail-title").textContent = "板块详情";
    container.innerHTML = '<div class="empty-state">请选择板块</div>';
    return;
  }
  document.getElementById("detail-title").textContent = `${detail.sector_name} 详情`;
  container.innerHTML = `
    <dt>板块名称</dt><dd>${detail.sector_name}</dd>
    <dt>采样时间</dt><dd>${detail.captured_at ? detail.captured_at.replace("T", " ").slice(0, 16) : "--"}</dd>
    <dt>净额</dt><dd class="${pickClass(detail.net_amount)}">${formatSigned(detail.net_amount)}</dd>
    <dt>净流入强度</dt><dd class="${pickClass(detail.net_strength)}">${formatSigned(detail.net_strength * 100)}%</dd>
    <dt>涨跌幅</dt><dd class="${pickClass(detail.change_percent)}">${formatPercent(detail.change_percent)}</dd>
    <dt>流入资金</dt><dd>${formatNumber(detail.inflow)}</dd>
    <dt>流出资金</dt><dd>${formatNumber(detail.outflow)}</dd>
    <dt>公司家数</dt><dd>${formatNumber(detail.company_count)}</dd>
    <dt>领涨股</dt><dd>${detail.leading_stock || "--"}</dd>
  `;
}

function renderDetailChart(payload) {
  document.getElementById("history-title").textContent = payload.sector_name ? `${payload.sector_name} 历史曲线` : "板块历史曲线";
  document.getElementById("history-subtitle").textContent =
    state.granularity === "minute"
      ? `${metricLabel()} 分钟级走势，交易日 ${state.selectedTradingDate || "--"}`
      : `${metricLabel()} 天级走势，最近 ${state.lookbackDays} 个交易日`;
  detailChart.setOption(
    {
      tooltip: { trigger: "axis" },
      grid: { left: 52, right: 24, top: 24, bottom: 36 },
      xAxis: { type: "category", data: payload.points.map((point) => point.label) },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter(value) {
            return state.metric === "net_strength" ? `${value * 100}%` : value;
          },
        },
      },
      series: [
        {
          name: payload.sector_name || "历史",
          type: "line",
          smooth: true,
          data: payload.points.map((point) => point.value),
        },
      ],
    },
    true
  );
}

function renderStocks(elementId, rows, fields) {
  const body = document.getElementById(elementId);
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">暂无数据</td></tr>';
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

async function loadOverviewSection() {
  const dateQuery = tradingDateQuery();
  const [overview, alerts, status] = await Promise.all([
    fetchJson(`/api/overview?sector_type=${state.sectorType}&metric=${state.metric}&limit=${state.limit}${dateQuery}`),
    fetchJson(`/api/alerts?sector_type=${state.sectorType}&metric=${state.metric}&limit=20${dateQuery}`),
    fetchJson("/api/status"),
  ]);

  state.latestOverview = overview;
  state.latestAlerts = alerts;

  if (!state.selectedSector) {
    state.selectedSector = overview.leaders[0]?.sector_name || overview.laggards[0]?.sector_name || null;
  }

  renderRankList("leaders-list", overview.leaders);
  renderRankList("laggards-list", overview.laggards);
  renderAlerts(alerts.items);

  const marketLabel = status.market_open ? "交易中" : "非交易时段";
  const snapshotLabel = overview.updated_at ? overview.updated_at.replace("T", " ").slice(0, 16) : "暂无";
  const scopeLabel = state.granularity === "minute" ? `查看交易日 ${state.selectedTradingDate || "--"}` : `查看近 ${state.lookbackDays} 日`;
  setStatus(`${marketLabel} | 最近采样 ${snapshotLabel} | ${scopeLabel}`);
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

async function loadDetailSection() {
  if (!state.selectedSector) {
    renderDetail(null);
    renderDetailChart({ sector_name: "", points: [] });
    renderStocks("sector-stocks-body", [], sectorStockFields);
    const individuals = await fetchJson("/api/individual-rankings?limit=20").catch(() => ({ stocks: [] }));
    renderStocks("individual-body", individuals.stocks || [], individualStockFields);
    return;
  }

  const [detailResult, historyResult, stocksResult, individualsResult] = await Promise.allSettled([
    fetchJson(
      `/api/sector-detail?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}${tradingDateQuery()}`
    ),
    fetchJson(
      `/api/series?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}${tradingDateQuery()}`
    ),
    fetchJson(`/api/sector-stocks?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}`),
    fetchJson("/api/individual-rankings?limit=20"),
  ]);

  if (detailResult.status === "fulfilled") {
    renderDetail(detailResult.value);
  } else {
    renderDetail(null);
  }

  if (historyResult.status === "fulfilled") {
    renderDetailChart(historyResult.value);
  } else {
    renderDetailChart({ sector_name: state.selectedSector, points: [] });
  }

  if (stocksResult.status === "fulfilled") {
    renderStocks("sector-stocks-body", stocksResult.value.stocks || [], sectorStockFields);
  } else {
    renderStocks("sector-stocks-body", [], sectorStockFields);
  }

  if (individualsResult.status === "fulfilled") {
    renderStocks("individual-body", individualsResult.value.stocks || [], individualStockFields);
  } else {
    renderStocks("individual-body", [], individualStockFields);
  }
}

async function refreshAll() {
  await loadOverviewSection();
  await loadComparisonSection();
  await loadDetailSection();
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
    await loadSectorOptions(state.watchlistFormType, true);
    await refreshAll();
  } finally {
    button.disabled = false;
    button.textContent = "立即采样";
  }
}

async function loadTradingDates() {
  try {
    const payload = await fetchJson(`/api/trading-dates?sector_type=${state.sectorType}`);
    state.tradingDateApiEnabled = true;
    state.availableDates = payload.dates;
    if (!state.selectedTradingDate || !state.availableDates.includes(state.selectedTradingDate)) {
      state.selectedTradingDate = state.availableDates[0] || null;
    }
  } catch (error) {
    if (!isNotFoundError(error)) {
      throw error;
    }
    state.tradingDateApiEnabled = false;
    state.availableDates = [];
    state.selectedTradingDate = null;
  }
  renderTradingDateOptions();
  syncGranularityControls();
}

function extractSectorNamesFromOverview(overview) {
  const names = [
    ...(overview?.leaders || []).map((item) => item.sector_name),
    ...(overview?.laggards || []).map((item) => item.sector_name),
  ].filter(Boolean);
  return [...new Set(names)];
}

async function loadSectorOptions(sectorType, force = false) {
  if (!force && state.sectorOptions[sectorType]?.length) {
    renderWatchlistControls();
    return;
  }

  const normalizeSectors = (items) =>
    [...new Set((items || []).map((item) => String(item || "").trim()).filter(Boolean))].sort((a, b) =>
      a.localeCompare(b, "zh-CN")
    );

  try {
    const payload = await fetchJson(`/api/sector-catalog?sector_type=${sectorType}`);
    state.sectorListApiEnabled = true;
    state.sectorOptions[sectorType] = normalizeSectors(payload.sectors || []);
  } catch (error) {
    if (!isNotFoundError(error)) {
      throw error;
    }

    try {
      const payload = await fetchJson(`/api/sectors?sector_type=${sectorType}`);
      state.sectorListApiEnabled = true;
      state.sectorOptions[sectorType] = normalizeSectors(payload.sectors || []);
    } catch (nestedError) {
      if (!isNotFoundError(nestedError)) {
        throw nestedError;
      }

      state.sectorListApiEnabled = false;
      if (sectorType === state.sectorType && state.latestOverview) {
        state.sectorOptions[sectorType] = normalizeSectors(extractSectorNamesFromOverview(state.latestOverview));
      } else {
        const fallbackOverview = await fetchJson(`/api/overview?sector_type=${sectorType}&limit=500`).catch(() => null);
        state.sectorOptions[sectorType] = normalizeSectors(extractSectorNamesFromOverview(fallbackOverview));
      }
    }
  }

  if (!state.sectorOptions[sectorType].length && state.latestOverview && sectorType === state.sectorType) {
    state.sectorListApiEnabled = true;
    state.sectorOptions[sectorType] = normalizeSectors(extractSectorNamesFromOverview(state.latestOverview));
  }

  renderWatchlistControls();
}

async function setSectorType(sectorType, selectedSector = null) {
  state.sectorType = sectorType;
  state.selectedSector = selectedSector;
  syncSectorTabs();
  if (state.granularity === "minute") {
    await loadTradingDates();
  }
  await loadSectorOptions(state.watchlistFormType, true);
  await refreshAll();
}

async function addWatchlist() {
  const sectorSelect = document.getElementById("watchlist-sector-select");
  const sectorName = sectorSelect.value;
  if (!sectorName) return;

  const nextItem = { sectorType: state.watchlistFormType, sectorName };
  if (!state.watchlist.some((item) => item.sectorType === nextItem.sectorType && item.sectorName === nextItem.sectorName)) {
    state.watchlist.push(nextItem);
    saveSettings();
    renderWatchlist();
    if (nextItem.sectorType === state.sectorType) {
      await loadComparisonSection();
    }
  }
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
}

async function boot() {
  bindControls();
  syncSectorTabs();
  syncGranularityControls();
  renderWatchlist();
  try {
    await loadTradingDates();
  } catch (error) {
    console.error(error);
  }
  await refreshAll();
  try {
    await loadSectorOptions(state.watchlistFormType, true);
  } catch (error) {
    console.error(error);
  }
  setInterval(async () => {
    try {
      if (state.granularity === "minute") {
        await loadTradingDates();
      }
      await loadOverviewSection();
      await loadComparisonSection();
      if (state.selectedSector) await loadDetailSection();
    } catch (error) {
      console.error(error);
      setStatus("加载失败，请检查后端服务日志");
    }
  }, 60000);
}

boot().catch((error) => {
  console.error(error);
  setStatus("加载失败，请检查后端服务日志");
});