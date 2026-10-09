# Acquisition Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make permitted dated historical imports repeatable and report the remaining acquisition gaps accurately.

**Architecture:** An offline batch coordinator validates saved inputs, invokes existing repository operations in one transaction and writes a reproducible receipt. Coverage remains separate from a reviewed phase-completion assessment.

**Tech Stack:** Existing Python, Pydantic, SQLAlchemy, Typer and pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-acquisition-completion.md`.

## Global Constraints

- Python >=3.12,<3.13; existing runtime dependencies; sequential writers.
- permitted_use must be `local_research`; all batches require reviewed permission evidence.
- No network fetch, provider contact, publication or invented dates in batch processing.
- Receipts and source data stay under ignored data/.
- Actual completion depends on permitted dated draw/rule/prize/jackpot inputs.

## Review Focus

- Broken evidence or permission hashes must fail before canonical writes (Task 1).
- Failure after rules import must roll back the entire batch (Task 2).
- Undated academic rows must never become chronological draws (Task 2).
- Annual all-games metrics must never fill draw-level coverage gaps (Task 3).
- Exact replay and conflicting source corrections must preserve provenance (Task 2).

### Task 1: validate the offline acquisition contract

**Files:** Create `src/lotto_model/ingestion/batch.py`, `tests/ingestion/test_batch.py`.

**Interfaces:** `AcquisitionBatch` implements the spec's exact version-1 JSON fields; `validate_batch(path: Path) -> AcquisitionBatch` resolves and verifies all inputs without DB writes/network. `batch_digest(batch: AcquisitionBatch) -> str` hashes normalized configuration and input bytes, excluding absolute paths.

- [ ] Write `test_batch_validation`: version 2, unsupported adapter, missing paired records, invalid hash, outside-root path and absent permission fail; permitted_use='local_research' with verified inputs passes. Require no network calls.
- [ ] Run `python -m uv run pytest tests/ingestion/test_batch.py -q`; expect missing-interface failures.
- [ ] Implement validation using existing artifact/observation/complementary contracts. Reuse existing parsers; add a format adapter only after its actual export is available and reviewed, with a source-specific fixture/test.
- [ ] Run targeted tests; commit `feat: validate reviewed offline acquisition batches`.

### Task 2: transactional batch ingestion and receipts

**Files:** Modify batch.py and `src/lotto_model/ingestion/workflows.py` only to expose connection-scoped import; create `tests/integration/test_batch.py`.

**Interfaces:** `import_batch(connection: Connection, batch: AcquisitionBatch) -> dict` returns digest and imported/corroborated/staged/quarantined counts. `run_batch(engine: Engine, path: Path, receipt: Path | None) -> dict` validates first and wraps imports in one transaction. Existing import_manifest public behaviour remains compatible.

- [ ] Write `test_batch_rollback_and_replay`: invalid enrichment after valid rules/draws leaves no partial rows; two identical imports keep canonical counts stable; changed valid evidence is appended and conflicting numbers quarantined.
- [ ] Write `test_undated_and_unknown_rules`: undated combinations stay staged, no guessed draw_date, unknown regime stays staged, null bonus/prize/jackpot remains null.
- [ ] Run `python -m uv run pytest tests/integration/test_batch.py -q`; expect intended failures.
- [ ] Implement rule-first import with validated records and existing Repository semantics. Preserve source identity and permission receipt. Write receipt only after commit; an output failure is reported with committed status and safe replay instructions.
- [ ] Run targeted tests plus `tests/integration/test_import.py`; commit `feat: import acquisition batches transactionally`.

### Task 3: measured status and delivery

**Files:** Modify `src/lotto_model/ingestion/commands.py`, report.py; create `tests/ingestion/test_acquisition_status.py`, `docs/acquisition-completion.md`; update phase2-coverage.md only after measured real inputs.

**Interfaces:** `acquisition_status(connection: Connection) -> dict` separates dated main-Lotto, staged undated, annual all-games and mandatory-field coverage. Add exact CLI commands from spec.

- [ ] Write `test_status_requires_mandatory_inputs`: annual/undated rows alone leave dated coverage zero and complete=false; missing rule/prize/jackpot availability stays explicit. Write CLI tests for sanitized failure and receipt paths.
- [ ] Run `python -m uv run pytest tests/ingestion/test_acquisition_status.py -q`; expect failures; implement measured reporting and CLI.
- [ ] If permitted exports exist, run a reviewed batch twice, compare counts and reconstruct in the isolated test database. Otherwise document the exact missing inputs and report software readiness separately.
- [ ] Verify database/evidence backup restore with private artifacts; never overwrite research DB.
- [ ] Run Compose test service, DB health, batch/status CLI checks, Ruff lint/format, full pytest and git diff --check. Commit task files, merge with local main, repeat runtime/full checks, then push only after success. Resolve unrelated changes without staging/discarding them.
