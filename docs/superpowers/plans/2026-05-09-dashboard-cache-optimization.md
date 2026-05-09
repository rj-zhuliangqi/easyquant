# Dashboard Cache Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured caching for sector component stocks and market-wide stock rankings, then update API and frontend behavior to read cached data first and recover gracefully when catalog data is empty.

**Architecture:** Keep minute-level sector snapshots as the existing core dataset, add two new snapshot tables for drill-down data, and centralize cache read-through logic in a dedicated service. Backend endpoints will prefer stored snapshots and only fetch live data on cache miss or explicit refresh, while the frontend clarifies which widgets are board-specific versus market-wide and improves selection fallback.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pandas, vanilla JS, ECharts, pytest

---

### Task 1: Lock Cache Behavior with Tests

**Files:**
- Modify: `tests/test_api.py`
- Create: `tests/test_realtime_cache.py`

- [ ] Add failing tests for sector stock cache reuse, individual ranking cache reuse, and sector catalog fallback.
- [ ] Run targeted pytest commands and confirm they fail for the expected missing model/service behavior.
- [ ] Keep the tests focused on read-through caching and response payload shape.

### Task 2: Add Structured Snapshot Models

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_realtime_cache.py`

- [ ] Define normalized SQLAlchemy models for sector component stock snapshots and market-wide individual stock snapshots.
- [ ] Add uniqueness boundaries that prevent duplicate rows for the same capture minute and stock code.
- [ ] Re-run the cache tests and confirm failures now move from import/schema gaps to missing service logic.

### Task 3: Implement Read-Through Cache Service

**Files:**
- Create: `app/services/realtime_cache.py`
- Modify: `app/services/__init__` only if needed
- Test: `tests/test_realtime_cache.py`

- [ ] Implement one service that loads latest cached rows by sector/date or day/date, fetches from AKShare on miss, persists normalized rows, and returns response-ready dictionaries.
- [ ] Re-run targeted cache tests until they pass.

### Task 4: Wire Cache Service into FastAPI Endpoints and Refresh Flow

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

- [ ] Update `/api/sector-stocks`, `/api/individual-rankings`, `/api/sector-catalog`, `/api/refresh`, and scheduled collection flow to use the new cache behavior.
- [ ] Verify integration tests cover empty catalog fallback and refresh/cached reads.

### Task 5: Improve Frontend Interaction and Layout

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/static/index.html`
- Modify: `app/static/styles.css`

- [ ] Fix watchlist option fallback when catalog endpoints return empty lists.
- [ ] Make the drill-down zone visually distinguish board-specific data from the market-wide stock ranking.
- [ ] Improve spacing, panel hierarchy, and mobile behavior without changing the overall workflow.

### Task 6: Final Verification

**Files:**
- Verify only

- [ ] Run targeted tests for cache and API behavior.
- [ ] Run the full pytest suite.
- [ ] Review the diff for unintended regressions before reporting completion.
