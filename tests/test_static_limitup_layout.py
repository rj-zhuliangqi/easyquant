from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_system_home_has_dashboard_layout_and_source_strip():
    html = (STATIC_DIR / "home.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "home.css").read_text(encoding="utf-8")
    script = (STATIC_DIR / "home.js").read_text(encoding="utf-8")

    assert 'id="home-sidebar"' in html
    assert 'id="home-main"' in html
    assert 'id="market-overview-panel"' in html
    assert 'id="market-pulse-strip"' in html
    assert 'id="market-signal-grid"' in html
    assert 'id="home-source-strip"' in html
    assert 'id="home-temperature-strip"' in html
    assert 'id="market-chart-panel"' in html
    assert 'id="market-index-switcher"' in html
    assert 'id="market-breadth-grid"' in html
    assert 'id="decision-panel"' in html
    assert 'id="system-summary-grid"' in html
    assert 'id="quick-entry-grid"' in html
    assert 'id="entry-sector-card"' in html
    assert 'id="entry-limitup-card"' in html
    assert 'href="/sector-monitor"' in html
    assert 'href="/limit-up-ladder"' in html
    assert "市场总览驾驶舱" in html
    assert "板块资金监控" in html
    assert "A股连板梯度" in html
    assert ".home-shell" in css
    assert ".pulse-strip" in css
    assert ".market-signal-grid" in css
    assert ".source-strip" in css
    assert ".source-card" in css
    assert ".home-sidebar" in css
    assert ".market-panel" in css
    assert ".decision-panel" in css
    assert ".summary-card" in css
    assert ".quick-entry-card" in css
    assert ".index-switcher" in css
    assert ".metric-card.rise" in css
    assert ".metric-card.fall" in css
    assert "selectedIndexSymbol" in script
    assert "function setActiveIndex" in script
    assert "function renderTemperatureStrip" in script
    assert "function renderSourceStrip" in script
    assert "formatSourceLabel" in script


def test_limit_up_page_has_filters_ladder_and_detail_panels():
    html = (STATIC_DIR / "limit-up.html").read_text(encoding="utf-8")
    script = (STATIC_DIR / "limit-up.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "limit-up.css").read_text(encoding="utf-8")

    assert 'id="limitup-date-select"' in html
    assert 'id="limitup-market-scope"' in html
    assert 'id="limitup-view-mode"' in html
    assert 'id="limitup-sort-by"' in html
    assert 'id="limitup-search-input"' in html
    assert 'id="limitup-summary-grid"' in html
    assert 'id="limitup-deskbar"' in html
    assert 'id="limitup-emotion-ribbon"' in html
    assert 'id="emotion-total-meta"' in html
    assert 'id="limitup-temperature-panel"' in html
    assert 'id="temperature-score"' in html
    assert 'id="temperature-band"' in html
    assert 'id="temperature-summary-text"' in html
    assert 'id="temperature-keypoint-legend"' in html
    assert 'id="temperature-signals"' in html
    assert 'id="temperature-trend-chart"' in html
    assert 'id="temperature-factor-chart"' in html
    assert 'id="temperature-volume-chart"' in html
    assert 'id="temperature-factor-grid"' in html
    assert 'id="limitup-ladder-grid"' in html
    assert 'id="limitup-stock-detail"' in html
    assert 'id="turnover-chart"' in html
    assert 'id="netinflow-chart"' in html

    assert "async function loadSummary()" in script
    assert "async function loadTemperatureModule()" in script
    assert "async function loadTemperatureHistory()" in script
    assert "function buildTemperatureKeyMarkers" in script
    assert "function renderTemperaturePanel" in script
    assert "async function loadLadder()" in script
    assert "async function loadBrokenPool()" in script
    assert "async function loadStockDetail(stockCode)" in script
    assert "async function searchStocks()" in script
    assert "function renderJudgementCallout" in script
    assert "const GROUP_PAGE_SIZE = 4;" in script
    assert "function buildPagination" in script
    assert ".ladder-pagination" in css
    assert ".session-deskbar" in css
    assert ".emotion-ribbon" in css
    assert ".temperature-panel" in css
    assert ".temperature-hero" in css
    assert ".temperature-factor-grid" in css
    assert ".temperature-keypoint-legend" in css
    assert ".temperature-signal-chip" in css
    assert ".callout-flags" in css


def test_decision_terminal_expansion_pages_have_core_layout_and_navigation():
    alerts_html = (STATIC_DIR / "alerts.html").read_text(encoding="utf-8")
    alerts_css = (STATIC_DIR / "alerts.css").read_text(encoding="utf-8")
    alerts_js = (STATIC_DIR / "alerts.js").read_text(encoding="utf-8")
    opportunities_html = (STATIC_DIR / "opportunity-pool.html").read_text(encoding="utf-8")
    opportunities_css = (STATIC_DIR / "opportunity-pool.css").read_text(encoding="utf-8")
    opportunities_js = (STATIC_DIR / "opportunity-pool.js").read_text(encoding="utf-8")
    review_html = (STATIC_DIR / "review-center.html").read_text(encoding="utf-8")
    workspace_html = (STATIC_DIR / "workspace.html").read_text(encoding="utf-8")

    assert 'id="alerts-feed"' in alerts_html
    assert 'id="alerts-summary-grid"' in alerts_html
    assert 'id="alerts-detail-panel"' in alerts_html
    assert 'href="/opportunity-pool"' in alerts_html
    assert 'href="/ai-center"' in alerts_html
    assert ".alerts-feed" in alerts_css
    assert "async function loadAlertsFeed()" in alerts_js
    assert "function renderAlertDetail" in alerts_js

    assert 'id="opportunity-mode-select"' in opportunities_html
    assert 'id="opportunity-table-body"' in opportunities_html
    assert 'id="opportunity-detail-panel"' in opportunities_html
    assert 'id="opportunity-watch-button"' in opportunities_html
    assert ".opportunity-table" in opportunities_css
    assert "async function loadOpportunities()" in opportunities_js
    assert "async function saveOpportunityToWorkspace" in opportunities_js

    assert 'id="review-date-select"' in review_html
    assert 'id="review-timeline"' in review_html
    assert 'id="review-temperature-summary"' in review_html
    assert 'id="workspace-notes"' in workspace_html
    assert 'id="workspace-watch-stocks"' in workspace_html
