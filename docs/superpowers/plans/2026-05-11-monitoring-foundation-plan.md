# Monitoring Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconnect the app entrypoints to the structured realtime cache layer and add a first monitoring-signals API on top of stored board snapshots.

**Architecture:** Keep `FundFlowSnapshot` as the core board timeline, use `RealtimeCacheService` for individual rankings and sector constituents, and expose a small read-only signals endpoint that derives acceleration, persistence, and price/flow divergence from cached minute snapshots. The scheduler should continue collecting board snapshots every minute while also refreshing the cached individual rankings.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pandas, pytest

---

### Task 1: Lock the API surface with tests

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\tests\test_api.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\tests\test_dashboard_service.py`

- [ ] Add API tests for cached `sector-stocks`, cached `individual-rankings`, and a new `monitor-signals` endpoint.
- [ ] Add dashboard service tests for signal calculations such as acceleration, persistence, and divergence.

### Task 2: Reconnect the app entrypoints

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\main.py`

- [ ] Instantiate `RealtimeCacheService` in `create_app`.
- [ ] Route `/api/sector-stocks` and `/api/individual-rankings` through the cache service with paging/sorting parameters.
- [ ] Add `/api/monitor-signals`.
- [ ] Refresh individual rankings inside `/api/refresh` and the scheduler tick.

### Task 3: Implement the first monitoring signals

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\dashboard.py`

- [ ] Add a service method that derives board monitoring signals from recent snapshots on a trading date.
- [ ] Return concise per-board metrics for:
- [ ] 1-sample acceleration
- [ ] 3-sample acceleration
- [ ] positive/negative persistence count
- [ ] price/flow divergence flag
- [ ] Keep the response simple enough for the current frontend to consume later.

### Task 4: Verify

**Files:**
- No code changes expected

- [ ] Run targeted tests first.
- [ ] Run `uv run pytest -q`.
- [ ] Smoke-check `/api/status`, `/api/individual-rankings`, and `/api/monitor-signals`.
