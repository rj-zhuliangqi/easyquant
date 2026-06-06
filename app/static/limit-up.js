const TEXT = {
  loadingStatus: "\u6b63\u5728\u52a0\u8f7d\u8fde\u677f\u68af\u5ea6...",
  ladderTitle: "\u8fde\u677f\u68af\u5ea6",
  ladderSubtitle: "\u4ece\u9996\u677f\u5230\u6700\u9ad8\u677f\uff0c\u89c2\u5bdf\u4eca\u5929\u662f\u5411\u9ad8\u6807\u62b1\u56e2\uff0c\u8fd8\u662f\u5728\u4e2d\u4f4e\u4f4d\u6269\u6563\u3002",
  brokenTitle: "\u70b8\u677f\u6c60",
  brokenSubtitle: "\u89c2\u5bdf\u54ea\u4e9b\u7968\u51b2\u677f\u540e\u5206\u6b67\u52a0\u5927\uff0c\u4f46\u4ecd\u6709\u56de\u5c01\u548c\u6b21\u65e5\u4fee\u590d\u4ef7\u503c\u3002",
  searchHint: "\u652f\u6301\u80a1\u7968\u540d\u79f0\u6216\u4ee3\u7801\u641c\u7d22\uff0c\u4f1a\u81ea\u52a8\u5b9a\u4f4d\u5230\u5bf9\u5e94\u68af\u961f\u6216\u70b8\u677f\u6c60\u3002",
  searchEmpty: "\u6ca1\u6709\u5339\u914d\u7ed3\u679c\uff0c\u8bf7\u6362\u4e2a\u5173\u952e\u5b57\u518d\u8bd5\u3002",
  detailEmpty: "\u7b49\u5f85\u9009\u62e9\u80a1\u7968",
  historyShort: "\u6682\u65e0\u8db3\u591f\u5386\u53f2\u6570\u636e",
  noData: "\u8be5\u4ea4\u6613\u65e5\u6682\u65e0\u8fde\u677f\u6570\u636e",
  noBroken: "\u5f53\u524d\u6ca1\u6709\u70b8\u677f\u6570\u636e",
  waitingSelect: "\u5148\u4ece\u5de6\u4fa7\u9009\u62e9\u4e00\u53ea\u80a1\u7968\uff0c\u53f3\u4fa7\u4f1a\u8054\u52a8\u5c55\u793a\u8fd15\u65e5\u6362\u624b\u3001\u51c0\u6d41\u5165\u548c\u540c\u5c42\u6392\u540d\u3002",
  detailLoaded: "\u5df2\u52a0\u8f7d",
  unselected: "\u672a\u9009\u62e9",
  readFailed: "\u8bfb\u53d6\u5931\u8d25",
  paginationPrev: "\u4e0a\u4e00\u9875",
  paginationNext: "\u4e0b\u4e00\u9875",
};

const GROUP_PAGE_SIZE = 4;

const state = {
  tradingDate: null,
  dates: [],
  marketScope: "all",
  viewMode: "ladder",
  sortBy: "board_count",
  searchKeyword: "",
  summary: null,
  temperature: null,
  temperatureHistory: null,
  ladder: null,
  broken: null,
  selectedStockCode: null,
  detail: null,
  groupPages: {},
};

const turnoverChart = echarts.init(document.getElementById("turnover-chart"));
const netInflowChart = echarts.init(document.getElementById("netinflow-chart"));
const temperatureTrendChart = echarts.init(document.getElementById("temperature-trend-chart"));
const temperatureFactorChart = echarts.init(document.getElementById("temperature-factor-chart"));
const temperatureVolumeChart = echarts.init(document.getElementById("temperature-volume-chart"));

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(text) {
  document.getElementById("limitup-status-text").textContent = text;
  renderDeskbar();
}

function marketScopeLabel(scope) {
  return {
    all: "全A",
    mainboard: "主板",
    gem: "创业板",
    star: "科创板",
  }[scope] || "全A";
}

function renderDeskbar() {
  const dateNode = document.getElementById("limitup-deskbar-date");
  const modeNode = document.getElementById("limitup-deskbar-mode");
  const highestNode = document.getElementById("limitup-deskbar-highest");
  const riskNode = document.getElementById("limitup-deskbar-risk");
  if (!dateNode || !modeNode || !highestNode || !riskNode) return;

  const summary = state.summary || {};
  dateNode.textContent = state.tradingDate || "等待数据";
  modeNode.textContent = `${state.viewMode === "broken" ? "炸板池" : "连板梯度"} · ${marketScopeLabel(state.marketScope)}`;
  highestNode.textContent =
    typeof summary.highest_board === "number" && summary.highest_board > 0
      ? `${summary.highest_board}连板 / ${summary.limit_up_count || 0}只`
      : "等待数据";
  riskNode.textContent = `炸板 ${summary.broken_count || 0} 只 · 晋级率 ${formatPercent(
    summary.promotion_rate != null ? summary.promotion_rate * 100 : null,
  )}`;
}

function renderEmotionRibbon() {
  const summary = state.summary || {};
  const totalNode = document.getElementById("emotion-total");
  const firstNode = document.getElementById("emotion-first-board");
  const highNode = document.getElementById("emotion-high-board");
  const strongNode = document.getElementById("emotion-strong-count");
  const totalMeta = document.getElementById("emotion-total-meta");
  const firstMeta = document.getElementById("emotion-first-board-meta");
  const highMeta = document.getElementById("emotion-high-board-meta");
  const strongMeta = document.getElementById("emotion-strong-count-meta");
  if (!totalNode || !firstNode || !highNode || !strongNode || !totalMeta || !firstMeta || !highMeta || !strongMeta) return;

  totalNode.textContent = typeof summary.limit_up_count === "number" ? `${summary.limit_up_count} 只` : "等待数据";
  firstNode.textContent = typeof summary.first_board_count === "number" ? `${summary.first_board_count} 只` : "等待数据";
  highNode.textContent = typeof summary.high_board_count === "number" ? `${summary.high_board_count} 只` : "等待数据";
  strongNode.textContent = typeof summary.strong_count === "number" ? `${summary.strong_count} 只` : "等待数据";
  totalMeta.textContent =
    typeof summary.limit_up_count === "number"
      ? summary.limit_up_count >= 25
        ? "梯队有扩散感"
        : "总量偏收缩"
      : "等待判断";
  firstMeta.textContent =
    typeof summary.first_board_count === "number" && typeof summary.limit_up_count === "number"
      ? summary.first_board_count / Math.max(summary.limit_up_count, 1) >= 0.45
        ? "低位扩散更明显"
        : "更偏高位抱团"
      : "等待判断";
  highMeta.textContent =
    typeof summary.high_board_count === "number"
      ? summary.high_board_count >= 3
        ? "高标仍有密度"
        : "高标样本稀疏"
      : "等待判断";
  strongMeta.textContent =
    typeof summary.strong_count === "number"
      ? summary.strong_count >= 6
        ? "强势样本够看"
        : "强势样本偏少"
      : "等待判断";
}

function updatePanelState(elementId, text, kind = "neutral") {
  const node = document.getElementById(elementId);
  node.textContent = text;
  node.dataset.kind = kind;
}

function formatAmount(value, withSign = true) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  const numeric = Number(value);
  const sign = withSign ? (numeric > 0 ? "+" : numeric < 0 ? "-" : "") : "";
  const absolute = Math.abs(numeric);
  if (absolute >= 100000000) {
    return `${sign}${(absolute / 100000000).toFixed(2)}\u4ebf`;
  }
  if (absolute >= 10000) {
    return `${sign}${(absolute / 10000).toFixed(2)}\u4e07`;
  }
  return `${sign}${absolute.toFixed(2)}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : numeric < 0 ? "-" : ""}${Math.abs(numeric).toFixed(2)}%`;
}

function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toFixed(2);
}

function formatRank(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return `\u7b2c ${Number(value)} \u540d`;
}

function formatTime(value) {
  const text = String(value ?? "").trim();
  if (!text || text === "nan" || text === "None" || text === "--") {
    return "--";
  }
  const digits = text.replace(/\D/g, "").padStart(6, "0").slice(0, 6);
  if (!digits) {
    return text;
  }
  return `${digits.slice(0, 2)}:${digits.slice(2, 4)}:${digits.slice(4, 6)}`;
}

function pickClass(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "";
  }
  if (numeric > 0) {
    return "positive";
  }
  if (numeric < 0) {
    return "negative";
  }
  return "";
}

function metricTileHtml(item) {
  return `
    <div class="metric-tile">
      <div class="metric-label">${escapeHtml(item.label)}</div>
      <div class="metric-value ${item.className || ""}">${escapeHtml(item.value)}</div>
    </div>
  `;
}

function detailTileHtml(item) {
  return `
    <div class="detail-tile">
      <div class="detail-label">${escapeHtml(item.label)}</div>
      <div class="detail-value ${item.className || ""}">${escapeHtml(item.value)}</div>
    </div>
  `;
}

function renderMetricGrid(elementId, items) {
  const node = document.getElementById(elementId);
  node.innerHTML = items.map(metricTileHtml).join("");
}

function renderDetailTiles(elementId, items) {
  const node = document.getElementById(elementId);
  node.innerHTML = items.map(detailTileHtml).join("");
}

function ladderTone(boardCount) {
  if (boardCount >= 5) {
    return "\u9ad8\u6807\u5c42";
  }
  if (boardCount >= 3) {
    return "\u5f3a\u52bf\u5c42";
  }
  return "\u6269\u6563\u5c42";
}

function renderChartEmpty(chart, title) {
  chart.setOption(
    {
      animation: false,
      xAxis: { type: "category", data: [] },
      yAxis: { type: "value" },
      series: [],
      graphic: {
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: `${title}\n\u5386\u53f2\u4e0d\u8db3`,
          textAlign: "center",
          fill: "#7a8ca3",
          font: '14px "Public Sans", "Microsoft YaHei", sans-serif',
        },
      },
    },
    true
  );
}

function temperatureFactorMeta(score) {
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return "等待判断";
  if (numeric >= 75) return "明显加分";
  if (numeric >= 55) return "偏正面";
  if (numeric >= 35) return "中性偏弱";
  return "明显拖累";
}

function bandToneLabel(band) {
  return {
    "\u8fc7\u70ed": "\u9ad8\u5f39\u6027\u9ad8\u6ce2\u52a8\uff0c\u5148\u9632\u5206\u6b67",
    "\u504f\u70ed": "\u8fdb\u653b\u5360\u4f18\uff0c\u4f46\u8981\u770b\u5bb9\u9519",
    "\u4e2d\u6027": "\u7ed3\u6784\u672a\u5171\u632f\uff0c\u5148\u7b49\u786e\u8ba4",
    "\u504f\u51b7": "\u5ef6\u7eed\u4e0d\u8db3\uff0c\u66f4\u504f\u89c2\u5bdf",
    "\u51b0\u70b9": "\u9000\u6f6e\u660e\u663e\uff0c\u5148\u7b49\u4fee\u590d",
  }[band] || "\u7b49\u5f85\u5224\u65ad";
}

function renderTemperatureFactorGrid(payload) {
  const factorNode = document.getElementById("temperature-factor-grid");
  const factors = payload?.factors || {};
  const cards = [
    ["\u7a7a\u95f4\u9ad8\u5ea6\u56e0\u5b50", factors.highest_board_score],
    ["\u8fde\u677f\u603b\u91cf\u56e0\u5b50", factors.limit_up_total_score],
    ["\u9996\u677f\u6269\u6563\u56e0\u5b50", factors.first_board_breadth_score],
    ["\u70b8\u677f\u538b\u529b\u56e0\u5b50", factors.broken_pressure_score],
    ["\u664b\u7ea7\u7387\u56e0\u5b50", factors.promotion_score],
    ["\u6210\u4ea4\u91cf\u914d\u5408\u56e0\u5b50", factors.turnover_score],
  ];
  factorNode.innerHTML = cards
    .map(
      ([label, score]) => `
        <article class="temperature-factor-card">
          <span>${escapeHtml(label)}</span>
          <strong class="${pickClass((Number(score) || 0) - 50)}">${escapeHtml(Number.isFinite(Number(score)) ? Number(score).toFixed(1) : "--")}</strong>
          <em>${escapeHtml(temperatureFactorMeta(score))}</em>
        </article>
      `
    )
    .join("");
}

function renderTemperatureSignals(payload) {
  const node = document.getElementById("temperature-signals");
  const items = Array.isArray(payload?.signals) && payload.signals.length ? payload.signals : ["\u7b49\u5f85\u5f02\u5e38\u4fe1\u53f7\u5224\u65ad"];
  node.innerHTML = items.map((item) => `<span class="temperature-signal-chip">${escapeHtml(item)}</span>`).join("");
}

function buildTemperatureKeyMarkers(items) {
  const markers = [];
  let previousLabel = null;
  items.forEach((item) => {
    const firstRatio = (item.first_board_count || 0) / Math.max(item.limit_up_count || 1, 1);
    let marker = null;
    if ((item.high_board_count || 0) <= 1 && (item.break_rate || 0) >= 0.4 && ((item.market_turnover_ratio_20d || 0) <= 0.95)) {
      marker = {
        coord: [item.trading_date, item.temperature_score],
        value: "退潮确认",
        symbol: "triangle",
        symbolRotate: 180,
        symbolSize: 24,
        itemStyle: { color: "#1f7a5e" },
        label: { color: "#1f7a5e", fontWeight: 700, formatter: "退潮" },
      };
    } else if ((item.market_turnover_ratio_20d || 0) >= 1.08 && (item.promotion_rate || 0) >= 0.3 && (item.break_rate || 0) <= 0.2) {
      marker = {
        coord: [item.trading_date, item.temperature_score],
        value: "升温确认",
        symbol: "diamond",
        symbolSize: 24,
        itemStyle: { color: "#cf4c32" },
        label: { color: "#b4472f", fontWeight: 700, formatter: "升温" },
      };
    } else if (((item.highest_board || 0) >= 4 && (item.break_rate || 0) >= 0.35) || ((item.promotion_rate || 0) <= 0.2 && firstRatio >= 0.55)) {
      marker = {
        coord: [item.trading_date, item.temperature_score],
        value: "虚热",
        symbol: "pin",
        symbolSize: 28,
        itemStyle: { color: "#c6782f" },
        label: { color: "#8f571f", fontWeight: 700, formatter: "虚热" },
      };
    }
    if (marker && marker.value !== previousLabel) {
      markers.push(marker);
      previousLabel = marker.value;
    }
  });
  return markers;
}

function renderTemperatureTrendChart(history) {
  const items = history?.items || [];
  if (!items.length) {
    renderChartEmpty(temperatureTrendChart, "\u5e02\u573a\u6e29\u5ea6\u8d8b\u52bf");
    return;
  }
  const keyMarkers = buildTemperatureKeyMarkers(items);
  temperatureTrendChart.setOption({
    animationDuration: 260,
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 31, 49, 0.92)",
      borderWidth: 0,
      textStyle: { color: "#f5f8fb" },
      formatter: (params) => {
        const point = items[params?.[0]?.dataIndex || 0];
        return [
          point.trading_date,
          `\u6e29\u5ea6\u5206\uff1a${Number(point.temperature_score).toFixed(1)}`,
          `\u5206\u6863\uff1a${point.temperature_band}`,
          `\u6700\u9ad8\u677f\uff1a${point.highest_board}`,
          `\u664b\u7ea7\u7387\uff1a${formatPercent((point.promotion_rate || 0) * 100)}`,
          keyMarkers.filter((marker) => marker.coord?.[0] === point.trading_date).map((marker) => `\u5173\u952e\u8282\u70b9\uff1a${marker.value}`).join("<br/>"),
        ].join("<br/>");
      },
    },
    grid: { left: 44, right: 18, top: 24, bottom: 28 },
    xAxis: { type: "category", boundaryGap: false, data: items.map((item) => item.trading_date), axisLine: { lineStyle: { color: "rgba(16, 36, 59, 0.12)" } }, axisLabel: { color: "#708197" } },
    yAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "rgba(16, 36, 59, 0.08)" } }, axisLabel: { color: "#708197" } },
    series: [{
      type: "line",
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { width: 3, color: "#214f94" },
      itemStyle: { color: "#214f94" },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(33, 79, 148, 0.28)" }, { offset: 1, color: "rgba(33, 79, 148, 0.04)" }]) },
      markArea: {
        silent: true,
        itemStyle: { opacity: 0.08 },
        data: [
          [{ yAxis: 0, itemStyle: { color: "#15735c" } }, { yAxis: 20 }],
          [{ yAxis: 21, itemStyle: { color: "#6f8cb7" } }, { yAxis: 40 }],
          [{ yAxis: 41, itemStyle: { color: "#a7b8ce" } }, { yAxis: 60 }],
          [{ yAxis: 61, itemStyle: { color: "#e1a86e" } }, { yAxis: 80 }],
          [{ yAxis: 81, itemStyle: { color: "#cf4d32" } }, { yAxis: 100 }],
        ],
      },
      markPoint: {
        symbolKeepAspect: true,
        data: keyMarkers,
      },
      data: items.map((item) => item.temperature_score),
    }],
  }, true);
}

function renderTemperatureFactorChart(history) {
  const items = history?.items || [];
  if (!items.length) {
    renderChartEmpty(temperatureFactorChart, "\u7ed3\u6784\u56e0\u5b50\u5bf9\u6bd4");
    return;
  }
  temperatureFactorChart.setOption({
    animationDuration: 260,
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { color: "#62758c" } },
    grid: { left: 42, right: 12, top: 34, bottom: 24 },
    xAxis: { type: "category", data: items.map((item) => item.trading_date), axisLine: { lineStyle: { color: "rgba(16, 36, 59, 0.12)" } }, axisLabel: { color: "#708197" } },
    yAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "rgba(16, 36, 59, 0.08)" } }, axisLabel: { color: "#708197" } },
    series: [
      { name: "\u7a7a\u95f4\u9ad8\u5ea6", type: "line", smooth: true, symbol: "none", lineStyle: { width: 2.2, color: "#214f94" }, data: items.map((item) => item.factors?.highest_board_score ?? null) },
      { name: "\u664b\u7ea7\u7387", type: "line", smooth: true, symbol: "none", lineStyle: { width: 2.2, color: "#bb6a2d" }, data: items.map((item) => item.factors?.promotion_score ?? null) },
      { name: "\u70b8\u677f\u538b\u529b", type: "line", smooth: true, symbol: "none", lineStyle: { width: 2.2, color: "#15735c" }, data: items.map((item) => item.factors?.broken_pressure_score ?? null) },
    ],
  }, true);
}

function renderTemperatureVolumeChart(history) {
  const items = history?.items || [];
  if (!items.length) {
    renderChartEmpty(temperatureVolumeChart, "\u603b\u91cf\u914d\u5408");
    return;
  }
  temperatureVolumeChart.setOption({
    animationDuration: 260,
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { color: "#62758c" } },
    grid: { left: 44, right: 12, top: 34, bottom: 24 },
    xAxis: { type: "category", data: items.map((item) => item.trading_date), axisLine: { lineStyle: { color: "rgba(16, 36, 59, 0.12)" } }, axisLabel: { color: "#708197" } },
    yAxis: [
      { type: "value", splitLine: { lineStyle: { color: "rgba(16, 36, 59, 0.08)" } }, axisLabel: { color: "#708197", formatter: (value) => `${Number(value).toFixed(2)}x` } },
      { type: "value", axisLabel: { color: "#708197" } },
    ],
    series: [
      { name: "\u6210\u4ea4\u91cf\u76f8\u5bf9\u5747\u503c", type: "bar", barMaxWidth: 18, itemStyle: { color: "rgba(187, 106, 45, 0.72)", borderRadius: [8, 8, 0, 0] }, data: items.map((item) => item.market_turnover_ratio_20d ?? 1) },
      { name: "\u8fde\u677f\u603b\u91cf", type: "line", yAxisIndex: 1, smooth: true, symbol: "circle", symbolSize: 6, lineStyle: { width: 2.2, color: "#214f94" }, itemStyle: { color: "#214f94" }, data: items.map((item) => item.limit_up_count ?? 0) },
    ],
  }, true);
}

function renderTemperaturePanel() {
  const payload = state.temperature;
  const history = state.temperatureHistory;
  if (!payload) {
    document.getElementById("temperature-score").textContent = "\u7b49\u5f85\u6570\u636e";
    document.getElementById("temperature-band").textContent = "\u7b49\u5f85\u5224\u65ad";
    document.getElementById("temperature-summary-title").textContent = "\u60c5\u7eea\u7ed3\u8bba";
    document.getElementById("temperature-summary-text").textContent = "\u7b49\u5f85\u51b7\u70ed\u590d\u6838\u7ed3\u679c";
    document.getElementById("temperature-risk-flag").textContent = "\u7b49\u5f85\u98ce\u9669\u63d0\u793a";
    renderTemperatureSignals({ signals: [] });
    renderTemperatureFactorGrid({ factors: {} });
    renderChartEmpty(temperatureTrendChart, "\u5e02\u573a\u6e29\u5ea6\u8d8b\u52bf");
    renderChartEmpty(temperatureFactorChart, "\u7ed3\u6784\u56e0\u5b50\u5bf9\u6bd4");
    renderChartEmpty(temperatureVolumeChart, "\u603b\u91cf\u914d\u5408");
    return;
  }

  document.getElementById("temperature-score").textContent = Number(payload.temperature_score).toFixed(1);
  const bandNode = document.getElementById("temperature-band");
  bandNode.textContent = payload.temperature_band;
  bandNode.dataset.band = payload.temperature_band;
  document.getElementById("temperature-summary-title").textContent = `${payload.temperature_band} · ${bandToneLabel(payload.temperature_band)}`;
  document.getElementById("temperature-summary-text").textContent = payload.summary_text || "\u7b49\u5f85\u51b7\u70ed\u590d\u6838\u7ed3\u679c";
  document.getElementById("temperature-risk-flag").textContent = payload.risk_flag || "\u7b49\u5f85\u98ce\u9669\u63d0\u793a";
  renderTemperatureFactorGrid(payload);
  renderTemperatureSignals(payload);
  renderTemperatureTrendChart(history);
  renderTemperatureFactorChart(history);
  renderTemperatureVolumeChart(history);
}

function renderLineChart(chart, points, field, formatter, color) {
  if (!Array.isArray(points) || !points.length) {
    renderChartEmpty(chart, TEXT.historyShort);
    return;
  }

  chart.setOption(
    {
      animationDuration: 260,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 31, 49, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#f5f8fb" },
        valueFormatter: (value) => formatter(value),
      },
      grid: { left: 46, right: 18, top: 18, bottom: 28 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((item) => item.date),
        axisLine: { lineStyle: { color: "rgba(16, 36, 59, 0.12)" } },
        axisLabel: { color: "#708197" },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(16, 36, 59, 0.08)" } },
        axisLabel: {
          color: "#708197",
          formatter: (value) => formatter(value),
        },
      },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 7,
          lineStyle: { width: 2.5, color },
          itemStyle: { color },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}66` },
              { offset: 1, color: `${color}08` },
            ]),
          },
          data: points.map((item) => item[field]),
        },
      ],
    },
    true
  );
}

function boardLabel(stock) {
  return stock.board_count > 1 ? `${stock.board_count}\u8fde\u677f` : "\u9996\u677f";
}

function groupPageKey(view, value) {
  return `${view}:${value}`;
}

function totalPages(totalItems) {
  return Math.max(1, Math.ceil(totalItems / GROUP_PAGE_SIZE));
}

function getGroupPage(key, totalItems) {
  const page = Number(state.groupPages[key] || 1);
  return Math.min(Math.max(page, 1), totalPages(totalItems));
}

function setGroupPage(key, nextPage, totalItems) {
  state.groupPages[key] = Math.min(Math.max(Number(nextPage) || 1, 1), totalPages(totalItems));
}

function syncPageToSelectedStock() {
  const stockCode = state.selectedStockCode;
  if (!stockCode) {
    return;
  }
  if (state.viewMode === "broken") {
    const items = state.broken?.items || [];
    const index = items.findIndex((item) => item.code === stockCode);
    if (index >= 0) {
      setGroupPage(groupPageKey("broken", "all"), Math.floor(index / GROUP_PAGE_SIZE) + 1, items.length);
    }
    return;
  }

  (state.ladder?.groups || []).forEach((group) => {
    const index = group.stocks.findIndex((item) => item.code === stockCode);
    if (index >= 0) {
      setGroupPage(groupPageKey("ladder", group.board_count), Math.floor(index / GROUP_PAGE_SIZE) + 1, group.stocks.length);
    }
  });
}

function buildPagination(pageKey, currentPage, totalItems) {
  const pages = totalPages(totalItems);
  if (pages <= 1) {
    return "";
  }
  return `
    <div class="ladder-pagination" data-page-key="${escapeHtml(pageKey)}">
      <button class="page-button" type="button" data-page-key="${escapeHtml(pageKey)}" data-page-next="${currentPage - 1}" ${currentPage <= 1 ? "disabled" : ""}>${TEXT.paginationPrev}</button>
      <div class="page-indicator">${currentPage} / ${pages}</div>
      <button class="page-button" type="button" data-page-key="${escapeHtml(pageKey)}" data-page-next="${currentPage + 1}" ${currentPage >= pages ? "disabled" : ""}>${TEXT.paginationNext}</button>
    </div>
  `;
}

function stockCardHtml(stock) {
  return `
    <button class="stock-row ${state.selectedStockCode === stock.code ? "active" : ""}" data-stock-code="${escapeHtml(stock.code)}">
      <div class="stock-row-head">
        <div>
          <div class="stock-row-name">${escapeHtml(stock.name)}</div>
          <div class="stock-row-code">${escapeHtml(stock.code)}</div>
        </div>
        <div class="stock-row-price">
          <strong class="stock-row-change ${pickClass(stock.change_percent)}">${escapeHtml(formatPercent(stock.change_percent))}</strong>
          <span>${escapeHtml(formatPrice(stock.latest_price))}</span>
        </div>
      </div>
      <div class="stock-row-grid">
        <div class="stock-row-metric">\u5c01\u677f\u65f6\u95f4<strong>${escapeHtml(formatTime(stock.first_limit_up_time))}</strong></div>
        <div class="stock-row-metric">\u6210\u4ea4\u989d<strong>${escapeHtml(formatAmount(stock.turnover, false))}</strong></div>
        <div class="stock-row-metric">\u6362\u624b\u7387<strong>${escapeHtml(formatPercent(stock.turnover_rate))}</strong></div>
        <div class="stock-row-metric">\u51c0\u6d41\u5165<strong class="${pickClass(stock.net_inflow)}">${escapeHtml(formatAmount(stock.net_inflow))}</strong></div>
      </div>
      <div class="stock-tags">
        <span class="stock-tag">${escapeHtml(boardLabel(stock))}</span>
        <span class="stock-tag">${escapeHtml(stock.industry || "\u672a\u5206\u7c7b")}</span>
        <span class="stock-tag">\u70b8\u677f ${escapeHtml(String(stock.broken_board_count ?? 0))}</span>
        <span class="stock-tag subtle">${escapeHtml(stock.net_inflow > 0 ? "资金承接" : "承接待确认")}</span>
      </div>
    </button>
  `;
}

function buildLadderColumn(group) {
  const hasActive = group.stocks.some((item) => item.code === state.selectedStockCode);
  const pageKey = groupPageKey("ladder", group.board_count);
  const currentPage = getGroupPage(pageKey, group.stocks.length);
  const start = (currentPage - 1) * GROUP_PAGE_SIZE;
  const visibleStocks = group.stocks.slice(start, start + GROUP_PAGE_SIZE);
  return `
    <section class="ladder-column ${hasActive ? "active" : ""}">
      <div class="ladder-column-top">
        <div class="ladder-title-wrap">
          <h3>${escapeHtml(group.label)}</h3>
          <p>${escapeHtml(ladderTone(group.board_count))} · ${escapeHtml(`${group.stock_count} \u53ea`)}</p>
        </div>
        <div class="board-badge">${escapeHtml(String(group.board_count))}</div>
      </div>
      <div class="ladder-meta">
        <div class="micro-tile">
          <div class="micro-label">\u80a1\u7968\u6570\u91cf</div>
          <div class="micro-value">${escapeHtml(String(group.stock_count))}</div>
        </div>
        <div class="micro-tile">
          <div class="micro-label">\u5e73\u5747\u6362\u624b</div>
          <div class="micro-value">${escapeHtml(formatPercent(group.avg_turnover_rate))}</div>
        </div>
        <div class="micro-tile">
          <div class="micro-label">\u5e73\u5747\u51c0\u6d41\u5165</div>
          <div class="micro-value ${pickClass(group.avg_net_inflow)}">${escapeHtml(formatAmount(group.avg_net_inflow))}</div>
        </div>
      </div>
      <div class="ladder-list">
        ${visibleStocks.map(stockCardHtml).join("")}
      </div>
      ${buildPagination(pageKey, currentPage, group.stocks.length)}
    </section>
  `;
}

function buildBrokenView(items) {
  const pageKey = groupPageKey("broken", "all");
  const currentPage = getGroupPage(pageKey, items.length);
  const start = (currentPage - 1) * GROUP_PAGE_SIZE;
  const visibleItems = items.slice(start, start + GROUP_PAGE_SIZE);
  return `
    <section class="ladder-column active">
      <div class="ladder-column-top">
        <div class="ladder-title-wrap">
          <h3>\u70b8\u677f\u6c60</h3>
          <p>\u770b\u5206\u6b67\u3001\u56de\u5c01\u548c\u627f\u63a5\uff0c\u800c\u4e0d\u662f\u53ea\u770b\u6709\u6ca1\u6709\u6478\u677f\u3002</p>
        </div>
        <div class="board-badge">${escapeHtml(String(items.length))}</div>
      </div>
      <div class="ladder-meta">
        <div class="micro-tile">
          <div class="micro-label">\u70b8\u677f\u6570\u91cf</div>
          <div class="micro-value">${escapeHtml(String(items.length))}</div>
        </div>
        <div class="micro-tile">
          <div class="micro-label">\u8ddf\u8e2a\u91cd\u70b9</div>
          <div class="micro-value">\u56de\u5c01\u627f\u63a5</div>
        </div>
        <div class="micro-tile">
          <div class="micro-label">\u89c2\u5bdf\u65b9\u5411</div>
          <div class="micro-value">\u6b21\u65e5\u4fee\u590d</div>
        </div>
      </div>
      <div class="ladder-list">
        ${items.length ? visibleItems.map(stockCardHtml).join("") : `<div class="empty-state">${TEXT.noBroken}</div>`}
      </div>
      ${buildPagination(pageKey, currentPage, items.length)}
    </section>
  `;
}

function bindStockButtons() {
  document.querySelectorAll("[data-stock-code]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedStockCode = button.dataset.stockCode;
      try {
        await loadStockDetail(state.selectedStockCode);
      } catch (error) {
        console.error(error);
        state.detail = null;
        renderStockDetail();
      }
      renderMainView();
    });
  });
}

function bindPaginationButtons() {
  document.querySelectorAll("[data-page-next]").forEach((button) => {
    button.addEventListener("click", () => {
      const pageKey = button.dataset.pageKey;
      const nextPage = Number(button.dataset.pageNext || 1);
      if (!pageKey) {
        return;
      }
      let totalItems = 0;
      if (pageKey.startsWith("ladder:")) {
        const boardCount = Number(pageKey.split(":")[1]);
        const group = (state.ladder?.groups || []).find((item) => item.board_count === boardCount);
        totalItems = group?.stocks?.length || 0;
      } else {
        totalItems = state.broken?.items?.length || 0;
      }
      setGroupPage(pageKey, nextPage, totalItems);
      renderMainView();
    });
  });
}

function renderMainView() {
  const grid = document.getElementById("limitup-ladder-grid");
  syncPageToSelectedStock();

  if (state.viewMode === "broken") {
    const items = state.broken?.items || [];
    document.getElementById("limitup-main-title").textContent = TEXT.brokenTitle;
    document.getElementById("limitup-main-subtitle").textContent = TEXT.brokenSubtitle;
    grid.innerHTML = buildBrokenView(items);
    updatePanelState("limitup-ladder-state", items.length ? `${items.length} \u53ea\u70b8\u677f\u80a1` : TEXT.noBroken, items.length ? "warning" : "neutral");
    bindStockButtons();
    bindPaginationButtons();
    renderDeskbar();
    return;
  }

  const groups = state.ladder?.groups || [];
  document.getElementById("limitup-main-title").textContent = TEXT.ladderTitle;
  document.getElementById("limitup-main-subtitle").textContent = TEXT.ladderSubtitle;

  if (!groups.length) {
    grid.innerHTML = `<div class="empty-state">${TEXT.noData}</div>`;
    updatePanelState("limitup-ladder-state", "\u6682\u65e0\u68af\u961f\u6570\u636e", "warning");
    return;
  }

  grid.innerHTML = groups.map(buildLadderColumn).join("");
  updatePanelState("limitup-ladder-state", `${groups.length} \u4e2a\u68af\u961f`, "fresh");
  bindStockButtons();
  bindPaginationButtons();
  renderDeskbar();
}

async function loadDates() {
  const payload = await fetchJson("/api/limit-up/dates");
  state.dates = payload.dates || [];
  if (!state.tradingDate) {
    state.tradingDate = state.dates[0] || null;
  }
  const select = document.getElementById("limitup-date-select");
  select.innerHTML = state.dates.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  select.value = state.tradingDate || "";
}

async function loadSummary() {
  const payload = await fetchJson(`/api/limit-up/summary?trading_date=${encodeURIComponent(state.tradingDate)}&market_scope=${state.marketScope}`);
  state.summary = payload;
  renderMetricGrid("limitup-summary-grid", [
    { label: "\u6700\u9ad8\u677f\u9ad8\u5ea6", value: `${payload.highest_board}\u677f` },
    { label: "\u8fde\u677f\u603b\u6570", value: `${payload.limit_up_count}` },
    { label: "\u9996\u677f\u6570\u91cf", value: `${payload.first_board_count}` },
    { label: "\u9ad8\u6807\u6570\u91cf", value: `${payload.high_board_count}` },
    { label: "\u70b8\u677f\u6570\u91cf", value: `${payload.broken_count}` },
    { label: "\u664b\u7ea7\u7387", value: formatPercent(payload.promotion_rate * 100), className: pickClass(payload.promotion_rate) },
    { label: "\u65ad\u677f\u7387", value: formatPercent(payload.break_rate * 100), className: pickClass(-payload.break_rate) },
  ]);
  updatePanelState("limitup-summary-state", `${payload.trading_date} \u5df2\u66f4\u65b0`, "fresh");
  renderDeskbar();
  renderEmotionRibbon();
}

async function loadTemperatureHistory() {
  state.temperatureHistory = await fetchJson(
    `/api/limit-up/temperature-history?lookback_days=20&market_scope=${state.marketScope}`
  );
}

async function loadTemperatureModule() {
  state.temperature = await fetchJson(
    `/api/limit-up/temperature?trading_date=${encodeURIComponent(state.tradingDate)}&market_scope=${state.marketScope}`
  );
  await loadTemperatureHistory();
  renderTemperaturePanel();
  updatePanelState("limitup-temperature-state", `${state.temperature.trading_date} \u5df2\u590d\u6838`, "fresh");
}

async function loadLadder() {
  const payload = await fetchJson(
    `/api/limit-up/ladder?trading_date=${encodeURIComponent(state.tradingDate)}&market_scope=${state.marketScope}&sort_by=${state.sortBy}`
  );
  state.ladder = payload;
}

async function loadBrokenPool() {
  const sortBy = state.sortBy === "board_count" ? "turnover" : state.sortBy;
  const payload = await fetchJson(
    `/api/limit-up/broken?trading_date=${encodeURIComponent(state.tradingDate)}&market_scope=${state.marketScope}&sort_by=${sortBy}`
  );
  state.broken = payload;
}

function ensureSelectedStock() {
  const availableCodes = new Set();
  (state.ladder?.groups || []).forEach((group) => group.stocks.forEach((stock) => availableCodes.add(stock.code)));
  (state.broken?.items || []).forEach((stock) => availableCodes.add(stock.code));

  if (state.selectedStockCode && availableCodes.has(state.selectedStockCode)) {
    return state.selectedStockCode;
  }

  const defaultStock =
    state.viewMode === "broken"
      ? state.broken?.items?.[0]
      : state.ladder?.groups?.find((group) => group.stocks.length)?.stocks?.[0] || state.broken?.items?.[0];

  state.selectedStockCode = defaultStock?.code || null;
  return state.selectedStockCode;
}

function buildJudgementTitle(payload) {
  if (payload.source_view === "broken") {
    return "\u70b8\u677f\u540e\u5148\u770b\u56de\u5c01\u8d28\u91cf";
  }
  if (payload.peer_rankings?.net_inflow_rank === 1 && payload.peer_rankings?.turnover_rank === 1) {
    return "\u540c\u5c42\u6838\u5fc3\uff0c\u53ef\u91cd\u70b9\u76ef\u627f\u63a5";
  }
  if (payload.judgement?.rebound_limit_up) {
    return "\u56de\u5c01\u6210\u529f\uff0c\u91cd\u70b9\u770b\u5206\u6b67\u540e\u7684\u627f\u63a5";
  }
  if ((payload.judgement?.broken_board_count || 0) >= 2) {
    return "\u5206\u6b67\u504f\u5927\uff0c\u4e0d\u5b9c\u53ea\u770b\u9ad8\u5ea6";
  }
  return "\u5c01\u677f\u5b8c\u6574\u5ea6\u5c1a\u53ef\uff0c\u7ee7\u7eed\u770b\u8d44\u91d1\u8fde\u7eed\u6027";
}

function buildJudgementText(payload) {
  const stock = payload.stock;
  const parts = [
    `${boardLabel(stock)}\uff0c${payload.judgement?.seal_status || "\u72b6\u6001\u5f85\u5b9a"}`,
    `\u9996\u6b21\u5c01\u677f ${formatTime(stock.first_limit_up_time)}`,
    `\u51c0\u6d41\u5165 ${formatAmount(stock.net_inflow)}`,
  ];
  if (payload.peer_rankings?.net_inflow_rank) {
    parts.push(`\u540c\u5c42\u51c0\u6d41\u5165\u6392\u540d ${formatRank(payload.peer_rankings.net_inflow_rank)}`);
  }
  if ((payload.judgement?.broken_board_count || 0) > 0) {
    parts.push(`\u65e5\u5185\u70b8\u677f ${payload.judgement.broken_board_count} \u6b21\uff0c\u9700\u5173\u6ce8\u56de\u5c01\u540e\u7684\u627f\u63a5\u8d28\u91cf`);
  }
  return parts.join(" \u00b7 ");
}

function renderStockHero(payload) {
  const stock = payload.stock;
  document.getElementById("limitup-stock-hero").innerHTML = `
    <div class="stock-hero-top">
      <div class="stock-hero-title">
        <h3>${escapeHtml(stock.name)}</h3>
        <div class="stock-hero-code">${escapeHtml(stock.code)}</div>
      </div>
      <div class="stock-hero-price">
        <strong class="${pickClass(stock.change_percent)}">${escapeHtml(formatPercent(stock.change_percent))}</strong>
        <div>${escapeHtml(formatPrice(stock.latest_price))}</div>
      </div>
    </div>
    <div class="stock-hero-meta">
      <span class="hero-chip">${escapeHtml(boardLabel(stock))}</span>
      <span class="hero-chip">${escapeHtml(stock.industry || "\u672a\u5206\u7c7b")}</span>
      <span class="hero-chip">\u5c01\u677f ${escapeHtml(formatTime(stock.first_limit_up_time))}</span>
      <span class="hero-chip">\u6210\u4ea4 ${escapeHtml(formatAmount(stock.turnover, false))}</span>
    </div>
  `;
}

function renderJudgementCallout(payload) {
  const riskFlags = [
    payload.judgement?.rebound_limit_up ? "回封已出现" : "回封未确认",
    (payload.judgement?.broken_board_count || 0) >= 2 ? "分歧偏大" : "分歧可控",
    payload.peer_rankings?.net_inflow_rank === 1 ? "同层净流入领先" : "看同层对比",
  ];
  document.getElementById("limitup-judgement-callout").innerHTML = `
    <div class="callout-label">\u8ffd\u677f\u63d0\u793a</div>
    <div class="callout-title">${escapeHtml(buildJudgementTitle(payload))}</div>
    <div class="callout-text">${escapeHtml(buildJudgementText(payload))}</div>
    <div class="callout-flags">${riskFlags.map((item) => `<span class="callout-flag">${escapeHtml(item)}</span>`).join("")}</div>
  `;
}

function renderStockDetail() {
  const payload = state.detail;
  if (!payload) {
    document.getElementById("limitup-detail-empty").classList.remove("hidden");
    document.getElementById("limitup-detail-content").classList.add("hidden");
    updatePanelState("limitup-detail-state", TEXT.unselected, "neutral");
    renderChartEmpty(turnoverChart, TEXT.detailEmpty);
    renderChartEmpty(netInflowChart, TEXT.detailEmpty);
    return;
  }

  document.getElementById("limitup-detail-empty").classList.add("hidden");
  document.getElementById("limitup-detail-content").classList.remove("hidden");

  renderStockHero(payload);
  renderJudgementCallout(payload);

  renderDetailTiles("limitup-stock-core", [
    { label: "\u8fde\u677f\u9ad8\u5ea6", value: boardLabel(payload.stock) },
    { label: "\u6d41\u901a\u5e02\u503c", value: formatAmount(payload.stock.float_market_value, false) },
    { label: "\u4e3b\u529b\u51c0\u6d41\u5165", value: formatAmount(payload.stock.net_inflow), className: pickClass(payload.stock.net_inflow) },
    { label: "\u4eca\u65e5\u6210\u4ea4\u989d", value: formatAmount(payload.stock.turnover, false) },
    { label: "\u6362\u624b\u7387", value: formatPercent(payload.stock.turnover_rate) },
    { label: "\u6240\u5c5e\u9898\u6750", value: payload.stock.industry || "\u672a\u5206\u7c7b" },
  ]);

  renderDetailTiles("limitup-judgement-grid", [
    { label: "\u5c01\u677f\u72b6\u6001", value: payload.judgement?.seal_status || "--" },
    { label: "\u5f00\u677f\u6b21\u6570", value: `${payload.judgement?.broken_board_count ?? 0}` },
    { label: "\u5c01\u5355\u5f3a\u5ea6", value: formatAmount(payload.judgement?.seal_amount) },
    { label: "\u91cf\u6bd4", value: payload.judgement?.volume_ratio === null || payload.judgement?.volume_ratio === undefined ? "--" : Number(payload.judgement.volume_ratio).toFixed(2) },
    { label: "\u632f\u5e45", value: formatPercent(payload.judgement?.amplitude) },
    { label: "\u56de\u5c01\u72b6\u6001", value: payload.judgement?.rebound_limit_up ? "\u70b8\u677f\u540e\u56de\u5c01" : "\u672a\u89c1\u56de\u5c01" },
  ]);

  renderDetailTiles("limitup-peer-rankings", [
    { label: "\u6210\u4ea4\u989d\u6392\u540d", value: formatRank(payload.peer_rankings?.turnover_rank) },
    { label: "\u6362\u624b\u7387\u6392\u540d", value: formatRank(payload.peer_rankings?.turnover_rate_rank) },
    { label: "\u51c0\u6d41\u5165\u6392\u540d", value: formatRank(payload.peer_rankings?.net_inflow_rank) },
    { label: "\u5c01\u677f\u65f6\u95f4\u6392\u540d", value: formatRank(payload.peer_rankings?.seal_time_rank) },
  ]);

  renderLineChart(turnoverChart, payload.turnover_history || [], "turnover_rate", (value) => `${Number(value).toFixed(1)}%`, "#214f94");
  renderLineChart(netInflowChart, payload.net_inflow_history || [], "net_inflow", (value) => formatAmount(value), "#bb6a2d");
  updatePanelState("limitup-detail-state", `${payload.stock.name} ${TEXT.detailLoaded}`, "fresh");
}

async function loadStockDetail(stockCode) {
  state.detail = await fetchJson(`/api/limit-up/stock-detail?trading_date=${encodeURIComponent(state.tradingDate)}&stock_code=${encodeURIComponent(stockCode)}`);
  renderStockDetail();
}

async function searchStocks() {
  const input = document.getElementById("limitup-search-input");
  const keyword = String(input.value || state.searchKeyword || "").trim();
  state.searchKeyword = keyword;
  if (!keyword) {
    document.getElementById("limitup-search-meta").textContent = TEXT.searchHint;
    return;
  }

  const payload = await fetchJson(
    `/api/limit-up/search?trading_date=${encodeURIComponent(state.tradingDate)}&market_scope=${state.marketScope}&keyword=${encodeURIComponent(keyword)}`
  );

  if (!payload.items.length) {
    document.getElementById("limitup-search-meta").textContent = TEXT.searchEmpty;
    return;
  }

  const first = payload.items[0];
  state.viewMode = first.source_view === "broken" ? "broken" : "ladder";
  document.getElementById("limitup-view-mode").value = state.viewMode;
  state.selectedStockCode = first.code;
  document.getElementById("limitup-search-meta").textContent = `\u547d\u4e2d ${payload.items.length} \u53ea\uff0c\u5df2\u5b9a\u4f4d\u5230 ${first.name}\u3002`;
  await loadStockDetail(first.code);
  renderMainView();
}

function bindControls() {
  document.getElementById("limitup-date-select").addEventListener("change", async (event) => {
    state.tradingDate = event.target.value;
    await refreshPage();
  });

  document.getElementById("limitup-market-scope").addEventListener("change", async (event) => {
    state.marketScope = event.target.value;
    state.selectedStockCode = null;
    await refreshPage();
  });

  document.getElementById("limitup-view-mode").addEventListener("change", async (event) => {
    state.viewMode = event.target.value;
    ensureSelectedStock();
    renderMainView();
    if (state.selectedStockCode) {
      try {
        await loadStockDetail(state.selectedStockCode);
      } catch {
        state.detail = null;
        renderStockDetail();
      }
    }
  });

  document.getElementById("limitup-sort-by").addEventListener("change", async (event) => {
    state.sortBy = event.target.value;
    await refreshCollections();
  });

  document.getElementById("limitup-search-input").addEventListener("input", (event) => {
    state.searchKeyword = event.target.value || "";
  });

  document.getElementById("limitup-search-input").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    await searchStocks();
  });

  window.addEventListener("resize", () => {
    turnoverChart.resize();
    netInflowChart.resize();
    temperatureTrendChart.resize();
    temperatureFactorChart.resize();
    temperatureVolumeChart.resize();
  });
}

async function refreshCollections() {
  await Promise.all([loadLadder(), loadBrokenPool()]);
  ensureSelectedStock();
  renderMainView();
  if (!state.selectedStockCode) {
    state.detail = null;
    renderStockDetail();
    return;
  }
  try {
    await loadStockDetail(state.selectedStockCode);
  } catch {
    state.detail = null;
    renderStockDetail();
  }
}

async function refreshPage() {
  setStatus(`\u6b63\u5728\u8bfb\u53d6 ${state.tradingDate || "--"} \u7684\u8fde\u677f\u7ed3\u6784...`);
  await Promise.all([loadSummary(), loadTemperatureModule(), refreshCollections()]);
  setStatus(`\u4ea4\u6613\u65e5 ${state.tradingDate} \u00b7 \u8fde\u677f\u68af\u5ea6\u3001\u70b8\u677f\u6c60\u548c\u4e2a\u80a1\u8be6\u60c5\u5df2\u540c\u6b65`);
}

async function boot() {
  document.getElementById("limitup-search-meta").textContent = TEXT.searchHint;
  document.getElementById("limitup-detail-empty").textContent = TEXT.waitingSelect;
  setStatus(TEXT.loadingStatus);
  await loadDates();
  bindControls();
  await refreshPage();
}

boot().catch((error) => {
  console.error(error);
  setStatus("\u8fde\u677f\u9875\u9762\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u540e\u7aef\u670d\u52a1\u3002");
  updatePanelState("limitup-summary-state", TEXT.readFailed, "warning");
  updatePanelState("limitup-temperature-state", TEXT.readFailed, "warning");
  updatePanelState("limitup-ladder-state", TEXT.readFailed, "warning");
  updatePanelState("limitup-detail-state", TEXT.readFailed, "warning");
});
