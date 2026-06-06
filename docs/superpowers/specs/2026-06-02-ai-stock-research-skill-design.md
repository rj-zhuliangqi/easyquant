# AI Stock Research Skill Design

## Goal
Build a Codex skill that researches a small basket of A-share stocks, persists the raw research results into the project database, and imports the structured picks into the existing AI Center so we can verify the full skill-to-database-to-AI-center loop.

## Scope
- Create one new Codex skill under `C:\Users\ruijie\.codex\skills`.
- Add project-side persistence for research runs and per-stock research items.
- Add one Python execution path that can be called manually or by the skill.
- Reuse the existing `AiCenterService.import_run()` contract for AI Center ingestion instead of inventing a second run schema.
- Verify the loop with automated tests and one end-to-end local execution.

## Architecture
The workflow has two data layers.

The first layer is a research ledger owned by this feature. A new service collects market-wide candidate stocks, applies simple ranking heuristics, records the full research run, and stores each candidate with its score, tags, reason, and source snapshot.

The second layer is the existing AI Center. After a research run is persisted, the same service builds a standard `import_run` payload and hands it to `AiCenterService.import_run()`. That keeps all downstream behavior, including AI Center pages, grouped picks, and T+1/T+3 outcomes, on the existing code path.

## Components
### Database models
- `AiStockResearchRun`
  - One row per skill execution.
  - Stores skill name, revision tag, trading date, run status, config snapshot, summary JSON, raw output text, and linked AI Center run id when import succeeds.
- `AiStockResearchItem`
  - One row per researched stock within a run.
  - Stores stock code, stock name, sector, rank score, confidence score, tags JSON, reason summary, and normalized quote metrics used in selection.

### Service
- `app/services/stock_research.py`
  - Fetch candidate stocks from the existing gateway, using the already normalized individual ranking data.
  - Score candidates with transparent heuristics so the test result is deterministic.
  - Persist the research run and items.
  - Ensure the matching AI skill, revision, and job exist or are created if absent.
  - Convert the top candidates into `structured_picks` and import them into AI Center.

### CLI entry
- `app/run_stock_research.py`
  - Small executable module that creates a session, runs the research service, and writes a compact terminal summary.
  - Accepts basic options such as trading date, limit, and mode so the skill can call it repeatedly.

### Codex skill
- `C:\Users\ruijie\.codex\skills\ai-stock-research-pipeline`
  - Instructs Codex to use the project script instead of recreating logic inline.
  - Includes one script-oriented workflow and concrete trigger phrases for discovery.

## Data flow
1. The skill invokes `uv run python -m app.run_stock_research`.
2. The runner creates a DB session and calls the research service.
3. The service fetches stock candidates and computes deterministic scores.
4. The service writes `AiStockResearchRun` and `AiStockResearchItem` rows.
5. The service creates or reuses AI Center metadata rows (`AiSkill`, `AiSkillRevision`, `AiJob`).
6. The service imports a standard AI Center run through `AiCenterService.import_run()`.
7. Existing AI Center endpoints expose the imported picks and outcomes.

## Error handling
- If market data fetch fails, mark the research run `failed`, store the error text, and do not create AI Center rows.
- If AI Center import fails after research persistence, keep the research run and mark it `partial_success` with the import error recorded.
- If a stock row is missing code or name after normalization, skip it and include the count in summary JSON instead of crashing the whole run.

## Testing
- Service test for research persistence and score ordering.
- Integration test that one research execution creates research tables plus an AI Center run and grouped picks.
- CLI smoke test is optional if the service-level path already covers the behavior.

## Assumptions
- The first version is a verification path, not a production alpha model.
- Candidate selection can rely on the current `fetch_individual_realtime` data shape already used by the project.
- The skill revision stored in AI Center can be text-based and lightweight; it does not need to mirror the full external skill folder.
