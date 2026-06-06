async function fetchReviewJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function loadReviewDates() {
  const payload = await fetchReviewJson("/api/limit-up/dates");
  const select = document.getElementById("review-date-select");
  select.innerHTML = payload.dates.map((item) => `<option value="${item}">${item}</option>`).join("");
  return payload.dates[0];
}

async function loadReviewDay() {
  const tradingDate = document.getElementById("review-date-select").value;
  const [day, timeline] = await Promise.all([
    fetchReviewJson(`/api/review/day?trading_date=${encodeURIComponent(tradingDate)}`),
    fetchReviewJson(`/api/review/timeline?trading_date=${encodeURIComponent(tradingDate)}`),
  ]);
  document.getElementById("review-status").textContent = tradingDate;
  document.getElementById("review-temperature-summary").innerHTML = `
    <article class="summary-card"><span>温度分</span><strong>${day.temperature.temperature_score?.toFixed?.(1) ?? day.temperature.temperature_score}</strong><em>${day.temperature.temperature_band}</em></article>
    <article class="summary-card"><span>最高板</span><strong>${day.ladder_summary.highest_board ?? "--"}</strong><em>连板总数 ${day.ladder_summary.limit_up_count ?? 0}</em></article>
    <article class="summary-card"><span>最强板块</span><strong>${day.top_sectors?.[0]?.sector_name || "--"}</strong><em>${day.review_text || "等待复盘文字"}</em></article>
  `;
  document.getElementById("review-timeline").innerHTML = (timeline.items || []).map((item) => `<article class="alert-item"><div class="alert-item-title">${item.title}</div><div class="alert-meta">${item.subject_name} · ${item.reason}</div></article>`).join("");
  document.getElementById("review-day-detail").className = "detail-card";
  document.getElementById("review-day-detail").innerHTML = `<h4>${day.temperature.temperature_band}</h4><p>${day.review_text}</p>`;
}

loadReviewDates().then(async (firstDate) => {
  document.getElementById("review-date-select").value = firstDate;
  document.getElementById("review-date-select").addEventListener("change", loadReviewDay);
  await loadReviewDay();
}).catch((error) => {
  document.getElementById("review-status").textContent = error.message;
});
