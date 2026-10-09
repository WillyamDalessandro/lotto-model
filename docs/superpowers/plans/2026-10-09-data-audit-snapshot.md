# Data Audit and Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified, portable main-Lotto research snapshot and a reconciled audit without training models.

**Architecture:** A new audit package reads a consistent database view, applies explicit eligibility and schedule rules, and writes deterministic evidence-inclusive bundles. A content-addressed registry records verified bundles; standalone verification requires neither database nor network.

**Tech Stack:** Existing Python 3.12, PostgreSQL, SQLAlchemy, Alembic, Pydantic, Typer and pytest; standard-library CSV/JSON/hash/file operations.

**Spec:** `docs/superpowers/specs/2026-10-09-data-audit-snapshot.md` (draft; review alongside this plan before implementation).

## Global Constraints

- Game is fixed to `lotto` for version 1; unsupported games fail explicitly.
- Runtime: Python >=3.12,<3.13; no new runtime dependency.
- Schema version is 1.
- Outputs remain under ignored `data/` by default. No raw evidence is committed or published.
- Zero eligible draws blocks snapshot creation. A report on an empty database remains valid.
- No collection, training, holdout selection or purchasing in this phase.
- Preserve concurrent collection edits; recheck schema head and source contracts when execution begins.

## Review Focus

- Valid other-game draws on the same date must not satisfy main-Lotto schedule coverage (Task 2).
- Unknown schedules and missing scheduled dates must remain separate (Task 2).
- Missing, escaped or corrupted evidence must prevent inclusion (Tasks 1/2).
- Database surrogate-ID changes after reconstruction must preserve content identity (Tasks 3/4).
- Partial writes and a failed registry transaction must permit safe retry without overwriting a completed bundle (Task 4).

## File structure and shared types

Create `src/lotto_model/audit/{__init__,contracts,reader,eligibility,bundle,registry,commands}.py`. Contracts owns Pydantic models and pure normalization; reader owns SQL and evidence loading; eligibility owns audit policy; bundle owns serialization and standalone verification; registry owns the sole database mutation; commands owns CLI composition.

Create unit tests in `tests/audit/` and database tests in `tests/integration/test_audit.py` and `test_snapshots.py`. Extend `src/lotto_model/cli.py`; add a new migration after the current head. Document operations in `docs/data-audit.md`; update README status without claiming real data coverage.

Models in `contracts.py`: `AuditRequest(game: Literal['lotto'], start: date, end: date)`, `RuleBindings(version: Literal[1], rules: list[RuleBinding], calendar_events: list[str])`, `RuleBinding(rule_code: str, artifact_sha256: str, source_url: str)`; `AuditInputs` contains normalized draws, rules, observations, issues, enrichment, reviewed exceptions and verified evidence bytes; `AuditResult` contains eligible draws, exclusions, counts, schedule classifications, warnings and bundle lineage; `SnapshotResult(path: Path, content_sha256: str, included_draws: int)`; `VerificationResult(content_sha256: str, included_draws: int)`. Dates and decimals stay typed until serialization. These interfaces are shared by every task.

### Task 1: contracts and consistent input reader

**Files:** contracts.py, reader.py, tests/audit/test_contracts.py, tests/integration/test_audit.py.

**Interfaces:** `read_inputs(connection: Connection, request: AuditRequest, evidence_root: Path, bindings: RuleBindings | None) -> AuditInputs`; `read_evidence(path: str, expected_sha256: str, evidence_root: Path) -> bytes`.

- [ ] Add `test_request_and_bindings_validation`: reversed dates, game `lotto_plus`, version 2, duplicate rule codes and malformed hashes raise validation errors; equal dates and empty event lists are valid.
- [ ] Add `test_evidence_resolution`: relative/absolute contained paths return original bytes; outside-root paths, missing files and wrong SHA-256 fail. Include symlink escape where supported.
- [ ] Add `test_reader_preserves_population`: one dated main-Lotto draw, one Plus draw and an undated academic observation return separate populations; a URL shared by two distinct artifact hashes is resolved only by exact binding; duplicate hash/URL matches fail as ambiguous.
- [ ] Run `python -m uv run pytest tests/audit/test_contracts.py tests/integration/test_audit.py -q`; confirm failures concern absent contracts/reader behaviour.
- [ ] Implement typed contracts and parameterized SQL reads. Use game/date predicates, retain relevant contradictory observations and original payloads, and validate evidence before adding bytes to AuditInputs. Do not mutate or infer missing dates.
- [ ] Add `test_repeatable_read_view`: in two dedicated test connections, a committed correction after the first read remains invisible within the audit transaction; a new transaction sees it. Use scoped fixture rows and clean up committed data.
- [ ] Run the same targeted tests; require all pass. Commit only task files with `feat: add consistent audit input reader`.

### Task 2: eligibility, schedules and audit reconciliation

**Files:** eligibility.py, tests/audit/test_eligibility.py, tests/integration/test_audit.py.

**Interfaces:** `audit_inputs(inputs: AuditInputs, request: AuditRequest) -> AuditResult`; consumes Task 1 models. No database or filesystem writes.

- [ ] Add `test_draw_eligibility_reasons`: accepted `[1,2,3,4,5,6]`, null bonus and verified in-range rule is included; duplicate/out-of-pool mains, mismatching accepted payload, invalid bonus, unresolved number conflict or missing rule binding produces the exact respective reason code: `invalid_mains`, `observation_mismatch`, `invalid_bonus`, `number_conflict`, `unverified_rule`. Use `invalid_status`, `rule_mismatch`, `invalid_evidence` for the other specified failures; retain all applicable reasons in sorted order.
- [ ] Add `test_schedule_populations`: for 2026-10-05 through 2026-10-08, Monday/Wednesday schedule and only Wednesday eligible yields expected=2, eligible_observed=1, missing_dates=['2026-10-05']; a Plus draw on Monday does not change it. Empty schedule yields unknown_schedule_days=4 and no missing-date claim.
- [ ] Add `test_boundaries_and_exceptions`: inclusive rule end/start are respected; overlap and conflicting scoped events block creation; Tuesday observation without reviewed exception yields unexpected_dates=['2026-10-06']; an explicit reviewed Tuesday event clears that classification.
- [ ] Add `test_enrichment_does_not_drop_numbers`: a prize conflict preserves the eligible draw, flags the disputed tier and excludes it from totals; unknown amounts remain null. Unverifiable enrichment is omitted with a count/reason.
- [ ] Run `python -m uv run pytest tests/audit/test_eligibility.py tests/integration/test_audit.py -q` and confirm intended failures.
- [ ] Implement eligibility with existing DrawInput where compatible, explicitly allowing unknown bonus. Derive coverage from scoped rules/events rather than cached observed flags; represent blocking conditions in AuditResult for snapshot creation to reject. Reconcile canonical candidate counts as included plus excluded, and track observation populations separately.
- [ ] Run targeted tests and commit with `feat: audit draw eligibility and schedule coverage`.

### Task 3: deterministic bundles and independent verification

**Files:** bundle.py, tests/audit/test_bundle.py.

**Interfaces:** `build_content(audit: AuditResult, request: AuditRequest) -> dict[str, bytes]`; `content_digest(files: dict[str, bytes]) -> str`; `verify_bundle(path: Path) -> VerificationResult`.

- [ ] Add `test_canonical_serialization`: shuffled input order yields identical bytes; main columns are sorted; null bonus is an empty CSV field; decimal `1.20` stays a JSON string; UTC metadata ends with Z. Require final LF and the spec's fixed draw columns.
- [ ] Add `test_portable_identity`: alter only database IDs, absolute evidence paths and run IDs in equivalent inputs; assert equal files and equal digests. Alter one canonical number with matching lineage; assert a different digest.
- [ ] Add `test_bundle_verification`: a complete valid fixture passes; changing one body byte, missing a file, extra content, unsafe manifest paths, symlinks, false count, invalid draw or missing lineage fails. Parameterize each failure and require ValueError rather than silent acceptance.
- [ ] Run `python -m uv run pytest tests/audit/test_bundle.py -q`; confirm intended failures.
- [ ] Implement all seven content categories from the spec, portable observation keys and manifest parsing. Exclude generated manifest metadata from content digest. Verification independently parses draws/rules/lineage, recomputes hashes, counts and eligibility rather than trusting audit counts.
- [ ] Run targeted tests and commit with `feat: build and verify portable dataset bundles`.

### Task 4: atomic publication and snapshot registry

**Files:** registry.py, bundle.py, new `migrations/versions/<next_revision>_snapshots.py`, tests/integration/test_snapshots.py, tests/audit/test_publication.py.

**Interfaces:** `publish_bundle(files: dict[str, bytes], metadata: dict, output_root: Path) -> SnapshotResult`; `register_snapshot(connection: Connection, result: SnapshotResult, request: AuditRequest) -> int`; `create_snapshot(engine: Engine, request: AuditRequest, evidence_root: Path, bindings: RuleBindings, output_root: Path, source_revision: str) -> SnapshotResult`.

- [ ] Confirm Alembic head at implementation time; select the next unused revision instead of changing frozen migrations.
- [ ] Add `test_registry_constraints_and_replay`: migration creates the spec's table; invalid hash/range/count fails; registering twice returns the same id and preserves first timestamp/path.
- [ ] Add `test_atomic_publication_and_retry`: inject a write failure and require no final directory; valid existing bundle is reused; corrupt existing bundle is rejected; failed registry transaction leaves a verifiable bundle and retry registers it exactly once. Snapshot creation with zero draws or unexpected dates produces no registered bundle.
- [ ] Run `python -m uv run pytest tests/audit/test_publication.py tests/integration/test_snapshots.py -q`; confirm intended failures.
- [ ] Implement temporary sibling publication, guarded cleanup, rename and verify-before-register. Use one REPEATABLE READ database transaction for input reading and registration. Never update canonical tables. Existing snapshot identity is insert-or-return.
- [ ] Add `test_reconstruction_identity`: rebuild equivalent synthetic observations/rules with different IDs and evidence locations in the isolated test database; require equal exported content hashes. Retain earlier finished bundle and verify it after source correction.
- [ ] Run targeted tests plus `python -m uv run pytest tests/integration/test_database.py -q`; require migrations and constraints pass. Commit with `feat: register immutable audited snapshots`.

### Task 5: CLI, operator documentation and end-to-end delivery

**Files:** commands.py, cli.py, tests/audit/test_commands.py, docs/data-audit.md, README.md.

**Interfaces:** commands expose the exact `lotto audit report`, `snapshot` and `verify` options in the spec; verify is database/network independent. Reuse the project's sanitized error convention.

- [ ] Add `test_cli_contracts`: invalid dates exit nonzero; empty report exits zero with counts; empty snapshot exits nonzero; valid fixture snapshot prints digest/count/path; verify succeeds with DB configuration absent and fails on tampering. Assert error output contains no credentials or evidence body text.
- [ ] Run `python -m uv run pytest tests/audit/test_commands.py -q` and confirm intended failures.
- [ ] Compose reader/audit/bundle/registry and register the CLI group. Report emits JSON to stdout or --output; snapshot emits a JSON result. Preserve canonical/registry read-only report behaviour.
- [ ] Document binding review, evidence_root selection, gaps/exclusions, retry, standalone verification, ignored local artifacts and reconstruction. State that synthetic verification does not complete actual historical acquisition/audit.
- [ ] Run `docker compose --profile test up -d --wait`, `python -m uv run ruff check .`, `python -m uv run ruff format --check .`, `python -m uv run pytest -q`, and `git diff --check`. Require every command succeeds.
- [ ] Run `python -m uv run lotto audit --help` and each subcommand's help; run report and snapshot/verify against synthetic evidence through an explicitly configured isolated test database. Require a valid bundle and matching printed/verified digest; do not seed synthetic draws into research data.
- [ ] Commit only this phase's files. Resolve unrelated outstanding changes before merge; never stage or discard another task's changes. Merge the feature branch with local main following the user's workflow.
- [ ] Repeat application/runtime checks and full relevant tests on local main. On success, push using the configured remote/upstream; report actual coverage separately from software completion.

## Self-review and next handoff

Tasks 1–2 implement provenance and population rules; Task 3 fixes portability and integrity; Task 4 implements migration, consistency and crash recovery; Task 5 implements operations and the required delivery workflow. No actual data acquisition or model evaluation is inferred from these steps.

Review this spec/plan before execution, particularly the explicit rule-evidence binding, unknown-bonus policy and treatment of schedule gaps. Implementation should use its own feature branch once concurrent collection work is safely integrated or isolated.
