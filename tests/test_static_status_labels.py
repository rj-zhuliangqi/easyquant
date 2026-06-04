from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_sector_stocks_status_labels_cover_refresh_and_failure_states():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "暂无缓存，已转后台刷新" in script
    assert "后台刷新中，稍后会自动回填结果" in script
    assert "成分股读取失败，请稍后重试" in script
    assert 'updatePanelState("sector-stocks-state", "后台刷新中", "fresh")' in script
    assert 'updatePanelState("sector-stocks-state", "读取失败", "warning")' in script


def test_market_status_bar_keeps_recent_snapshot_copy():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'const marketLabel = status.market_open ? "交易中" : "非交易时段";' in script
    assert 'setStatus(`${marketLabel} | 最近采样 ${snapshotLabel} | 自选预采样 ${status.watched_sector_count} 个`);' in script
