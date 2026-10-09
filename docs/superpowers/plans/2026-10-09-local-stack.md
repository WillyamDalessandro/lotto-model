# Local Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Execute in this session.

**Goal:** Deliver a working local PostgreSQL database, reproducible Python environment and tested CLI before collecting historical data.

**Architecture:** A Python package owns configuration, draw validation and database access. Docker Compose owns the persistent PostgreSQL service; Alembic owns schema evolution. Tests use an isolated database and never reset the research database.

**Tech Stack:** Python 3.12, uv, PostgreSQL 18, SQLAlchemy 2, psycopg 3, Alembic, Pydantic Settings, Typer, pytest, Ruff and GitHub Actions.

**Spec:** [Approved foundation](../../project-foundation.md). Phase 1 implements its local stack gate; later collection and modelling remain separate phases.

## Global constraints

- PostgreSQL binds to localhost only; use a named volume and a tested image digest.
- Credentials, raw evidence, local databases and generated artefacts stay outside Git.
- Use DATE for draw dates, timezone-aware UTC timestamps for events and NUMERIC for money.
- Unknown values remain null; sorted main numbers do not imply physical draw order.
- No source acquisition or model training in phase 1.
- Playwright will access public results in a later phase. Spending tracking and manual purchase remain the final workflow; no automated ticket purchase.
- Merge into local main after runtime and full-suite checks, repeat both checks after merge, then push.

## Review focus

- Missing or malformed database configuration fails clearly without exposing credentials.
- Failed connections return a nonzero CLI status with a sanitised message.
- Duplicate draws and invalid number sets cannot become accepted canonical records.
- Tests cannot accidentally run destructive operations against the research database.
- Migration and restart preserve existing records rather than recreating the database.

## Task 1: Package, configuration and command interface

**Files:** pyproject.toml, uv.lock, .python-version, .gitignore, .env.example, src/lotto_model/__init__.py, config.py, cli.py, tests/test_config.py, tests/test_cli.py.

**Interfaces:** `Settings` reads `LOTTO_DATABASE_URL` from environment/.env and accepts PostgreSQL psycopg URLs only. `lotto --help` and `lotto db health` are Typer commands. The health check executes SELECT 1 and returns zero only on success.

- [ ] Provision uv and Python 3.12; declare package and separate development/research extras; resolve a lockfile.
- [ ] Write tests for missing/invalid URLs, valid settings, CLI help and sanitised connection failure; run them and observe failures for missing behaviour.
- [ ] Implement configuration and CLI health behaviour with a bounded connection timeout. Never print full exception text containing connection credentials.
- [ ] Run `uv run pytest tests/test_config.py tests/test_cli.py` and `uv run ruff check .`; require success.
- [ ] Commit the package and checks.

## Task 2: Docker database and versioned schema

**Files:** compose.yaml, alembic.ini, migrations/env.py, migrations/script.py.mako, migrations/versions/0001_initial.py, src/lotto_model/db.py, contracts.py, tests/test_contracts.py, tests/integration/test_database.py, tests/conftest.py.

**Interfaces:** `lotto db migrate` upgrades to head without manual SQL. `DrawInput` takes game, draw date, rule, eligible pool, six mains and bonus and rejects duplicates/out-of-pool values. `create_engine_from_settings(settings)` supplies bounded database connections.

Initial tables: sources, ingestion_runs, raw_artifacts, source_observations, games, rule_regimes, draws, draw_numbers and prize_tiers. Later context, quality reporting and snapshot tables are introduced with their ingestion functionality.

Use foreign keys and unique constraints for source identity, (game, draw_date), (draw, number) and (draw, tier). Number rows have an explicit main/bonus role. Application validation enforces exactly six eligible mains and a distinct bonus; database constraints additionally reject nonpositive numbers, invalid roles, negative winner counts/prizes and duplicate numbers. Rule/game linkage is validated before canonical writes; phase 2 must use that validated transaction path.

- [ ] Write draw-contract tests for valid 6/45 and 6/47 lines, five/seven mains, duplicate mains, bonus collision and ineligible numbers; observe failures before implementing the contract.
- [ ] Add Compose with required environment credentials, persistent volume, localhost port, pg_isready health check and pinned image. Add a separate test service/profile with separate database and volume.
- [ ] Implement contracts, metadata and initial Alembic migration. Load database URL from settings without storing credentials in alembic.ini.
- [ ] Write integration tests for empty-database upgrade, second upgrade, uniqueness/check constraints and transaction rollback. Test fixtures refuse a database unless its name ends in `_test`.
- [ ] Run the full suite with the test profile running; confirm no skipped integration tests. Keep test data separate from real draws.
- [ ] Insert a clearly identified synthetic sentinel in the test database, restart the test service and verify persistence; remove the sentinel afterwards.
- [ ] Commit the database deliverable.

## Task 3: Operations, CI and delivery

**Files:** .github/workflows/checks.yml, README.md, docs/local-development.md, docs/project-foundation.md.

**Interfaces:** documented PowerShell commands create local environment configuration, start PostgreSQL, migrate, check health and run all tests. CI runs the same suite against a PostgreSQL service with its own test credentials.

- [ ] Document `uv sync --locked`, Compose startup, health, migration, lint and test commands. Explain separate test credentials and storage.
- [ ] Document pg_dump backup and restore into a separate verification database; demonstrate restore with synthetic test data. Never use volume deletion as routine cleanup.
- [ ] Add CI with Python 3.12, locked dependencies, Ruff and the complete pytest suite against PostgreSQL. Do not introduce production credentials into CI.
- [ ] Run `docker compose config --quiet`, runtime health/migration commands, `uv run ruff check .`, `uv run ruff format --check .`, and the full test suite. Check `git diff --check` and review the final diff.
- [ ] Commit verified changes, merge the feature branch into local main, and repeat runtime and full-suite checks on main.
- [ ] Push main only after post-merge checks succeed. Record test totals, runtime status and any outstanding phase scope in the delivery message.

## Deferred phases

Phase 2 inventories permissible sources, then implements cache/provenance and idempotent ingestion. Phase 3 freezes audited data. Phases 4–5 implement statistical baselines and leakage-safe experiments. Phase 6 adds prospective records, Playwright public-result access and configurable per-draw/weekly spending tracking with manual ticket purchase. Budget values will be supplied before that phase; none are assumed here.
