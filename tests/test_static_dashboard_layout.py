from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_dashboard_layout_keeps_restored_workspace_shell():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "板块资金监控工作台" in html
    assert 'id="status-text"' in html
    assert 'id="session-deskbar"' in html
    assert 'id="sector-intel-ribbon"' in html
    assert 'id="comparison-chart"' in html
    assert 'id="analysis-title"' in html
    assert 'id="sector-spotlight"' in html
    assert 'id="sector-stocks-body"' in html
    assert 'id="individual-body"' in html

    assert ".dashboard-grid" in css
    assert ".analysis-grid" in css
    assert ".hero-grid" in css
    assert ".session-deskbar" in css
    assert ".intel-ribbon" in css
    assert ".command-grid" in css
    assert ".sector-spotlight" in css
    assert ".rank-item-detail-grid" in css
    assert ".rank-tag" in css
    assert ".table-tag-stack" in css
    assert "grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) minmax(0, 1fr);" in css


def test_dashboard_analysis_workspace_removes_duplicate_detail_trend_chart():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="detail-chart"' not in html
    assert 'id="history-title"' not in html
    assert 'id="history-state"' not in html
    assert "detailChart" not in script
    assert "history-state" not in script
    assert "分钟趋势" not in html


def test_sector_stocks_panel_uses_background_refresh_and_stale_request_guard():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "requestToken: 0" in script
    assert "function sectorStocksContextKey(input)" in script
    assert 'background_refresh: String(!forceRefresh)' in script
    assert 'payload.source_status === "refreshing"' in script
    assert "暂无缓存，已转后台刷新" in script
    assert "后台刷新中，稍后会自动回填结果" in script
    assert "if (requestToken !== state.sectorStocks.requestToken) return;" in script


def test_dashboard_normalizes_selected_sector_when_switching_rank_source():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "function normalizeSelectedSector(candidateNames, fallbackName)" in script
    assert "const overviewSectorNames = [" in script
    assert "if (!normalizeSelectedSector(overviewSectorNames, overview.leaders[0]?.sector_name || overview.laggards[0]?.sector_name || null))" in script


def test_generated_runtime_artifacts_are_ignored_and_database_is_not_lfs_tracked():
    gitignore = (STATIC_DIR.parents[1] / ".gitignore").read_text(encoding="utf-8")
    gitattributes = (STATIC_DIR.parents[1] / ".gitattributes").read_text(encoding="utf-8")

    for pattern in ["data/*.db", "data/*.db-*", "server-*.log", "artifacts/"]:
        assert pattern in gitignore
    assert "sector_fund_monitor.db filter=lfs" not in gitattributes
