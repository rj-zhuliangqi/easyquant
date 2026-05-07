# Sector Fund Monitor Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the dashboard to compare all sectors by normalized fund-flow strength, add alerts, multi-day history, daily aggregation, and trading-hours-aware sampling.

**Architecture:** Keep the existing FastAPI + SQLite app, but expand the query layer to compute comparison metrics and historical aggregations from stored minute snapshots. The frontend becomes a comparison console with control state for sector type, metric, granularity, lookback window, and top-N overlays.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler, AKShare, pytest, HTML/CSS/JavaScript, ECharts

---

## File Map

- Modify: `app/main.py`
- Modify: `app/services/collector.py`
- Create: `app/services/market_time.py`
- Modify: `app/services/dashboard.py`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Modify: `tests/test_dashboard_service.py`
- Modify: `tests/test_api.py`

### Task 1: Lock in failing tests for metric comparison and history
- [ ] Add service tests for normalized rankings, multi-sector comparison series, day aggregation, alerts, and trading-time checks.
- [ ] Run `uv run pytest tests/test_dashboard_service.py -v` and confirm failure before implementation.

### Task 2: Implement market-hours-aware collection
- [ ] Add trading-session helper functions for A-share hours.
- [ ] Update scheduler-triggered collection to skip non-trading time.
- [ ] Keep manual refresh available.

### Task 3: Implement comparison and alert queries
- [ ] Add normalized metric helpers (`net_strength` first).
- [ ] Add multi-sector comparison API support for minute/day and multi-day lookback.
- [ ] Add single-sector history API support for minute/day and multi-day lookback.
- [ ] Add alert detection based on strength delta and rank change.

### Task 4: Lock in failing API tests
- [ ] Add API tests for comparison, alerts, and market status.
- [ ] Run `uv run pytest tests/test_api.py -v` and confirm failure before route updates.
- [ ] Wire new routes and response payloads.

### Task 5: Rebuild frontend as comparison dashboard
- [ ] Replace single-sector main chart with multi-sector comparison chart.
- [ ] Add controls for metric, granularity, lookback days, and top-N.
- [ ] Add alert panel and keep sector drill-down detail/table.

### Task 6: Verify end to end
- [ ] Run `uv run pytest -v`.
- [ ] Start the app locally, verify key endpoints with live AKShare data, and confirm scheduler status outside trading hours.
