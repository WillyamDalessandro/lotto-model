# Expanded collection implementation plan

> Execute inline with superpowers:executing-plans; request a fresh final review.

**Spec:** [Collection continuation](../specs/2026-10-09-expanded-collection.md).
**Branch:** codex/expanded-data-collection, base 79cb6c0.
**Authority:** user's approved phase 2 and subsequent collection instruction.

## Review focus

- Student/simulated selections must never enter real draw observations.
- Missing individual dates must remain null even though source order is known.
- Annual metrics must retain all-games scope, source sections, rounding and conflicts.
- Unreviewed policy changes, HTML errors and restricted redirects must stop collection.
- Idempotent replay must preserve evidence identity and never create canonical draws
  from undated results. Publication rights must not be implied by local acquisition.

## Task 1: Source parsers and acquisition

**Files:** ingestion/research_sources.py, contracts.py; tests/ingestion/test_research_sources.py.
**Produces:** validated UndatedObservation, parse_journal, parse_regulator and
collect_research returning observations and complementary records with artifacts.

- [ ] Write tests for mixed groups, unknown group, malformed numbers, exact source
  row retention, table headers/units, contradictory sections, malformed money and
  HTML errors. Expected: failures because new interfaces are missing.
- [ ] Implement strict source parsers and bounded policy/document/data acquisition;
  pinned reviewed policies and academic files, no fabricated dates.
- [ ] Run focused tests. Expected: all pass; changed policies stop before data fetch.
- [ ] Commit parser/acquisition deliverable.

## Task 2: Storage, CLI and measured coverage

**Files:** repository.py, commands.py, report.py; integration and CLI tests.
**Consumes:** Task 1 observations and records; existing 0002 schema.
**Produces:** data research command and undated/missingness/metric-conflict reports.

- [ ] Write integration tests for undated staging, no canonical draw creation,
  idempotence, immutable payload, invalid evidence, annual conflicting values,
  rollback and command imports. Expected: new interfaces fail.
- [ ] Implement transactions and explicit undated coverage, missing draw-date count,
  conflict groups with every value and source reference; no migration needed.
- [ ] Run focused tests and Ruff. Expected: all pass, no lint issues.
- [ ] Commit storage/report deliverable.

## Task 3: Live collection and integration

- [ ] Collect reviewed sources to ignored data/raw/research, run the command twice,
  compare row counts. Expected: 264 undated results and 110 RNL statements; repeat
  collection does not duplicate them. Verify counts against saved source documents.
- [ ] Generate ignored coverage JSON, save database/evidence backups and document
  actual counts, two contradictory metrics and remaining historical gaps.
- [ ] Run database health and full pytest/Ruff. Expected: healthy and all pass.
- [ ] Commit docs; fresh whole-branch review and necessary fixes.
- [ ] Merge local main, repeat runtime/full tests, then push as authorized.
