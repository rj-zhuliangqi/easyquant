const opportunityState = {
  items: [],
  selectedIndex: 0,
};

async function fetchOpportunityJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function formatPercent(value) {
  return typeof value === "number" ? `${value > 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
}

function formatCount(value) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "--";
}

function getAiOutcomeLabel(outcomes) {
  if (!Array.isArray(outcomes) || !outcomes.length) {
    return "Pending review";
  }
  const t1 = outcomes.find((item) => item.window === "T+1");
  if (!t1 || typeof t1.average_close_change_pct !== "number") {
    return "Pending review";
  }
  return `T+1 ${formatPercent(t1.average_close_change_pct)}`;
}

function normalizeAiPick(item) {
  const source = Array.isArray(item.sources) && item.sources.length ? item.sources[0] : {};
  return {
    candidate_type: "ai-t-plus-1",
    mode: "AI T+1",
    stock_code: item.stock_code,
    stock_name: item.stock_name,
    sector_name: item.sector_name,
    board_count: item.source_count,
    theme: Array.isArray(item.tags) && item.tags.length ? item.tags.join(" / ") : "--",
    stock_net_amount: "--",
    turnover_rate: "--",
    entry_reason: source.reason_summary || "AI generated candidate",
    risk_flag: getAiOutcomeLabel(item.outcomes),
    action_url: "/ai-center?tab=reviews",
    revision_title: source.revision_title || "--",
    skill_name: source.skill_name || "--",
    source_count: item.source_count || 0,
  };
}

function renderOpportunityDetail(item) {
  const node = document.getElementById("opportunity-detail-content");
  if (!item) {
    node.className = "detail-card empty";
    node.textContent = "No candidate selected";
    return;
  }

  const aiMeta =
    item.mode === "AI T+1"
      ? `
        <p>Skill: ${item.skill_name || "--"}</p>
        <p>Revision: ${item.revision_title || "--"}</p>
        <p>Sources: ${formatCount(item.source_count)}</p>
      `
      : "";

  node.className = "detail-card";
  node.innerHTML = `
    <div class="tag">${item.mode || "--"}</div>
    <h3>${item.stock_name || item.sector_name || "--"}</h3>
    <p>${item.entry_reason || "--"}</p>
    ${aiMeta}
    <p>Risk: ${item.risk_flag || "--"}</p>
    <p>Open: <a href="${item.action_url || "/ai-center"}">View details</a></p>
  `;
}

async function saveOpportunityToWorkspace() {
  const item = opportunityState.items[opportunityState.selectedIndex];
  if (!item) {
    return;
  }
  const payload = item.stock_code
    ? {
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        sector_name: item.sector_name,
        watch_reason: item.entry_reason,
      }
    : {
        watch_type: "sector",
        sector_type: "industry",
        sector_name: item.sector_name,
        watch_reason: item.entry_reason,
      };
  await fetchOpportunityJson("/api/opportunities/watch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function renderOpportunityRows(items) {
  const body = document.getElementById("opportunity-table-body");
  body.innerHTML = items
    .map(
      (item, index) => `
        <tr class="op-row ${index === opportunityState.selectedIndex ? "active" : ""}" data-index="${index}">
          <td><strong>${item.stock_name || item.sector_name || "--"}</strong><div>${item.stock_code || item.candidate_type || "--"}</div></td>
          <td>${item.board_count ?? "--"}</td>
          <td>${item.theme || "--"}</td>
          <td>${item.stock_net_amount ?? item.sector_net_amount ?? "--"}</td>
          <td>${item.turnover_rate ?? "--"}</td>
          <td>${item.entry_reason || "--"}</td>
          <td>${item.risk_flag || "--"}</td>
        </tr>
      `,
    )
    .join("");

  body.querySelectorAll(".op-row").forEach((row) => {
    row.addEventListener("click", () => {
      opportunityState.selectedIndex = Number(row.dataset.index || 0);
      renderOpportunityRows(opportunityState.items);
      renderOpportunityDetail(opportunityState.items[opportunityState.selectedIndex] || null);
    });
  });
}

async function loadDefaultOpportunities(mode) {
  const payload = await fetchOpportunityJson(`/api/opportunities?mode=${encodeURIComponent(mode)}&limit=20`);
  return payload.items || [];
}

async function loadAiTPlusOneOpportunities() {
  const payload = await fetchOpportunityJson("/api/ai/picks?run_type=production");
  return (payload.items || []).map(normalizeAiPick);
}

async function loadOpportunities() {
  const mode = document.getElementById("opportunity-mode-select").value;
  const items = mode === "ai-t-plus-1" ? await loadAiTPlusOneOpportunities() : await loadDefaultOpportunities(mode);
  opportunityState.items = items;
  opportunityState.selectedIndex = 0;
  document.getElementById("op-status").textContent = `${items.length} items`;
  renderOpportunityRows(items);
  renderOpportunityDetail(items[0] || null);
}

document.getElementById("opportunity-mode-select").addEventListener("change", () => {
  loadOpportunities().catch((error) => {
    document.getElementById("op-status").textContent = error.message;
  });
});

document.getElementById("opportunity-watch-button").addEventListener("click", async () => {
  try {
    await saveOpportunityToWorkspace();
    document.getElementById("op-status").textContent = "Saved to workspace";
  } catch (error) {
    document.getElementById("op-status").textContent = error.message;
  }
});

loadOpportunities().catch((error) => {
  document.getElementById("op-status").textContent = error.message;
});
