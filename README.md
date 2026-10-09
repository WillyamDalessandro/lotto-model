# Lotto Model

Research project evaluating whether historical Irish Lotto draws support an out-of-sample advantage over random number selection.

## Objectives

- Predict six distinct main numbers before each draw.
- Primary evaluation: at least 3 main matches, one line per draw.
- Secondary evaluation: at least 5 main matches and portfolios of 5 or 10 lines, compared at identical budgets.
- Main Lotto only; bonus matches and jackpot optimisation are outside the initial scope.

## Implementation plan

Read [the implementation plan](docs/implementation-plan.md) for data contracts, leakage controls, chronological validation, baselines, candidate models, uncertainty and delivery stages.

## Status

Planning complete. No model has been trained or validated yet.

The initial historical experiment uses the 6/47 regime. The small 6/45 sample is not sufficient for reliable evaluation. Historical prize-sharing correlations are not evidence that winning numbers can be predicted. A result showing no advantage over random selection is a valid outcome.

## Data provenance

Read [data collection and preparation](docs/data-collection.md) for the sources, retrieval and recovery workflow, table structure, enrichment, validation and reproducibility limitations.
