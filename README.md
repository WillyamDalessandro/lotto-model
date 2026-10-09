# Lotto Model

Research project evaluating whether historical Irish Lotto draws support an out-of-sample advantage over random number selection.

## Objectives

- Predict six distinct main numbers before each draw.
- Primary evaluation: at least 3 main matches, one line per draw.
- Secondary evaluation: at least 5 main matches and portfolios of 5 or 10 lines, compared at identical budgets.
- Main Lotto only; bonus matches and jackpot optimisation are outside the initial scope.

## Project phases and stack

Read [the project foundation](docs/project-foundation.md) for the repository audit, proposed Python/PostgreSQL/Docker stack, data contracts and phased roadmap. Start with infrastructure and verifiable ingestion before modelling.

## Implementation plan

Read [the implementation plan](docs/implementation-plan.md) for data contracts, leakage controls, chronological validation, baselines, candidate models, uncertainty and delivery stages.

## Status

Phase 1 implements the local Python/PostgreSQL stack. Phase 2 adds evidence storage, offline draw imports, reconciliation, complementary imports, official report metrics and coverage reporting. See [ingestion operations](docs/ingestion.md) and [actual coverage and remaining gates](docs/phase2-coverage.md). `lotto data collect` backfills the full draw history (3,909 draws, 1988–2026) from a permitted source, with reviewed rule evidence. Prize breakdowns are still outstanding. See [local development](docs/local-development.md) for setup, tests and backups.

Phase 7 runs on that real data: `lotto research study` tunes on earlier draws only, evaluates the last five years of each rule regime, and compares four ML model families, frequency, heuristics and random selection across several line-selection methods. See [Phase 7 study](docs/phase7-study.md).

The software for Phases 3–6 is implemented and verified with synthetic data:

- Reviewed offline acquisition batches: [acquisition completion](docs/acquisition-completion.md).
- Audited, content-addressed snapshots: [data audit](docs/data-audit.md).
- Model, dataset and statistical-power research: [AI model research](docs/ai-model-research.md).
- Frozen protocols and baselines: [baselines](docs/baselines.md).
- Leakage-safe experiments with an immutable ledger: [historical experiments](docs/historical-experiments.md).
- Pre-result prospective records: [prospective research](docs/prospective-research.md).

A real audited snapshot now exists (see coverage). The Phase 5 once-only holdout protocol and Phase 6 prospective issuance have not been run on it yet. Decisions taken during implementation are recorded in [implementation decisions](docs/implementation-decisions.md).

The initial historical experiment uses the 6/47 regime. The small 6/45 sample is not sufficient for reliable evaluation. Historical prize-sharing correlations are not evidence that winning numbers can be predicted. A result showing no advantage over random selection is a valid outcome.

## Data provenance

Read [data collection and preparation](docs/data-collection.md) for the sources, retrieval and recovery workflow, table structure, enrichment, validation and reproducibility limitations.

The proposed [complementary data catalogue](docs/complementary-data.md) specifies jackpot and rollover context, prizes, rules/prices, calendar, public ticket metadata, official aggregates and dataset-level coverage for phase 2.
