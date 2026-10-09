# Historical experiments

Status: software implemented and tested end to end on synthetic snapshots in the
isolated test database. No real experiment has run, because no audited historical
snapshot or frozen real protocol exists. See `docs/ai-model-research.md` for
the power analysis: with the provisional 282-draw minimum, the 57-draw holdout
can only detect a one-line 3-plus rate of about 0.095 (about 4.5 times uniform).

## Workflow

```bash
uv run lotto research develop  data/experiments/<protocol> --snapshot data/snapshots/<digest>
uv run lotto research freeze   data/experiments/<protocol>/development
uv run lotto research holdout  data/experiments/<protocol>/frozen/<identity> --snapshot data/snapshots/<digest>
uv run lotto research nulls    data/experiments/<protocol>/frozen/<identity> --snapshot data/snapshots/<digest> --count 10000
uv run lotto research reconcile data/experiments/<protocol>/frozen/<identity> --snapshot data/snapshots/<digest>
uv run lotto research report   data/experiments/<protocol>/frozen/<identity> --snapshot data/snapshots/<digest>
uv run lotto research predict  data/experiments/<protocol>/frozen/<identity> --snapshot data/snapshots/<newer> --target-date YYYY-MM-DD
```

1. **develop** scores the six fixed candidates on the common development folds:
   logistic regression with C in {0.01, 0.1, 1} (StandardScaler fitted on
   training rows only), and histogram gradient boosting with max_leaf_nodes in
   {3, 7, 15}. Features are rebuilt before every target from earlier draws only.
   Results are written once to `development/`.
2. **freeze** records the selected configuration, feature schema,
   protocol/snapshot digests, development hash and `uv.lock` hash in
   `frozen/<identity>/frozen.json`. Its SHA-256 is the experiment identity.
3. **holdout** claims the identity in the `experiments` table and holds a session
   advisory lock, so two processes cannot run it at once. For each holdout
   target it refits on all earlier draws (including earlier holdout draws, as
   frozen), commits the full 1/5/10-line portfolios, and then records
   evaluations separately. Issued predictions and evaluations reject
   UPDATE/DELETE. An interrupted run is resumed by rerunning the command: issued
   lines are reused and never regenerated. A completed identity returns its
   existing results without refitting. A changed configuration is a new identity.
4. **nulls** runs seeded null-history refits with one checkpoint file per
   replicate. A resumed run equals an uninterrupted one. The final report needs
   10,000 replicates. That means 10,000 times the number of holdout targets in
   refits: hours for logistic, much longer for boosting. Plan compute first.
5. **reconcile** recomputes intersections, denominators and rates from the raw
   CSVs and the snapshot, without the runner's metric helpers, and checks the
   artifact hashes.
6. **report** writes `report.md`, `model-card.md` and `findings.json`. The
   primary claim is the one-line 3-plus rate against exact p0, with a 95%
   Clopper-Pearson interval minus p0, the minimum detectable rate, the paired
   draw bootstrap vs uniform (block-5 sensitivity), the null Monte Carlo p and
   Holm-adjusted secondary comparisons.

"Promising" requires a positive improvement, an interval excluding zero, a final
null p ≤ 0.05 and reconciliation. Prospective confirmation is still required.
Anything else reads "no demonstrated advantage" and states the undetectable
range: low power is never presented as evidence of equality.

## Outputs (ignored `data/`)

`prediction_log.csv`, `evaluation_results.csv`, `model_comparison.csv`,
`baseline_simulation_summary.csv`, `probabilities.csv`, `metrics.json`,
`model.json`, `manifest.json`, then `report.md`, `model-card.md` and
`findings.json`. `notebooks/historical-experiment.ipynb` reloads these after
checking the manifest hashes, and plots the match histogram and calibration.

`model.json` is a JSON artifact (logistic parameters, or a reproducible refit
spec for boosting). Pickle/joblib files are never written or loaded.
`predict` refits the frozen configuration on verified history earlier than the
target and returns six distinct eligible mains, probabilities, cutoff and
digests. It is research output, not betting advice.

Records are retrospective simulations. Issue time is execution time and the
cutoff is target-relative, so they are not real pre-draw forecasts.
