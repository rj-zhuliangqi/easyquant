# AI Stock Research Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one stock-research Codex skill that persists research output into the app database and imports the resulting picks into the existing AI Center.

**Architecture:** Add a dedicated research ledger in the app database, then route the selected candidates through the existing `AiCenterService.import_run()` path so downstream AI Center features need no separate integration layer. Keep the scoring deterministic and transparent so tests stay stable.

**Tech Stack:** Python 3.11+, SQLAlchemy, FastAPI app models/services, pytest, Codex personal skills.

---

### Task 1: Add failing tests for the research loop

**Files:**
- Modify: `tests/test_ai_center.py`
- Test: `tests/test_ai_center.py`

- [ ] **Step 1: Add a failing service-level integration test**

Add a test that:
- builds the in-memory app database,
- seeds no stock research data,
- runs a future `StockResearchService`,
- expects one research run, multiple research items, and one imported AI Center run.

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `uv run pytest -q tests/test_ai_center.py -k stock_research`

Expected: FAIL because `StockResearchService` or the new models do not exist yet.

- [ ] **Step 3: Commit the red state mentally and do not write production code before the failure is seen**

No file change in this step.

### Task 2: Add research ledger models

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_ai_center.py`

- [ ] **Step 1: Add `AiStockResearchRun` and `AiStockResearchItem` models**

Include:
- primary keys,
- indexes on trading date and run id,
- JSON stored as `Text`,
- optional `ai_run_id` link for the imported AI Center run,
- unique ordering boundary for `run_id + stock_code`.

- [ ] **Step 2: Run the targeted test to see the next failure**

Run: `uv run pytest -q tests/test_ai_center.py -k stock_research`

Expected: FAIL because the service implementation still does not exist.

### Task 3: Implement the stock research service

**Files:**
- Add: `app/services/stock_research.py`
- Modify: `tests/test_ai_center.py`

- [ ] **Step 1: Implement deterministic candidate scoring and persistence**

Service responsibilities:
- fetch market-wide candidates from the gateway,
- normalize records,
- rank by simple score using available net flow and change percent,
- persist one run row and item rows,
- create or reuse AI skill metadata,
- call `AiCenterService.import_run()`,
- update the research run with `ai_run_id` and summary JSON.

- [ ] **Step 2: Re-run the targeted test**

Run: `uv run pytest -q tests/test_ai_center.py -k stock_research`

Expected: PASS for the new stock research test.

### Task 4: Add a callable script entry and wire config defaults

**Files:**
- Add: `app/run_stock_research.py`
- Modify: `app/config.py`
- Test: `tests/test_ai_center.py`

- [ ] **Step 1: Add optional config paths for stock research outputs if needed**

Only add config constants if the runner needs them.

- [ ] **Step 2: Add a minimal CLI module**

The module should:
- accept `--trading-date`, `--limit`, and `--mode`,
- create a session with `create_session_factory()`,
- instantiate the gateway and service,
- print a compact JSON-like summary.

- [ ] **Step 3: Run the same targeted test suite**

Run: `uv run pytest -q tests/test_ai_center.py -k "stock_research or ai_import"`

Expected: PASS.

### Task 5: Create the Codex skill

**Files:**
- Create: `C:\Users\ruijie\.codex\skills\ai-stock-research-pipeline\SKILL.md`
- Create: `C:\Users\ruijie\.codex\skills\ai-stock-research-pipeline\agents\openai.yaml`
- Create: `C:\Users\ruijie\.codex\skills\ai-stock-research-pipeline\scripts\run-example.ps1`

- [ ] **Step 1: Initialize the skill scaffold**

Use the system `init_skill.py` helper with `scripts` resources.

- [ ] **Step 2: Replace the template with a real workflow**

The skill must tell Codex to:
- inspect the project path,
- run `uv run python -m app.run_stock_research`,
- verify database rows or AI Center endpoints,
- avoid re-implementing the research logic inline.

- [ ] **Step 3: Validate the skill**

Run: `python C:\Users\ruijie\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\ruijie\.codex\skills\ai-stock-research-pipeline`

Expected: validation passes.

### Task 6: Verify the end-to-end loop

**Files:**
- No code changes required unless verification exposes a bug.

- [ ] **Step 1: Run focused automated tests**

Run: `uv run pytest -q tests/test_ai_center.py`

Expected: PASS.

- [ ] **Step 2: Run one manual research execution**

Run: `uv run python -m app.run_stock_research --trading-date 2026-05-08 --limit 3`

Expected: summary output shows one research run, imported AI run metadata, and non-zero candidate count.

- [ ] **Step 3: Spot-check the persisted result**

Run a small query or service read to confirm:
- research run exists,
- research items exist,
- AI Center picks exist for the same trading date.
