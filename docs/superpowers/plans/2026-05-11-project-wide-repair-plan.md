# Project-Wide Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the project end-to-end so data collection, cache freshness, board name mapping, chart continuity, detail drilldown, and frontend refresh behavior all work consistently during trading hours.

**Architecture:** Treat `FundFlowSnapshot` as the authoritative board timeline, `SectorStockSnapshot` and `IndividualStockSnapshot` as structured realtime caches, and make every user-facing panel read from stored snapshots first with controlled refresh and explicit fallback. The frontend should only render boards that truly exist in the current dataset or have been mapped to a valid canonical board name, and every timed refresh must align with backend cache TTL behavior.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pandas, APScheduler, vanilla JS, ECharts, pytest

---

### Task 1: Stabilize startup and scheduler writes

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\main.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\realtime_cache.py`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_realtime_cache.py`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_api.py`

- [ ] **Step 1: Add failing tests for startup-safe cache refresh**

Add tests that cover:
- duplicate stock codes in one individual snapshot
- stale cache refresh for current trading day
- fallback to stale cache when live refresh fails

Run:
```powershell
uv run pytest -q tests/test_realtime_cache.py
```

Expected before implementation:
- duplicate code write or stale cache behavior fails

- [ ] **Step 2: Make `RealtimeCacheService` idempotent within one snapshot**

Implementation requirements:
- deduplicate `IndividualStockSnapshot` rows by `stock_code` before insert
- keep the first valid row for a duplicated code
- keep current `SectorStockSnapshot` insert behavior
- never let scheduler startup crash on repeated codes from upstream

- [ ] **Step 3: Make scheduler refresh explicit and predictable**

In `app/main.py`:
- keep board snapshot collection in `_collect_once`
- keep individual rankings refresh in `_collect_once`
- ensure scheduler startup uses the same safe refresh path as runtime ticks

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_realtime_cache.py tests/test_api.py
```

Expected:
- PASS

### Task 2: Normalize board names and canonical board selection

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\akshare_client.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\dashboard.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_akshare_client.py`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_api.py`

- [ ] **Step 1: Add failing tests for alias board names**

Cover cases such as:
- old watchlist names not matching current AKShare canonical names
- included watchlist board names that have no actual points for the day
- fuzzy mapping from local alias to current canonical board name

Run:
```powershell
uv run pytest -q tests/test_akshare_client.py tests/test_api.py
```

- [ ] **Step 2: Introduce canonical board name resolution**

In `app/akshare_client.py`:
- add a method that resolves a user-facing watchlist name to a canonical current board name
- match exact name first
- then normalized alias
- then contains/fuzzy match
- return `None` when no safe match exists

- [ ] **Step 3: Stop surfacing phantom watchlist boards**

In `app/services/dashboard.py`:
- do not include watchlist names in comparison output unless they either:
  - exist in the current trading date snapshot set, or
  - can be resolved to a canonical board name first

In `app/static/app.js`:
- if a watchlist board cannot be resolved, show it as invalid and exclude it from chart requests

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_akshare_client.py tests/test_api.py
```

Expected:
- alias boards either resolve to a real board or are explicitly marked unavailable

### Task 3: Fix chart continuity and sampling gaps

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\dashboard.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_dashboard_service.py`

- [ ] **Step 1: Add failing tests for sparse minute snapshots**

Cover:
- missing minutes inside a trading session
- watchlist boards with fewer points than the chart x-axis
- normalized first point remaining at `0`

Run:
```powershell
uv run pytest -q tests/test_dashboard_service.py
```

- [ ] **Step 2: Fill chart gaps on the backend**

In `app/services/dashboard.py`:
- build a canonical minute label timeline for the selected trading date
- for each series, emit points for every minute label in that timeline
- use forward-fill for short intraday gaps after the first valid point
- keep leading minutes before the first valid point as `null`
- keep post-session data excluded

- [ ] **Step 3: Render chart gaps intentionally on the frontend**

In `app/static/app.js`:
- keep `connectNulls: false`
- rely on backend-filled series so short missing intervals no longer appear as broken lines
- add a subtle badge if the dataset had missing sample minutes

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_dashboard_service.py
```

Expected:
- no broken line from single-minute collection gaps

### Task 4: Repair realtime cache freshness end-to-end

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\realtime_cache.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_realtime_cache.py`

- [ ] **Step 1: Add failing tests for stale cache TTL**

Cover:
- current-day individual rankings older than TTL should refresh
- current-day sector stock cache older than TTL should refresh
- historical trading dates should not auto-refresh

- [ ] **Step 2: Make TTL rules explicit**

Implementation rules:
- current trading date:
  - individual rankings refresh when older than configured TTL
  - sector stocks refresh when older than configured TTL
- historical trading dates:
  - always serve stored snapshots only
- refresh failure:
  - fall back to latest available snapshot and mark `stale_cache`

- [ ] **Step 3: Align frontend auto-refresh with backend TTL**

In `app/static/app.js`:
- refresh comparison, workspace, sector stocks, and individual rankings on the same minute heartbeat
- do not keep reusing old panel state if refreshed payload has a newer `updated_at`
- show panel-level update time beside each table

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_realtime_cache.py
```

Expected:
- cache freshness behavior is deterministic

### Task 5: Add pre-sampling for selected boards

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\main.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\realtime_cache.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_api.py`

- [ ] **Step 1: Add failing tests for scheduled board prefetch**

Cover:
- scheduler can refresh a configured list of watchlist boards into `SectorStockSnapshot`
- refresh endpoint can prefetch one or more explicit boards

- [ ] **Step 2: Introduce explicit prefetch inputs**

Implementation requirements:
- backend accepts a list of prioritized boards for prefetch
- scheduler refreshes these boards after the main board snapshot pass
- keep this list small and controlled

- [ ] **Step 3: Persist watchlist-driven prefetch state**

Choose one of:
- local settings file, or
- lightweight database table

Recommended:
- add a tiny table for watched boards with `sector_type`, `sector_name`, `enabled`

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_api.py
```

Expected:
- selected boards receive fresh constituent snapshots during trading hours

### Task 6: Repair the frontend data contract

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\index.html`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\styles.css`

- [ ] **Step 1: Cleanly separate four panel states**

Panels:
- comparison chart
- board workspace
- sector stock table
- individual ranking table

Each panel should independently show:
- loading
- fresh data
- stale cache
- unavailable

- [ ] **Step 2: Show panel update times and stale-state badges**

For sector stocks and individual rankings:
- render `updated_at`
- render source state badge
- render whether data came from fresh pull or cache fallback

- [ ] **Step 3: Fix watchlist persistence UX**

Rules:
- invalid watchlist boards remain visible but marked unavailable
- user can remove or remap them
- only valid boards participate in comparison requests

- [ ] **Step 4: Verify**

Run:
```powershell
node --check C:\Users\ruijie\Documents\New project 2\app\static\app.js
```

Expected:
- syntax passes

### Task 7: Expand monitoring metrics on top of repaired data

**Files:**
- Modify: `C:\Users\ruijie\Documents\New project 2\app\services\dashboard.py`
- Modify: `C:\Users\ruijie\Documents\New project 2\app\static\app.js`
- Test: `C:\Users\ruijie\Documents\New project 2\tests\test_dashboard_service.py`

- [ ] **Step 1: Extend the signals payload**

Add:
- acceleration over 1, 3, and 5 samples
- positive/negative persistence direction
- price/flow divergence class
- board breadth placeholder when sector constituents exist

- [ ] **Step 2: Only compute breadth when constituent cache is fresh enough**

Rules:
- derive breadth from the latest board constituent snapshot
- if constituent cache is missing or stale, return `null` instead of fake breadth

- [ ] **Step 3: Surface top signals in the UI**

Add:
- a compact monitor card or list for strongest acceleration
- a compact divergence list

- [ ] **Step 4: Verify**

Run:
```powershell
uv run pytest -q tests/test_dashboard_service.py
```

Expected:
- monitor signals are stable and interpretable

### Task 8: Final verification and operational handoff

**Files:**
- Modify if needed: `C:\Users\ruijie\Documents\New project 2\README.md`

- [ ] **Step 1: Run full verification**

Run:
```powershell
uv run pytest -q
node --check C:\Users\ruijie\Documents\New project 2\app\static\app.js
```

Expected:
- all tests pass
- frontend script passes syntax check

- [ ] **Step 2: Restart the service on the repaired code**

Run the local restart flow and confirm:
- `/api/status`
- `/api/individual-rankings`
- `/api/sector-stocks`
- `/api/comparison`
- `/api/monitor-signals`

- [ ] **Step 3: Manual smoke checklist**

Verify in the browser:
- comparison chart no longer shows phantom watchlist boards
- valid watchlist boards draw continuously through short collection gaps
- individual ranking table updates timestamps during trading
- sector stocks update after TTL or watchlist prefetch
- invalid watchlist names are explicitly marked and removable
