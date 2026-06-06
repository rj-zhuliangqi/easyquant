from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_watchlist_controls_keep_select_based_flow() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="watchlist-type-select"' in html
    assert 'id="watchlist-sector-search"' in html
    assert 'id="watchlist-sector-search-meta"' in html
    assert 'id="watchlist-sector-select"' in html
    assert 'id="watchlist-add-button"' in html
    assert 'id="watchlist-chips"' in html
    assert "watchlistSearchQuery:" in script
    assert "function filterSectorOptions(query, sectorType = state.watchlistFormType)" in script
    assert "function renderWatchlistControls()" in script
    assert 'document.getElementById("watchlist-type-select")' in script
    assert 'document.getElementById("watchlist-sector-search")' in script
    assert 'document.getElementById("watchlist-sector-select")' in script
    assert 'watchlist-sector-search-meta' in script
