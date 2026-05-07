# Sector Fund Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app that samples AKShare industry and concept fund-flow snapshots each minute, stores them, and visualizes live rankings and intraday curves.

**Architecture:** A FastAPI backend runs a scheduled collector that fetches AKShare snapshots, normalizes them, and stores minute-level rows in SQLite. The same app serves JSON APIs plus a lightweight ECharts dashboard for rankings, curves, and sector drill-down into stock-level fund flow.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, APScheduler, AKShare, pandas, pytest, httpx, HTML/CSS/JavaScript, ECharts

---

## File Map

- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/models.py`
- Create: `app/schemas.py`
- Create: `app/akshare_client.py`
- Create: `app/services/collector.py`
- Create: `app/services/dashboard.py`
- Create: `app/main.py`
- Create: `app/static/index.html`
- Create: `app/static/app.js`
- Create: `app/static/styles.css`
- Create: `tests/conftest.py`
- Create: `tests/test_collector.py`
- Create: `tests/test_dashboard_service.py`
- Create: `tests/test_api.py`

### Task 1: Project bootstrap and dependency wiring
- [ ] Add `pyproject.toml` with runtime and test dependencies.
- [ ] Create app package skeleton and test package skeleton.
- [ ] Create a README-quality run target in `pyproject.toml` scripts if helpful.

### Task 2: Failing tests for snapshot normalization and persistence
- [ ] Write a collector test that feeds mocked AKShare rows and expects normalized `SnapshotRecord` values.
- [ ] Run `uv run pytest tests/test_collector.py -v` and confirm the test fails for missing implementation.
- [ ] Implement minimal database models, schemas, and collector code to make the test pass.
- [ ] Re-run `uv run pytest tests/test_collector.py -v` until green.

### Task 3: Failing tests for dashboard queries
- [ ] Write service tests for latest rankings, intraday minute series, and sector detail queries.
- [ ] Run `uv run pytest tests/test_dashboard_service.py -v` and confirm failure before implementation.
- [ ] Implement repository/query helpers to satisfy those tests.
- [ ] Re-run the service tests until green.

### Task 4: Failing tests for HTTP API
- [ ] Write API tests covering dashboard summary, time-series endpoint, manual refresh endpoint, and stock drill-down endpoint.
- [ ] Run `uv run pytest tests/test_api.py -v` and confirm failure before wiring routes.
- [ ] Implement FastAPI routes and app startup behavior.
- [ ] Re-run the API tests until green.

### Task 5: Frontend dashboard
- [ ] Build a single-page dashboard with industry/concept tabs, rankings, ECharts minute curve, and drill-down table.
- [ ] Manually verify the page against the API in a local browser.
- [ ] Refine loading, empty, and error states.

### Task 6: Real-data integration and end-to-end verification
- [ ] Install dependencies with `uv sync`.
- [ ] Run a direct AKShare smoke script to verify `stock_fund_flow_industry(symbol="即时")`, `stock_fund_flow_concept(symbol="即时")`, `stock_fund_flow_individual(symbol="即时")`, and `stock_sector_fund_flow_summary(...)`.
- [ ] Run the app locally, trigger snapshot refresh, and verify the dashboard updates with live data.
- [ ] Run the full test suite and record exact commands/output before claiming completion.
