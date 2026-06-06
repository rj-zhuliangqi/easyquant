const alertsState = { items: [], selectedIndex: 0 };

async function fetchAlertsJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function levelClass(level) {
  return level === "high" ? "level-high" : level === "medium" ? "level-medium" : "level-low";
}

function renderAlertSummary(payload) {
  const grid = document.getElementById("alerts-summary-grid");
  grid.innerHTML = `
    <article class="summary-card"><span>预警总数</span><strong>${payload.total ?? 0}</strong><em>盘中决策先看新增变化</em></article>
    <article class="summary-card"><span>高优先级</span><strong>${payload.high_priority_count ?? 0}</strong><em>${payload.title || "等待高优先级信号"}</em></article>
    <article class="summary-card"><span>顶部信号</span><strong>${payload.top_signal?.subject_name || "--"}</strong><em>${payload.top_signal?.title || "暂无顶部信号"}</em></article>
  `;
}

function renderAlertDetail(item) {
  const panel = document.getElementById("alerts-detail-content");
  if (!item) {
    panel.className = "detail-card empty";
    panel.textContent = "等待选择预警";
    return;
  }
  panel.className = "detail-card";
  panel.innerHTML = `
    <span class="signal-chip ${levelClass(item.level)}">${item.level === "high" ? "高优先级" : item.level === "medium" ? "中优先级" : "观察"}</span>
    <h4>${item.title}</h4>
    <p>${item.reason}</p>
    <div class="detail-grid">
      <div class="detail-tile"><span>对象</span><strong>${item.subject_name}</strong></div>
      <div class="detail-tile"><span>状态</span><strong>${item.status}</strong></div>
      <div class="detail-tile"><span>来源状态</span><strong>${item.freshness_level}</strong></div>
      <div class="detail-tile"><span>动作入口</span><strong><a href="${item.action_url}">立即查看</a></strong></div>
    </div>
  `;
}

function renderAlertsFeed(items) {
  const feed = document.getElementById("alerts-feed");
  alertsState.items = items;
  if (!items.length) {
    feed.innerHTML = `<div class="detail-card empty">当前没有匹配的预警。</div>`;
    renderAlertDetail(null);
    return;
  }
  feed.innerHTML = items.map((item, index) => `
    <article class="alert-item ${index === alertsState.selectedIndex ? "active" : ""}" data-index="${index}">
      <div class="alert-item-head">
        <div>
          <div class="alert-item-title">${item.title}</div>
          <div class="alert-meta">${item.subject_name} · ${item.freshness_level} · ${item.source_label}</div>
        </div>
        <span class="level-chip ${levelClass(item.level)}">${item.level === "high" ? "高优先级" : item.level === "medium" ? "中优先级" : "观察"}</span>
      </div>
      <div class="alert-meta">${item.reason}</div>
    </article>
  `).join("");
  feed.querySelectorAll(".alert-item").forEach((node) => {
    node.addEventListener("click", () => {
      alertsState.selectedIndex = Number(node.dataset.index || 0);
      renderAlertsFeed(alertsState.items);
      renderAlertDetail(alertsState.items[alertsState.selectedIndex]);
    });
  });
  renderAlertDetail(items[alertsState.selectedIndex] || items[0]);
}

async function loadAlertsFeed() {
  const signalType = document.getElementById("alerts-type-select").value;
  const strength = document.getElementById("alerts-strength-select").value;
  const timeWindow = document.getElementById("alerts-window-select").value;
  const [summary, feed] = await Promise.all([
    fetchAlertsJson("/api/alerts/summary"),
    fetchAlertsJson(`/api/alerts/feed?signal_type=${encodeURIComponent(signalType)}&strength=${encodeURIComponent(strength)}&time_window=${encodeURIComponent(timeWindow)}&limit=20`),
  ]);
  document.getElementById("alerts-status").textContent = `已同步 ${feed.items.length} 条`;
  renderAlertSummary(summary);
  renderAlertsFeed(feed.items || []);
}

document.getElementById("alerts-type-select").addEventListener("change", loadAlertsFeed);
document.getElementById("alerts-strength-select").addEventListener("change", loadAlertsFeed);
document.getElementById("alerts-window-select").addEventListener("change", loadAlertsFeed);
loadAlertsFeed().catch((error) => {
  document.getElementById("alerts-status").textContent = "加载失败";
  document.getElementById("alerts-feed").innerHTML = `<div class="detail-card empty">${error.message}</div>`;
});
