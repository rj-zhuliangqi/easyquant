async function fetchWorkspaceJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function loadWorkspace() {
  const payload = await fetchWorkspaceJson("/api/workspace");
  document.getElementById("workspace-status").textContent = `板块 ${payload.watched_sectors.length} · 个股 ${payload.watched_stocks.length}`;
  document.getElementById("workspace-watch-sectors").innerHTML = (payload.watched_sectors || []).map((item) => `<article class="alert-item"><div class="alert-item-title">${item.sector_name}</div><div class="alert-meta">${item.sector_type}</div></article>`).join("") || `<div class="detail-card empty">暂无观察板块</div>`;
  document.getElementById("workspace-watch-stocks").innerHTML = (payload.watched_stocks || []).map((item) => `<article class="alert-item"><div class="alert-item-title">${item.stock_name}</div><div class="alert-meta">${item.stock_code} · ${item.watch_reason || "等待备注"}</div></article>`).join("") || `<div class="detail-card empty">暂无观察个股</div>`;
  document.getElementById("workspace-notes").innerHTML = (payload.notes || []).map((item) => `<article class="alert-item"><div class="alert-item-title">${item.subject_key}</div><div class="alert-meta">${item.content}</div></article>`).join("") || `<div class="detail-card empty">暂无备注</div>`;
}

loadWorkspace().catch((error) => {
  document.getElementById("workspace-status").textContent = error.message;
});
