# Project foundation and phased delivery

Date: 9 October 2026. Status: foundation approved; detailed phase 1 plan prepared for review. Infrastructure and ingestion are not implemented.

## Repository audit

The repository has README.md, docs/data-collection.md and docs/implementation-plan.md. There is no application, dependency manifest, Docker configuration, database migration, collector, dataset, model, dashboard or test suite. The working tree was clean before this planning change.

The collection document describes an external snapshot of 527 draws and supporting exports. These are historical claims, not verified repository assets. Recover original CSVs, scripts, cached responses and recovery JSON if available; otherwise rebuild from accessible sources and report the resulting coverage independently. Never fabricate the missing snapshot.

The previous model plan remains the statistical design reference. Its dashboard and publication instructions describe prior external work and do not establish that a dashboard exists here or authorise publication in this project. Its fixed five-year counts and splits must be revisited when the actual dataset is frozen.

## Purpose and boundaries

Build a reproducible local research system for Irish main Lotto: gather the longest verifiable public history, preserve evidence, ingest validated observations into PostgreSQL in Docker, and then evaluate whether historical information supports an advantage over random selection. Success includes a reproducible finding of no advantage. This project does not purchase tickets or automate betting.

Collect as much relevant data as is verifiably available, rather than limiting collection to five years. Track coverage separately for winning numbers, prizes, jackpots and supplementary metadata. Missing enrichment must not discard an otherwise valid draw. Main Lotto is the first canonical dataset; Plus games may be archived when returned by the same source but must have separate game identities and are outside the initial model.

## Stack proposal

| Component | Choice | Purpose |
|---|---|---|
| Runtime | Python 3.12, managed with uv | Reproducible ingestion and research environment |
| Database | PostgreSQL 18 in Docker Compose | Constraints, transactions, audit queries and durable local storage |
| Database access | SQLAlchemy 2, psycopg 3, Alembic | Typed access and versioned schema migrations |
| Collection | httpx and Beautiful Soup | Bounded HTTP fetching and source-specific HTML parsers |
| Contracts and CLI | Pydantic and Typer | Explicit validation and repeatable operator commands |
| Analysis | pandas, NumPy, SciPy, scikit-learn | Baselines, chronological evaluation and modest candidate models |
| Exploration | Jupyter, matplotlib | Reviewable notebooks and diagnostic figures |
| Quality | pytest, Ruff, GitHub Actions | Parser, database, leakage and reproducibility checks |

Resolve and lock compatible dependency versions during implementation; pin the database image to a tested patch version/digest. Keep runtime dependencies separate from research and development extras. No web server, distributed queue, orchestration platform or model registry service is needed initially.

Alternatives considered: SQLite is simpler but does not fulfil the Docker database objective as well; a full Airflow/MLflow platform adds operational work before there is a reliable dataset. A Python CLI with PostgreSQL is the recommended starting point.

Local checks: Docker CLI 29.7.2 and Compose v5.4.0 are installed; Python reports 3.11.2; uv is not on PATH. These checks do not establish that the Docker daemon is running. Provision the proposed project runtime independently of system Python.

References: [Docker Compose](https://docs.docker.com/compose/), [PostgreSQL documentation](https://www.postgresql.org/docs/current/), [uv documentation](https://docs.astral.sh/uv/).

## Data flow and contracts

Source discovery → immutable raw response files and retrieval manifest → parsed source observations → validation/quarantine → canonical database records → frozen dataset export → leakage-safe features → chronological backtest → report.

Store raw bodies outside Git under data/raw with SHA-256 hashes. The database holds source URL, UTC retrieval time, response status, content type, body hash/path, parser version and ingestion-run identifier. Preserve blocked and invalid fetch status; never accept CAPTCHA/error HTML as draw evidence. Files and database backups together must support reconstruction.

Proposed tables:

- sources and ingestion_runs: source authority, access policy, run configuration, progress and errors.
- raw_artifacts and source_observations: immutable evidence and parsed claims; retain disagreements between publishers.
- games and rule_regimes: effective date intervals, eligible pool, main/bonus count, schedule and supporting rule sources.
- draws and draw_numbers: unique (game, draw_date), six distinct main numbers and separate bonus, rule and accepted observation references. Preserve physical draw order only if actually published; sorted ranks are not draw order.
- prize_tiers: unique (draw, tier), nullable winner count, decimal EUR prize and original published text/type.
- draw_context: nullable jackpot pool, rollover outcome and independently sourced metadata.
- quality_issues and dataset_snapshots: rejected/conflicting records, coverage reports, export hashes and snapshot lineage.
- experiments and predictions, added in the modelling phase: configuration, seed, regime, cutoff and immutable issued lines.

Use DATE for draw dates, timezone-aware UTC timestamps for events and NUMERIC for money. Validate number eligibility, distinctness and rule compatibility in application contracts and enforce database invariants where practical. Dates alone are insufficient keys across multiple games. Unknown values remain null. Derivations retain their input lineage.

Repeated ingestion must leave canonical counts unchanged. A source correction creates a new observation; it must not silently overwrite evidence. Contradictory number sets are quarantined pending explicit reconciliation. Prefer operator evidence when it covers the disputed record, record the resolution, and preserve both claims. Missing prizes do not block valid numbers; unresolved numbers do block that draw from modelling.

## Phases and completion gates

| Phase | Deliverables | Completion gate |
|---|---|---|
| 0 — Design and inventory | This foundation, source inventory and reviewed implementation scope | Design approved; actual repository and external artefacts distinguished |
| 1 — Local stack | Python package, lockfile, Compose DB, migrations, CLI, environment example, CI | Healthy DB; migrate empty DB; CLI query; full tests pass |
| 2 — Collection and ingestion | Source adapters, cache/manifest, incremental checkpointing, import path, validators | Idempotent import; invalid-response and conflict handling tested; coverage quantified |
| 3 — Data audit and freeze | Regime verification, reconciliation, completeness report, snapshot and backups | Dataset rebuildable; every accepted draw has evidence; gaps explicitly listed |
| 4 — Model design and baselines | Updated experiment spec, exact odds, random/frequency policies, frozen chronological split | Leakage and baseline checks pass; evaluation protocol frozen before tuning |
| 5 — Experiments | Logistic and bounded boosting candidates, locked holdout, uncertainty and model card | Independent metric reconciliation; no unsupported advantage claim |
| 6 — Prospective research and manual play support | Pre-result prediction records, Playwright public-result access, incremental refresh, configurable per-draw/weekly spending tracker and manual-purchase preparation | Eligible current-regime lines; immutable cutoffs; spending limits enforced in preparation; purchase remains manual |

Each phase gets its own implementation scope and checks. Never begin training to compensate for an incomplete data audit. Playwright result access will preserve retrieved evidence and follow the same source access policy as HTTP collection. Budget values must be defined before implementing spending tracking; automated ticket purchasing is outside scope.

The detailed [phase 1 implementation plan](superpowers/plans/2026-10-09-local-stack.md) defines the package, database, checks and delivery sequence.

## Source discovery and acquisition

Start with the [operator result history](https://www.lottery.ie/draw-games/results/view?game=lotto&lang=en) and the independent archive patterns already documented in data-collection.md. Discover earliest and latest accessible draws per source through a small access probe before planning a bulk backfill. No official bulk endpoint is established by this audit.

Collect numbers, bonus, draw date and game first; then prize tiers, winners, published amounts, jackpot pools/outcomes and effective rules/schedules. Optional public ticket-location context is descriptive and low priority. Do not collect private player identities. Ticket sales, player selections and redemption mixes remain unavailable unless an explicit published source is found.

Respect source access rules; use conservative configurable pacing, bounded retries for transient failures, checkpoints and conditional requests where supported. Stop retrying access-denied/CAPTCHA responses and use another permissible source or a provenance-bearing manual import. Do not repeatedly fetch complete history. Maintain per-source and per-field coverage plus an expected-versus-observed calendar derived from verified rules, allowing documented exceptions.

The [operator announcement](https://www.lottery.ie/news/press-releases/change-is-coming), checked on 9 October 2026, specifies 6/45 from 5 September 2026 and the first Monday draw on 7 September. Older regimes and effective dates require their own evidence. Do not merge different pools into one model population.

## Model design constraints

Retain the existing primary objective: one research line per draw, at least three main matches; five matches and larger portfolios are secondary. A research line is an evaluation unit, not a complete retail purchase: the operator announcement states a two-line minimum purchase. Any later spend/return study must respect actual ticket rules.

Use exact hypergeometric odds and seeded uniform portfolios before learned models. Fit transformations on training data only and use strictly prior-draw inputs. Prize outcomes, winner counts and target-draw descriptive features are excluded from predictors. Reassess chronological split sizes and statistical power against the recovered history; do not reuse documented counts as facts. Historical 6/47 performance cannot validate current 6/45 predictions. No model is presumed to improve a fair independent draw.

## Phase 1 implementation outline

1. Review this design and confirm phase 1 scope before application scaffolding.
2. Create a feature branch; write the detailed phase 1 spec and implementation plan before code.
3. Add pyproject.toml, uv.lock, src/lotto_model, tests, .gitignore and .env.example. Ignore credentials, caches, local data and model outputs.
4. Add Compose PostgreSQL with a named volume, health check and localhost-only port binding. Keep credentials in local environment configuration.
5. Add initial provenance/rules/draw/prize migrations, configuration validation and CLI database health/migration commands. Document backup and restore; never destroy volumes as a routine reset.
6. Verify Compose configuration, start the DB, apply migrations and exercise the CLI. Run the full relevant suite against a separate test database, including persistence/restart, constraints and migration checks.
7. Merge into local main only after success; repeat runtime and full tests on main, then push as required by the project workflow. Report blockers precisely if Docker or network access prevents checks.

Phases 2–6 need detailed plans at their gates. This outline is not a claim that code, a database or ingestion already exists.
