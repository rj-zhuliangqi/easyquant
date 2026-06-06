const homeState = {
  marketOverview: null,
  systemSummary: null,
  status: null,
  chart: null,
  selectedIndexSymbol: "sh000001",
};

const INDEX_COLORS = {
  sh000001: "#b57724",
  sz399001: "#2f5f9f",
  sz399006: "#2f806d",
};

function requestJson(url) {
  return fetch(url).then((response) => {
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
  });
}

function formatCount(value) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "--";
}

function formatPercent(value) {
  return typeof value === "number" ? `${value > 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
}

function formatRatio(value) {
  return typeof value === "number" ? `${value.toFixed(2)} : 1` : "--";
}

function formatAmount(value) {
  if (typeof value !== "number") return "--";
  const absolute = Math.abs(value);
  if (absolute >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  if (absolute >= 10000) return `${(value / 10000).toFixed(2)}万`;
  return value.toFixed(2);
}

function formatDateTime(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(0, 16);
}

function formatSourceLabel(label) {
  return (
    {
      akshare: "AKShare 主源",
      tencent: "腾讯补源",
      eastmoney: "东财补源",
      cache: "本地缓存",
    }[label] || "来源未知"
  );
}

function getSelectedIndex() {
  return (homeState.marketOverview?.indices || []).find((item) => item.symbol === homeState.selectedIndexSymbol) || null;
}

function setActiveIndex(symbol) {
  homeState.selectedIndexSymbol = symbol;
  renderIndexSwitcher();
  renderMarketChart();
}

function marketBiasLabel(breadth) {
  if (!breadth) return { title: "等待数据", tone: "neutral", meta: "等待涨跌结构" };
  const ratio = breadth.up_down_ratio ?? 0;
  const delta = (breadth.up_count || 0) - (breadth.down_count || 0);
  if (ratio >= 1.15 && delta > 400) {
    return { title: "偏强扩散", tone: "rise", meta: "上涨家数明显占优" };
  }
  if (ratio <= 0.85 && delta < -400) {
    return { title: "偏弱退潮", tone: "fall", meta: "下跌家数明显占优" };
  }
  return { title: "分歧拉扯", tone: "balance", meta: "情绪没有完全站队" };
}

function promotionLabel(rate) {
  if (typeof rate !== "number") return "等待晋级数据";
  if (rate >= 0.28) return "高于常态，承接尚可";
  if (rate >= 0.18) return "处于中位，继续观察";
  return "晋级偏弱，注意炸板回撤";
}

function activityLabel(breadth) {
  if (!breadth || breadth.market_activity == null) return "等待活跃度";
  if ((breadth.up_down_ratio ?? 0) >= 1.1) return "扩散占优，资金在向外推开";
  if ((breadth.up_down_ratio ?? 0) <= 0.9) return "退潮偏多，先看防守";
  return "结构拉扯，更适合交叉确认";
}

function highBoardLabel(limit) {
  if (typeof limit.highest_board !== "number") return "等待空间高度";
  if ((limit.high_board_count ?? 0) >= 3) return `高标 ${formatCount(limit.high_board_count)} 只，抱团不弱`;
  if ((limit.highest_board ?? 0) >= 4) return `最高板 ${limit.highest_board} 连板，样本偏少`;
  return "高标不多，留意首板和低位扩散";
}

function buildDecision() {
  const breadth = homeState.marketOverview?.breadth || {};
  const summary = homeState.systemSummary || {};
  const sector = summary.sector_monitor || {};
  const limit = summary.limit_up_ladder || {};
  const ratio = breadth.up_down_ratio ?? 0;
  const highestBoard = limit.highest_board ?? 0;
  const promotionRate = limit.promotion_rate ?? 0;
  const hasSectorLead = Boolean(sector.strongest_inflow_sector);

  if (highestBoard >= 4 && promotionRate >= 0.2) {
    return {
      chip: "情绪优先",
      title: "先看连板梯度，确认高标是否继续抱团",
      copy: "当前高标仍有空间，先判断龙头承接、炸板回封和同层强弱，再回到板块页确认题材是否同步吸金。",
      primaryHref: "/limit-up-ladder",
      primaryTitle: "先去连板梯度工作台",
      primaryCopy: `${highestBoard} 连板仍在，晋级率 ${formatPercent(promotionRate * 100)}`,
      secondaryHref: "/sector-monitor",
      secondaryTitle: "再看板块资金承接",
      secondaryCopy: hasSectorLead ? `${sector.strongest_inflow_sector} 正在承接资金` : "回看板块是否跟随高标扩散",
      pulse: "先看情绪",
      pulseMeta: `${highestBoard} 连板仍在，先判断抱团是否延续`,
      entryPrimary: "高标还在扩空间，优先看谁在继续晋级、谁只是回封续命。",
      entrySecondary: hasSectorLead ? `确认 ${sector.strongest_inflow_sector} 是否成为高标背后的主线板块。` : "再用板块页确认有没有同步吸金的主线。",
    };
  }

  if (hasSectorLead && ratio <= 1.05) {
    return {
      chip: "资金优先",
      title: "先看板块资金，锁定今天真正被承接的方向",
      copy: "市场并非一致强势，先确认最强流入和最弱流出的资金差，再决定是否切回连板页看情绪是否配合。",
      primaryHref: "/sector-monitor",
      primaryTitle: "先去板块资金工作台",
      primaryCopy: `${sector.strongest_inflow_sector} / ${sector.weakest_outflow_sector || "等待补全"}`,
      secondaryHref: "/limit-up-ladder",
      secondaryTitle: "再看连板空间配合",
      secondaryCopy: highestBoard > 0 ? `${highestBoard} 连板空间仍可跟踪` : "等待情绪空间抬升",
      pulse: "先看资金",
      pulseMeta: "板块强弱比情绪高度更值得先确认",
      entryPrimary: `先锁定 ${sector.strongest_inflow_sector || "最强板块"} 的承接强度，再看成分股是否同步放量。`,
      entrySecondary: highestBoard > 0 ? `用连板页确认 ${highestBoard} 连板空间是否还能继续打开。` : "再看连板页确认情绪是否开始抬升。",
    };
  }

  return {
    chip: "双线并看",
    title: "指数和结构没有单边答案，先双向交叉确认",
    copy: "当前更像平衡或切换阶段，先用首页判断整体节奏，再分别进板块页和连板页确认资金与情绪是否同向。",
    primaryHref: "/sector-monitor",
    primaryTitle: "先看板块资金工作台",
    primaryCopy: hasSectorLead ? `${sector.strongest_inflow_sector} 可能是切入口` : "等待资金领涨方向确认",
    secondaryHref: "/limit-up-ladder",
    secondaryTitle: "同步看连板梯度工作台",
    secondaryCopy: highestBoard > 0 ? `${highestBoard} 连板与炸板数一起看` : "等待情绪数据补全",
    pulse: "双线并看",
    pulseMeta: "市场没有给出单边答案，更适合交叉验证",
    entryPrimary: hasSectorLead ? `从 ${sector.strongest_inflow_sector} 入手，更容易看到资金是否真正在扩散。` : "先找最强流入和最弱流出，确认今天的资金站队。",
    entrySecondary: highestBoard > 0 ? `看 ${highestBoard} 连板是否稳住，能帮助判断情绪是抱团还是退潮。` : "补看连板页，确认今天的情绪高度是否开始修复。",
  };
}

function renderStatus() {
  const status = homeState.status;
  const summary = homeState.systemSummary;
  const statusText = document.getElementById("home-market-status");
  const statusMeta = document.getElementById("home-status-meta");
  if (!statusText || !statusMeta || !status) return;

  statusText.textContent = status.market_open ? "盘中监控运行中" : "当前为非交易时段";
  statusText.classList.toggle("is-up", Boolean(status.market_open));
  statusText.classList.toggle("is-down", !status.market_open);

  const snapshotAt = summary?.sector_monitor?.last_snapshot_at;
  statusMeta.textContent = `首页更新 ${formatDateTime(status.updated_at)} | 最近板块采样 ${formatDateTime(snapshotAt)}`;
}

function renderPulseStrip() {
  const breadth = homeState.marketOverview?.breadth;
  const summary = homeState.systemSummary;
  const sector = summary?.sector_monitor || {};
  const limit = summary?.limit_up_ladder || {};
  const bias = marketBiasLabel(breadth);
  const decision = buildDecision();

  const cards = Array.from(document.querySelectorAll(".pulse-card"));
  cards.forEach((card) => card.classList.remove("rise", "fall", "balance", "neutral"));
  cards[0]?.classList.add(bias.tone);

  document.getElementById("pulse-bias").textContent = bias.title;
  document.getElementById("pulse-bias-meta").textContent = bias.meta;

  document.getElementById("pulse-strong-sector").textContent = sector.strongest_inflow_sector || "--";
  document.getElementById("pulse-strong-sector-meta").textContent =
    typeof sector.strongest_inflow_amount === "number" ? `净流入 ${formatAmount(sector.strongest_inflow_amount)}` : "等待板块数据";

  document.getElementById("pulse-weak-sector").textContent = sector.weakest_outflow_sector || "--";
  document.getElementById("pulse-weak-sector-meta").textContent =
    typeof sector.weakest_outflow_amount === "number" ? `净流出 ${formatAmount(sector.weakest_outflow_amount)}` : "等待板块数据";

  document.getElementById("pulse-highest-board").textContent =
    typeof limit.highest_board === "number" && limit.highest_board > 0 ? `${limit.highest_board} 连板` : "--";
  document.getElementById("pulse-highest-board-meta").textContent =
    typeof limit.limit_up_count === "number" ? `连板总数 ${formatCount(limit.limit_up_count)} | 炸板 ${formatCount(limit.broken_count)}` : "等待情绪数据";

  document.getElementById("pulse-priority").textContent = decision.pulse;
  document.getElementById("pulse-priority-meta").textContent = decision.pulseMeta;
}

function renderMarketSignals() {
  const breadth = homeState.marketOverview?.breadth || {};
  const summary = homeState.systemSummary || {};
  const sector = summary.sector_monitor || {};
  const limit = summary.limit_up_ladder || {};

  document.getElementById("signal-activity").textContent = formatPercent(breadth.market_activity);
  document.getElementById("signal-activity-meta").textContent = activityLabel(breadth);

  document.getElementById("signal-promotion").textContent =
    limit.promotion_rate != null ? formatPercent(limit.promotion_rate * 100) : "--";
  document.getElementById("signal-promotion-meta").textContent = promotionLabel(limit.promotion_rate);

  document.getElementById("signal-high-board").textContent =
    typeof limit.high_board_count === "number" ? formatCount(limit.high_board_count) : "--";
  document.getElementById("signal-high-board-meta").textContent = highBoardLabel(limit);

  document.getElementById("signal-first-board").textContent =
    typeof limit.first_board_count === "number" ? formatCount(limit.first_board_count) : "--";
  document.getElementById("signal-first-board-meta").textContent =
    typeof limit.limit_up_count === "number" ? `首板扩散占比 ${(limit.first_board_count / Math.max(limit.limit_up_count, 1) * 100).toFixed(0)}%` : "等待情绪总量";

  document.getElementById("signal-watchlist").textContent =
    typeof sector.watched_sector_count === "number" ? formatCount(sector.watched_sector_count) : "--";
  document.getElementById("signal-watchlist-meta").textContent =
    sector.last_snapshot_at ? `最近采样 ${formatDateTime(sector.last_snapshot_at)}` : "等待监控数据";

  document.getElementById("signal-focus").textContent = sector.strongest_inflow_sector || "--";
  document.getElementById("signal-focus-meta").textContent =
    typeof sector.strongest_inflow_amount === "number" ? `${formatAmount(sector.strongest_inflow_amount)} | 资金领跑` : "等待方向确认";
}

function renderSourceStrip() {
  const overviewSource = homeState.marketOverview?.source_summary || {};
  const systemSource = homeState.systemSummary?.source_summary || {};

  const items = [
    {
      key: "indices",
      source: overviewSource.indices,
      labelId: "source-indices-label",
      metaId: "source-indices-meta",
      cardId: "source-indices-card",
    },
    {
      key: "breadth",
      source: overviewSource.breadth,
      labelId: "source-breadth-label",
      metaId: "source-breadth-meta",
      cardId: "source-breadth-card",
    },
    {
      key: "summary",
      source: {
        source_label: systemSource.sector_monitor?.source_label || systemSource.limit_up_ladder?.source_label || "cache",
        updated_at: systemSource.sector_monitor?.updated_at || systemSource.limit_up_ladder?.updated_at || homeState.systemSummary?.updated_at,
        fallback_used: Boolean(systemSource.sector_monitor?.fallback_used || systemSource.limit_up_ladder?.fallback_used),
        degraded_fields: [
          ...(systemSource.sector_monitor?.degraded_fields || []),
          ...(systemSource.limit_up_ladder?.degraded_fields || []),
        ],
      },
      labelId: "source-summary-label",
      metaId: "source-summary-meta",
      cardId: "source-summary-card",
    },
  ];

  for (const item of items) {
    const source = item.source || {};
    const label = document.getElementById(item.labelId);
    const meta = document.getElementById(item.metaId);
    const card = document.getElementById(item.cardId);
    if (!label || !meta || !card) continue;

    const degradedCount = Array.isArray(source.degraded_fields) ? source.degraded_fields.length : 0;
    label.textContent = formatSourceLabel(source.source_label);
    meta.textContent = `${formatDateTime(source.updated_at)} | ${degradedCount ? `缺失 ${degradedCount} 项` : "字段完整"}`;
    card.classList.remove("source-fallback", "source-cache", "source-degraded");
    if (source.fallback_used) card.classList.add("source-fallback");
    if (source.source_label === "cache") card.classList.add("source-cache");
    if (degradedCount) card.classList.add("source-degraded");
  }
}

function renderTemperatureStrip() {
  const temperature = homeState.systemSummary?.limit_up_ladder?.market_temperature || {};
  const scoreNode = document.getElementById("home-temperature-score");
  const scoreMetaNode = document.getElementById("home-temperature-score-meta");
  const bandNode = document.getElementById("home-temperature-band");
  const bandMetaNode = document.getElementById("home-temperature-band-meta");
  const summaryNode = document.getElementById("home-temperature-summary");
  const riskNode = document.getElementById("home-temperature-risk");
  if (!scoreNode || !scoreMetaNode || !bandNode || !bandMetaNode || !summaryNode || !riskNode) return;

  const score = typeof temperature.temperature_score === "number" ? temperature.temperature_score : null;
  scoreNode.textContent = score != null ? score.toFixed(1) : "--";
  scoreMetaNode.textContent = score == null ? "等待情绪复核" : score >= 61 ? "进攻端更要看承接" : score <= 40 ? "防守端更要等修复" : "先看结构是否共振";

  bandNode.textContent = temperature.temperature_band || "--";
  bandMetaNode.textContent = temperature.temperature_band
    ? {
        "冰点": "空间与容错同时受压",
        "偏冷": "延续性不足，先等修复",
        "中性": "扩散与承接还在拉扯",
        "偏热": "进攻占优，但要看分歧",
        "过热": "高弹性高波动，容错开始收缩",
      }[temperature.temperature_band] || "绛夊緟鍒ゆ柇"
    : "绛夊緟鍒ゆ柇";

  summaryNode.textContent = temperature.summary_text || "--";
  riskNode.textContent = temperature.risk_flag || "绛夊緟椋庨櫓鎻愮ず";
}

function renderActionRail() {
  const summary = homeState.systemSummary || {};
  const action = summary.action_priority || {};
  const alerts = summary.alert_summary || {};
  const opportunities = summary.opportunity_summary || {};

  const priorityCard = document.getElementById("action-priority-card");
  const alertsCard = document.getElementById("action-alerts-card");
  const opportunitiesCard = document.getElementById("action-opportunities-card");
  if (!priorityCard || !alertsCard || !opportunitiesCard) return;

  priorityCard.href = action.href || "/sector-monitor";
  alertsCard.href = alerts.action_url || "/alerts";
  opportunitiesCard.href = opportunities.action_url || "/opportunity-pool";

  document.getElementById("action-priority-title").textContent = action.title || "等待行动建议";
  document.getElementById("action-priority-copy").textContent = action.reason || "等待系统判断先看哪边。";
  document.getElementById("action-alerts-title").textContent = alerts.title || "等待预警摘要";
  document.getElementById("action-alerts-copy").textContent =
    typeof alerts.high_priority_count === "number"
      ? `高优先级 ${alerts.high_priority_count} 条 / 全部 ${alerts.count ?? 0} 条`
      : "等待高优先级信号";
  document.getElementById("action-opportunities-title").textContent = opportunities.title || "等待候选摘要";
  document.getElementById("action-opportunities-copy").textContent =
    typeof opportunities.count === "number"
      ? `${opportunities.mode || "机会池"} 当前样本 ${opportunities.count} 个`
      : "等待系统筛好的候选";
}

function renderBreadth() {
  const breadth = homeState.marketOverview?.breadth;
  if (!breadth) return;

  document.getElementById("up-count").textContent = formatCount(breadth.up_count);
  document.getElementById("down-count").textContent = formatCount(breadth.down_count);
  document.getElementById("flat-count").textContent = formatCount(breadth.flat_count);
  document.getElementById("updown-ratio").textContent = formatRatio(breadth.up_down_ratio);
  document.getElementById("limit-pair").textContent = `${formatCount(breadth.limit_up_count)} / ${formatCount(breadth.limit_down_count)}`;
  document.getElementById("market-turnover").textContent = formatAmount(breadth.market_turnover);
  document.getElementById("market-activity-text").textContent = `市场活跃度 ${formatPercent(
    breadth.market_activity,
  )}，上涨与下跌家数对比可以帮助判断资金是在扩散还是收缩。`;
  document.getElementById("breadth-updated-at").textContent = `更新于 ${formatDateTime(homeState.marketOverview.updated_at)}`;
}

function renderIndexSwitcher() {
  const container = document.getElementById("market-index-switcher");
  const indices = homeState.marketOverview?.indices || [];
  if (!container) return;

  container.innerHTML = "";
  for (const item of indices) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `index-switch-button${item.symbol === homeState.selectedIndexSymbol ? " active" : ""}`;
    button.innerHTML = `
      <span>${item.name}</span>
      <strong class="${typeof item.change_percent === "number" && item.change_percent < 0 ? "is-down" : "is-up"}">${item.price?.toFixed(2) ?? "--"}</strong>
      <em>${formatPercent(item.change_percent)} | 成交额 ${formatAmount(item.turnover)}</em>
    `;
    button.addEventListener("click", () => setActiveIndex(item.symbol));
    container.appendChild(button);
  }
}

function renderMarketChart() {
  const container = document.getElementById("market-chart");
  const title = document.getElementById("market-chart-title");
  const meta = document.getElementById("market-chart-meta");
  const selected = getSelectedIndex();
  if (!container || typeof echarts === "undefined" || !selected) return;

  if (!homeState.chart) {
    homeState.chart = echarts.init(container);
    window.addEventListener("resize", () => homeState.chart && homeState.chart.resize());
  }

  title.textContent = `${selected.name}走势`;
  meta.textContent = `${selected.name}近 ${selected.points.length} 个交易日收盘走势`;

  const color = INDEX_COLORS[selected.symbol] || "#2459a8";
  const labels = selected.points.map((point) => point.label);
  const values = selected.points.map((point) => point.value);

  homeState.chart.setOption(
    {
      animation: false,
      grid: { top: 18, right: 12, bottom: 28, left: 56 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: labels,
        axisLine: { lineStyle: { color: "rgba(17, 36, 62, 0.14)" } },
        axisLabel: { color: "#6b8099", fontSize: 12 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(17, 36, 62, 0.08)" } },
        axisLabel: { color: "#6b8099", fontSize: 12 },
      },
      series: [
        {
          name: selected.name,
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 3, color },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: `${color}33` },
                { offset: 1, color: `${color}05` },
              ],
            },
          },
          data: values,
        },
      ],
      color: [color],
    },
    true,
  );
}

function renderDecisionBoard() {
  const decision = buildDecision();
  document.getElementById("decision-chip").textContent = decision.chip;
  document.getElementById("decision-title").textContent = decision.title;
  document.getElementById("decision-copy").textContent = decision.copy;

  const primaryLink = document.getElementById("decision-primary-link");
  const secondaryLink = document.getElementById("decision-secondary-link");
  primaryLink.href = decision.primaryHref;
  secondaryLink.href = decision.secondaryHref;

  document.getElementById("decision-primary-title").textContent = decision.primaryTitle;
  document.getElementById("decision-primary-copy").textContent = decision.primaryCopy;
  document.getElementById("decision-secondary-title").textContent = decision.secondaryTitle;
  document.getElementById("decision-secondary-copy").textContent = decision.secondaryCopy;
  document.getElementById("decision-meta").textContent = `基于首页数据 ${formatDateTime(homeState.status?.updated_at)}`;

  document.getElementById("entry-sector-copy").textContent = decision.primaryHref === "/sector-monitor" ? decision.entryPrimary : decision.entrySecondary;
  document.getElementById("entry-limitup-copy").textContent = decision.primaryHref === "/limit-up-ladder" ? decision.entryPrimary : decision.entrySecondary;
  document.getElementById("entry-sector-card").classList.toggle("entry-primary", decision.primaryHref === "/sector-monitor");
  document.getElementById("entry-limitup-card").classList.toggle("entry-primary", decision.primaryHref === "/limit-up-ladder");
}

function renderSystemSummary() {
  const summary = homeState.systemSummary;
  if (!summary) return;
  const temperature = summary.limit_up_ladder.market_temperature || {};

  document.getElementById("sector-strongest").textContent = summary.sector_monitor.strongest_inflow_sector || "--";
  document.getElementById("sector-weakest").textContent = summary.sector_monitor.weakest_outflow_sector || "--";
  document.getElementById("sector-watchlist-count").textContent = formatCount(summary.sector_monitor.watched_sector_count);
  document.getElementById("sector-summary-updated").textContent = formatDateTime(summary.sector_monitor.last_snapshot_at);
  document.getElementById("sector-summary-hint").textContent = summary.sector_monitor.strongest_inflow_sector
    ? `先看 ${summary.sector_monitor.strongest_inflow_sector} 是否继续吸金`
    : "等待板块强弱确认";
  document.getElementById("sector-summary-copy").textContent = `最近采样 ${formatDateTime(
    summary.sector_monitor.last_snapshot_at,
  )}，适合先对照 ${summary.sector_monitor.strongest_inflow_sector || "强势板块"} 和 ${
    summary.sector_monitor.weakest_outflow_sector || "弱势板块"
  } 的资金背离。`;

  document.getElementById("limitup-highest").textContent =
    typeof summary.limit_up_ladder.highest_board === "number" ? `${summary.limit_up_ladder.highest_board} 连板` : "--";
  document.getElementById("limitup-total").textContent = formatCount(summary.limit_up_ladder.limit_up_count);
  document.getElementById("limitup-broken").textContent = formatCount(summary.limit_up_ladder.broken_count);
  document.getElementById("limitup-summary-updated").textContent = summary.limit_up_ladder.trading_date || "--";
  document.getElementById("limitup-summary-hint").textContent =
    temperature.temperature_band
      ? `${temperature.temperature_band} | ${typeof temperature.temperature_score === "number" ? temperature.temperature_score.toFixed(1) : "--"} 分`
      : typeof summary.limit_up_ladder.highest_board === "number" && summary.limit_up_ladder.highest_board >= 4
        ? "高标仍在，先看抱团还是分歧"
        : "先看首板和炸板的扩散力度";
  document.getElementById("limitup-summary-copy").textContent =
    temperature.summary_text ||
    `${summary.limit_up_ladder.trading_date || "--"} 最高板 ${summary.limit_up_ladder.highest_board ?? "--"}，首板 ${formatCount(
      summary.limit_up_ladder.first_board_count,
    )}，晋级率 ${formatPercent(summary.limit_up_ladder.promotion_rate != null ? summary.limit_up_ladder.promotion_rate * 100 : null)}。`;
}

function renderHomeDashboard() {
  renderStatus();
  renderPulseStrip();
  renderMarketSignals();
  renderSourceStrip();
  renderTemperatureStrip();
  renderActionRail();
  renderBreadth();
  renderIndexSwitcher();
  renderMarketChart();
  renderDecisionBoard();
  renderSystemSummary();
}

function loadHomeDashboard() {
  const tasks = [
    requestJson("/api/home/status").then((status) => {
      homeState.status = status;
      renderStatus();
      renderDecisionBoard();
    }),
    requestJson("/api/home/market-overview").then((marketOverview) => {
      homeState.marketOverview = marketOverview;
      renderPulseStrip();
      renderMarketSignals();
      renderSourceStrip();
      renderBreadth();
      renderIndexSwitcher();
      renderMarketChart();
      renderDecisionBoard();
    }),
    requestJson("/api/home/system-summary").then((systemSummary) => {
      homeState.systemSummary = systemSummary;
      renderStatus();
      renderPulseStrip();
      renderMarketSignals();
      renderSourceStrip();
      renderTemperatureStrip();
      renderActionRail();
      renderDecisionBoard();
      renderSystemSummary();
    }),
  ];
  return Promise.allSettled(tasks).then((results) => {
    const rejected = results.find((result) => result.status === "rejected");
    if (rejected) {
      throw rejected.reason;
    }
  });
}

loadHomeDashboard().catch((error) => {
  const statusText = document.getElementById("home-market-status");
  const statusMeta = document.getElementById("home-status-meta");
  if (statusText) statusText.textContent = "首页数据加载失败";
  if (statusMeta) statusMeta.textContent = error.message;
});
