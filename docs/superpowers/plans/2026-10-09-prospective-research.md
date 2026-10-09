# Prospective Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Issue immutable current-regime research lines before results and evaluate later observations without backfilling.

**Architecture:** A prospective ledger extends shared research contracts with server-time issuance, coordinated draw locks and revisioned scoring. Optional manual preparation is isolated behind complete budget/price configuration.

**Tech Stack:** Existing Python, SQLAlchemy/Alembic, Pydantic, Typer, Decimal/zoneinfo and pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-prospective-research.md`.

## Global Constraints

- Python >=3.12,<3.13; existing dependencies; no publication or automated purchase.
- Database server UTC time governs issuance; explicit timezone-aware deadlines required.
- Unknown rules/schedules/deadlines fail closed; no incompatible historical model transfer.
- Default review window is 100 completed draws, descriptive reporting only.
- Optional play requires supplied EUR limits and verified prices/minimum lines; never invent values.
- No automation schedule or browser source adapter is created implicitly.

## Review Focus

- Results arriving during issue preparation must prevent late issuance (Task 2).
- Rule transitions must reject ineligible numbers and stale models (Tasks 1/2).
- Missed issues and disputed outcomes must remain visible (Task 3).
- Corrections must revise scores without rewriting issued lines (Task 3).
- Concurrent reservations, retries and Dublin week/DST boundaries must respect both limits (Task 4).

### Task 1: reviewed current-regime protocol

**Files:** Create `src/lotto_model/prospective/{__init__,contracts,protocol}.py`, tests/prospective/test_protocol.py.

**Interfaces:** `ProspectiveProtocol` contains all spec inputs; `validate_protocol(protocol: ProspectiveProtocol, verified_rules: list[dict]) -> ProspectiveProtocol`; `freeze_prospective(protocol: ProspectiveProtocol, output_root: Path) -> Path`.

- [ ] Write `test_current_rule_contract`: pool=45 rejects lines containing 46/47; naive deadline, missing evidence/schedule and stale rule interval fail; reviewed uniform arm succeeds. Historical model arm without current-regime contract fails.
- [ ] Write `test_protocol_revision`: post-issue configuration changes fail; new arm requires forward start date; no retroactive start or guessed cutoff.
- [ ] Run `python -m uv run pytest tests/prospective/test_protocol.py -q`; expect missing interfaces; implement contract/freeze using verified Phase 3 evidence and shared hashes.
- [ ] Run targeted tests; commit `feat: freeze prospective current-regime protocols`.

### Task 2: atomic pre-result issuance

**Files:** Create prospective/ledger.py, issuance.py, next-head migration `<revision>_prospective.py`; modify ingestion/repository.py to coordinate the same draw lock; create tests/integration/test_prospective.py.

**Interfaces:** `lock_draw(connection: Connection, game: str, target_date: date) -> None` uses transaction advisory lock with a stable SHA-256-derived signed 64-bit game/date key; `issue(connection: Connection, protocol: ProspectiveProtocol, target_date: date) -> IssueResult` reads DB clock and returns issued/existing/missed/failed status. Issuance rows are immutable, with outcome/status events separate.

- [ ] Write `test_issuance_timing`: exact-deadline and later calls are missed, earlier valid calls issued; existing results refuse issue; no result-to-issue backfill; repeated identical call returns existing lines; changed budget/policy fails.
- [ ] Write `test_issue_ingestion_race`: two isolated test connections contend on the same lock; whichever commits the result first makes subsequent issuance fail; issuance checks clock after lock acquisition. Test whole-portfolio rollback and immutable-row trigger.
- [ ] Run `python -m uv run pytest tests/integration/test_prospective.py -q`; expect failures. Implement lock in both issuance and canonical ingestion, transaction clock checks, seed reproducibility and eligible line validation.
- [ ] Run prospective tests plus existing ingestion/integration suite; commit `feat: issue race-safe pre-result research records`.

### Task 3: result revisions and prospective coverage

**Files:** Create prospective/evaluation.py, reporting.py, commands.py, tests/prospective/test_reporting.py; extend test_prospective.py and cli.py; create docs/prospective-research.md.

**Interfaces:** `evaluate_available(connection: Connection, protocol_digest: str) -> dict`; `prospective_report(connection: Connection, protocol_digest: str) -> dict`. Evaluation identity includes issue and accepted result-evidence hash; latest accepted revision is explicit.

- [ ] Write `test_result_revisions`: same evidence scores once; quarantine stays pending/disputed; corrected accepted mains append new score revision and leave line bytes unchanged.
- [ ] Write `test_coverage_denominators`: fixtures with one completed issue, one missed issue and one disputed outcome yield separate counts; completed performance denominator=1, scheduled coverage denominator=3. Interim reports label descriptive and do not claim confirmed advantage.
- [ ] Run targeted tests; implement refresh via existing permitted imports, no automatic network scheduler. Add `lotto prospective protocol PATH`, `issue PROTOCOL --target-date DATE`, `evaluate PROTOCOL`, `report PROTOCOL`; sanitize errors and record missing windows.
- [ ] Verify synthetic future deadlines/current-rule fixtures in isolated test DB, with no real ticket or publication action. Run Ruff/full pytest/whitespace and runtime CLI checks; commit this deliverable.

### Task 4: optional manual preparation after configuration is supplied

**Files:** Create prospective/budget.py, tests/prospective/test_budget.py, tests/integration/test_budget.py; next unused migration for budget ledger; extend prospective commands/docs.

**Prerequisite:** Explicit opt-in and user-supplied per-draw/weekly limits plus dated price/minimum-line evidence. If absent, keep this task pending and deliver prospective research without pretending play support is implemented.

**Interfaces:** `BudgetConfig(per_draw_eur: Decimal, weekly_eur: Decimal, price_per_line_eur: Decimal, minimum_lines: int, evidence_hash: str, effective_start: date, effective_end: date | None)`; `reserve_preparation(connection: Connection, issue_id: int, lines: int, config: BudgetConfig) -> int`; `confirm_manual_spend(connection: Connection, reservation_id: int) -> None`; `cancel_preparation(connection: Connection, reservation_id: int) -> None`.

- [ ] Write tests: unknown limits/prices disable; negative/sub-cent values fail; exact-limit passes, one cent over fails; existing reservations count; retry returns same reservation; confirmation never double-charges; cancellation releases without erasing history; under-minimum retail lines fail.
- [ ] Write concurrency and week tests with Europe/Dublin Sunday/Monday across both DST transitions; require no aggregate reservation exceeds either limit. Use account/week lock plus per-draw lock with consistent ordering.
- [ ] Run targeted tests; implement Decimal cents, atomic reservations and manual-only CLI. Run runtime/full suite and document supplied values/evidence locally.
- [ ] Commit only approved component. For delivered scope, merge local main, repeat runtime/full Ruff/pytest/whitespace checks and push only after success. Report omitted optional scope explicitly if its prerequisites were not supplied.
