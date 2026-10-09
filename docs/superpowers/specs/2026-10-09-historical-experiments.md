# Phase 5: historical experiments and reconciled findings

Date: 9 October 2026. Status: draft for review.

## Purpose and entry gate

Determine whether the frozen historical protocol supports an out-of-sample advantage. Require a verified Phase 3 snapshot and reviewed Phase 4 protocol; reject changed digests or incompatible protocol versions. A no-advantage result is valid. No deployment, publication or betting claims.

## Features and fixed candidates

For each target/eligible number, use only earlier same-regime observations. Features: observed inclusion fractions over last 10/25/50/100 draws (short windows use available history); draws-since-last-appearance capped at 100 with separate never_seen flag; last-1/2/3 inclusion flags with validity flags when the lag crosses a missing scheduled draw; 10-minus-100 frequency; smoothed full-history frequency (count+6/47)/(history_count+1); target weekday as seven one-hot columns; elapsed calendar days from prior observed draw. No target sum/parity/overlap, prizes, winners, jackpot, number identity or pair features. Never_seen recency value is 100. Fixed feature order and timestamps are persisted.

Pooled logistic candidate: StandardScaler fitted on training rows only; LogisticRegression(C in [0.01,0.1,1.0], penalty='l2', solver='lbfgs', max_iter=2000), no class weights. Nonconvergence fails the run rather than silently accepting it. Boosting: HistGradientBoostingClassifier(max_leaf_nodes in [3,7,15], max_iter=100, learning_rate=0.05, min_samples_leaf=47, l2_regularization=1.0, early_stopping=False); fixed random_state derived from protocol. Six configurations total. No calibration step or additional hyperparameter search.

Use expanding fits at every development/holdout target. Historical training rows start at the 150-draw warmup index; each row's features exclude its own target. Models begin evaluation only after 25 supervised training draws exist (target index 175). Restrict every baseline/candidate comparison to the Phase 4 common dates: folds [175,200) onward, at least two full validation blocks and minimum 282 draws (development length >=225). Never alter a frozen protocol automatically; reject any older protocol that lacks these training boundaries until an explicitly reviewed revision is frozen.

Choose one primary configuration using Phase 4's pooled 3-plus/Brier/log-loss/stable-ID ordering. Primary line is top six probabilities with number-ascending ties. Report marginal probabilities; they are not a joint combination distribution. Keep weighted portfolios secondary, using Phase 4 policies with predicted probabilities substituted for frequencies, no overlap search or temperature tuning.

## Freeze and holdout

Persist selected configuration, feature schema, protocol/snapshot hashes, dependency lock hash and development outputs before holdout. Claim an experiment in a database registry atomically; states are selected, evaluating, evaluated, failed. Issued predictions are append-only; evaluations are separate rows. A trigger rejects UPDATE/DELETE of issued records. Unique keys prevent reissuing the same experiment/date/budget/line index. Transactions attach full portfolios atomically.

An evaluating/evaluated/failed holdout cannot be restarted as a new confirmatory run under the same experiment identity. Resume interrupted execution only for already-frozen identity, reuse issued lines and continue missing targets; never regenerate them. Record attempts/errors. Corrected source data requires a new snapshot and exploratory label if previous results influenced choices. Holdout is evaluated once for model selection purposes, not once per process invocation.

Write predictions before evaluating each target; then sequentially incorporate earlier observed holdout draws at the predeclared retraining cadence without retuning. Historical issue time is execution time and simulated cutoff is target-relative; do not describe a retrospective record as a real pre-draw forecast.

## Inference and artifacts

Implement Phase 4 exact-null improvement interval, paired bootstrap/sensitivity, 10,000 sequential null-history refits and Holm-adjusted secondary tests. Batch null replicates with seed-keyed checkpoints so interruptions do not change counts; require all 10,000 before a final inference report. Report candidate inclusion probabilities with Brier/log loss/calibration bins (10 equal-width [0,1] bins, final bin includes 1), but resample/evaluate at draw level.

Promising requires positive primary improvement, 95% primary interval excluding zero, one-sided null p<=0.05, no validation failure and prospective confirmation still pending. Otherwise say no demonstrated advantage; do not equate low power with evidence of equality.

Output immutable prediction_log.csv, evaluation_results.csv, baseline_simulation_summary.csv, model_comparison.csv, metrics.json, model artifact, reproducible notebook and model-card.md under ignored data/experiments/. Use a local Markdown report with figures, counts, date ranges, protocol and uncertainty. No existing dashboard assumed. Never load untrusted pickle/joblib artifacts; only internally created verified artifacts with hashes and environment compatibility may be loaded.

## Completion

Python >=3.12,<3.13; existing research extras; six configurations; chronological evaluation only. Test training-only preprocessing, future perturbation, discontinuities, immutable predictions, resume, independent intersections/denominators, seeded inference and artifact hashes. Full runtime/tests before and after local-main merge; push code/docs only. Real research completion requires fully reconciled holdout report, not merely passing synthetic tests.
