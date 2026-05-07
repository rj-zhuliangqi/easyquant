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
  deltaThreshold: persisted.deltaThreshold ?? 1.5,
  rankThreshold: persisted.rankThreshold ?? 2,
  watchlist: persisted.watchlist ?? [],
  latestOverview: null,
  latestAlerts: null,
};

const comparisonChart = echarts.init(document.getElementById("comparison-chart"));
const detailChart = echarts.init(document.getElementById("detail-chart"));

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
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function toNumeric(value) {
  if (typeof value === "number") return value;
  return Number(String(value).replace(/[%+,]/g, ""));
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  return toNumeric(value).toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatSigned(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = toNumeric(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits })}`;
}

function formatMetric(value) {
  return state.metric === "net_strength" ? `${formatSigned(Number(value) * 100, 2)}%` : formatSigned(value);
}

function pickClass(value) {
  const numeric = toNumeric(value);
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
          <div class="rank-item-subtitle">净额 ${formatSigned(row.net_amount)} / 涨跌幅 ${formatSigned(row.change_percent)}%</div>
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
      (sectorName) => `
        <span class="chip">
          <span>${sectorName}</span>
          <button data-sector-name="${sectorName}">×</button>
        </span>
      `
    )
    .join("");
  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.watchlist = state.watchlist.filter((name) => name !== button.dataset.sectorName);
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
  const uniqueDates = new Set(payload.series.flatMap((series) => series.points.map((point) => point.label.split(" ")[0])));
  const note =
    state.granularity === "minute" && uniqueDates.size < state.lookbackDays
      ? "分钟历史只能展示本地已采样交易日，跨日历史需要后续继续积累。"
      : "默认展示最新 Top N，并叠加自选板块池。";
  subtitle.textContent = `${state.granularity === "minute" ? "分钟级" : "天级"}，最近 ${state.lookbackDays} 个交易日。${note}`;
  badges.innerHTML = `
    <span class="badge">比较口径 ${metricLabel()}</span>
    <span class="badge">时间粒度 ${state.granularity === "minute" ? "分钟" : "天级"}</span>
    <span class="badge">最近交易日 ${state.lookbackDays}</span>
    <span class="badge">自选板块 ${state.watchlist.length}</span>
  `;

  const labels = [...new Set(payload.series.flatMap((series) => series.points.map((point) => point.label)))];
  comparisonChart.setOption({
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
      return {
        name: series.sector_name,
        type: "line",
        smooth: true,
        showSymbol: state.selectedSector === series.sector_name,
        emphasis: { focus: "series" },
        lineStyle: {
          width: state.selectedSector === series.sector_name || state.watchlist.includes(series.sector_name) ? 4 : 2,
          opacity: state.selectedSector && state.selectedSector !== series.sector_name && !state.watchlist.includes(series.sector_name) ? 0.45 : 1,
        },
        data: labels.map((label) => (pointMap.has(label) ? pointMap.get(label) : null)),
      };
    }),
  });
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
    container.innerHTML = '<div class="empty-state">请选择板块</div>';
    return;
  }
  document.getElementById("detail-title").textContent = `${detail.sector_name} 详情`;
  container.innerHTML = `
    <dt>板块名称</dt><dd>${detail.sector_name}</dd>
    <dt>净额</dt><dd class="${pickClass(detail.net_amount)}">${formatSigned(detail.net_amount)}</dd>
    <dt>净流入强度</dt><dd class="${pickClass(detail.net_strength)}">${formatSigned(detail.net_strength * 100)}%</dd>
    <dt>涨跌幅</dt><dd class="${pickClass(detail.change_percent)}">${formatSigned(detail.change_percent)}%</dd>
    <dt>流入资金</dt><dd>${formatNumber(detail.inflow)}</dd>
    <dt>流出资金</dt><dd>${formatNumber(detail.outflow)}</dd>
    <dt>公司家数</dt><dd>${formatNumber(detail.company_count)}</dd>
    <dt>领涨股</dt><dd>${detail.leading_stock || "--"}</dd>
  `;
}

function renderDetailChart(payload) {
  document.getElementById("history-title").textContent = `${payload.sector_name} 历史曲线`;
  document.getElementById("history-subtitle").textContent = `${metricLabel()} ${state.granularity === "minute" ? "分钟级" : "天级"}走势`;
  detailChart.setOption({
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
    series: [{ name: payload.sector_name, type: "line", smooth: true, data: payload.points.map((point) => point.value) }],
  });
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
  const [overview, alerts, status] = await Promise.all([
    fetchJson(`/api/overview?sector_type=${state.sectorType}&metric=${state.metric}&limit=10`),
    fetchJson(`/api/alerts?sector_type=${state.sectorType}&metric=${state.metric}&limit=20`),
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
  setStatus(`${marketLabel} | 最近采样 ${snapshotLabel} | 定时采样仅在交易时段运行`);
}

async function loadComparisonSection() {
  const include = state.watchlist.join(",");
  const payload = await fetchJson(
    `/api/comparison?sector_type=${state.sectorType}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}&limit=${state.limit}&include_sectors=${encodeURIComponent(include)}`
  );
  renderComparisonChart(payload);
}

async function loadDetailSection() {
  if (!state.selectedSector) {
    renderDetail(null);
    renderStocks("sector-stocks-body", [], []);
    return;
  }

  const [detail, history, stocks, individuals] = await Promise.all([
    fetchJson(`/api/sector-detail?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}`),
    fetchJson(
      `/api/series?sector_type=${state.sectorType}&sector_name=${encodeURIComponent(state.selectedSector)}&metric=${state.metric}&granularity=${state.granularity}&lookback_days=${state.lookbackDays}`
    ),
    fetchJson(`/api/sector-stocks?sector_name=${encodeURIComponent(state.selectedSector)}`),
    fetchJson("/api/individual-rankings?limit=12"),
  ]);

  renderDetail(detail);
  renderDetailChart(history);
  renderStocks("sector-stocks-body", stocks.stocks.slice(0, 12), [
    { key: "代码" },
    { key: "名称" },
    { key: "最新价", format: formatNumber },
    { key: "今天涨跌幅", format: formatSigned, cls: pickClass },
    { key: "今日主力净流入-净额", format: formatNumber, cls: pickClass },
  ]);
  renderStocks("individual-body", individuals.stocks, [
    { key: "股票代码" },
    { key: "股票简称" },
    { key: "最新价", format: formatNumber },
    { key: "涨跌幅", cls: pickClass },
    { key: "净额" },
  ]);
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
    await refreshAll();
  } finally {
    button.disabled = false;
    button.textContent = "立即采样";
  }
}

async function addWatchlist() {
  const input = document.getElementById("watchlist-input");
  const value = input.value.trim();
  if (!value) return;
  if (!state.watchlist.includes(value)) {
    state.watchlist.push(value);
    saveSettings();
    renderWatchlist();
    await loadComparisonSection();
  }
  input.value = "";
}

function bindControls() {
  document.querySelectorAll("#sector-tabs .tab-button").forEach((button) => {
    button.addEventListener("click", async () => {
      document.querySelectorAll("#sector-tabs .tab-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.sectorType = button.dataset.sectorType;
      state.selectedSector = null;
      await refreshAll();
    });
  });

  document.getElementById("granularity-select").addEventListener("change", async (event) => {
    state.granularity = event.target.value;
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

  document.getElementById("watchlist-add-button").addEventListener("click", addWatchlist);
  document.getElementById("watchlist-input").addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      await addWatchlist();
    }
  });
}

async function boot() {
  bindControls();
  renderWatchlist();
  await refreshAll();
  setInterval(async () => {
    await loadOverviewSection();
    await loadComparisonSection();
    if (state.selectedSector) await loadDetailSection();
  }, 60000);
}

boot().catch((error) => {
  console.error(error);
  setStatus("加载失败，请检查后端服务日志");
});
