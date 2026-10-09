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

Phase 1 implements the local Python/PostgreSQL stack. Phase 2 adds evidence storage, offline draw imports, reconciliation, complementary imports, official report metrics and coverage reporting. See [ingestion operations](docs/ingestion.md) and [actual coverage and remaining gates](docs/phase2-coverage.md). Historical acquisition is incomplete because reviewed draw sources restrict harvesting; permitted exports are needed. Model training remains deferred. See [local development](docs/local-development.md) for setup, tests and backups.

The initial historical experiment uses the 6/47 regime. The small 6/45 sample is not sufficient for reliable evaluation. Historical prize-sharing correlations are not evidence that winning numbers can be predicted. A result showing no advantage over random selection is a valid outcome.

## Data provenance

Read [data collection and preparation](docs/data-collection.md) for the sources, retrieval and recovery workflow, table structure, enrichment, validation and reproducibility limitations.

The proposed [complementary data catalogue](docs/complementary-data.md) specifies jackpot and rollover context, prizes, rules/prices, calendar, public ticket metadata, official aggregates and dataset-level coverage for phase 2.
