# Irish Lotto number model — implementation plan

Status: proposed experiment, not trained.
Repository note (9 October 2026): the referenced datasets and dashboard are absent from this checkout. Treat counts below as a description of an external snapshot until verified. The [project foundation](project-foundation.md) governs infrastructure, ingestion and phased delivery; confirm dataset coverage and update this experiment protocol after ingestion. Prior publication language below is historical context, not current project authorisation.
Scope: main Lotto only. Predict six distinct main numbers before each draw. Primary objective: at least 3 main matches. Secondary objective: at least 5 main matches. Bonus matches and jackpot optimisation are outside the first version.

## 1. Research question and success criteria

Does a model using only historical draws improve the rate of 3-or-more matches over uniform random lines at the same line budget?

A fair independent lottery gives every valid six-number combination the same theoretical chance. This experiment must establish an out-of-sample advantage rather than assume one. Historical prize-sharing correlations do not establish number predictability. A negative result is a valid outcome.

Primary analysis: one line per draw. Separate secondary analyses: portfolios of 5 and 10 distinct lines. Compare each budget only against the same budget. Freeze the primary configuration before inspecting holdout results.

Retain a model as promising only if the untouched holdout shows a positive improvement in the primary match rate with a predeclared 95% interval excluding zero, supporting randomisation evidence, and no leakage or validation failure. Also report chronological stability and predictive calibration. A promising result requires prospective confirmation; it is not proof of a lasting advantage. Do not optimise a model on isolated 5-match successes.

## 2. Sources and data contract

Source files:
- irish_lotto_draws_5_years.csv: draw_date, six sorted mains, bonus and rule_id.
- irish_lotto_game_rules.csv: effective rule intervals and eligible number pool.
- irish_lotto_calendar_5_years.csv: date and scheduled draw metadata.

Current coverage: 527 draws, 9 October 2021–7 October 2026; 512 under 6/47 and 15 under 6/45. Recount and verify the current files when implementation begins. Results were primarily collected from independent historical archives; verify operator sources where available and retain provenance and discrepancies.

Prize files are used for optional retrospective prize-value summaries, not as future-draw targets or predictors containing post-draw information. Do not infer ticket-level return on investment or ticket sales from draw-level payouts.

Canonical grain: one draw per date. Target main numbers form an unordered set. Validate dates, duplicates, scheduled coverage, six distinct eligible mains, bonus distinctness and effective rules before feature creation. Preserve actual chronological draw order, including the introduction of Monday draws.

## 3. Rule regimes and evaluation boundaries

Run the initial historical experiment only within the 512-draw 6/47 regime. Do not mix it silently with 6/45. Define lag and target pairs within the same regime so the final 6/47 observation does not acquire a 6/45 target.

The 15 6/45 draws are insufficient for a reliable trained-model evaluation. Show this regime as insufficient evidence. Collect subsequent draws for prospective testing. Any future transfer model must be explicitly assessed for changed eligibility, schedule and distribution rather than treated as a validated deployment of the 6/47 model.

The initial experiment is a historical study, not a recommendation for current 6/45 tickets. Ineligible numbers 46 and 47 must never appear in a current-regime output.

## 4. Targets and prediction records

For target draw t and eligible number j:
- number_in_draw[t,j] = 1 if j appears among the six mains, otherwise 0.
- matched_mains[t,line] = size of the intersection between the predicted six-number line and the actual six mains.
- hit_3_plus = matched_mains >= 3.
- hit_5_plus = matched_mains >= 5.

Report exact 3 and exact 5 matches as supplementary counts so the inclusive objectives are unambiguous. For portfolios report both per-line results and whether any line reaches each threshold in a draw. Distinguish matching 5 mains from operator prize tiers involving the bonus.

Store draw date, issue time/cutoff, rule, model/version, training endpoint, feature configuration, seed, line budget, line index, six predicted numbers, per-number probabilities and subsequent observed match count. Future predictions must be immutable before results arrive.

## 5. Features and leakage prevention

Build features from draws strictly earlier than the target draw. Never calculate rolling statistics on the complete dataset and then split it.

Initial candidate features:
- Eligible-number inclusion frequencies over the previous 10, 25, 50 and 100 draws.
- Draws since each number last appeared; separately mark never seen in the available history.
- Inclusion in each of the previous 1–3 draws.
- Short-window frequency minus long-window frequency.
- Smoothed historical inclusion frequency.
- Target weekday and elapsed days since the prior draw, known before the target draw.

Evaluate pair frequencies only as a later ablation, with smoothing and a tightly bounded feature set. Five years is too small for unrestricted pair/triple search. Pair features may describe historical co-occurrence but cannot reference unknown members of the target combination.

Recompute previous-draw overlap correctly for each candidate prediction or past draw; do not use target-draw overlap as an input. Target-draw main sum, odd count, low-number count, consecutive pairs, winner counts and prize values are unavailable before that draw and prohibited as features.

Fit scaling, imputation, smoothing choices, feature selection and calibration on training data only. Persist feature timestamps and assert max input date < target draw date. No preprocessing fitted on validation or holdout rows.

## 6. Baselines

Use the same eligible pool, prediction dates, information cutoff and line budget for every comparison:
1. Uniform random valid lines without replacement within a portfolio.
2. Smoothed historical-frequency selection from the same training window.
3. Balanced coverage portfolios, defined without inspecting test outcomes, as a secondary construction baseline.

Generate at least 10,000 seeded random backtest simulations for uncertainty and a stable null comparison. Freeze seeds/configurations before final evaluation. Randomise full portfolios and account for overlap between their lines; do not multiply single-line probabilities as if lines were independent.

Use the exact hypergeometric baseline for a single fixed line: P(K=k)=C(6,k)×C(N−6,6−k)/C(N,6), with N equal to the eligible pool. Sum over k>=3 and k>=5. Check simulated results against this exact expectation. Different valid line shapes have identical marginal odds under the fair independent-draw assumption.

## 7. Candidate models

Start with a pooled, regularised logistic model over draw-number records, using number-specific historical features and carefully regularised number identity effects. Treat the draw as the evaluation group: 47 candidate-number rows from one draw are not 47 independent outcomes.

Compare against a small shallow gradient-boosting model. Restrict search space, depth and minimum leaf sizes. Candidate families and tuning budget must be fixed in advance. Do not introduce neural networks or large feature searches without evidence that the simple models are useful.

Predict a probability for each eligible number. Evaluate marginal calibration, log loss and Brier score in addition to line matches. If calibration is used, fit it within the historical training/validation chronology. The six inclusion labels are dependent; marginal probabilities do not define a complete joint combination distribution.

## 8. Line and portfolio construction

Primary one-line policy: choose the six largest marginal inclusion probabilities with deterministic tie-breaking. This is a transparent baseline policy; it maximises the sum of marginal inclusion probabilities, not necessarily P(at least 3 matches).

Secondary policies may use seeded probability-weighted sampling and overlap-limited diversified portfolios. Freeze sampling temperature, overlap limit and candidate count from validation only. Keep exactly 5 or 10 unique valid lines as specified. Never claim that diversification increases single-line marginal odds.

Do not optimise a 3-match or 5-match probability from independent per-number probabilities without stating and testing the joint-distribution assumption. Compare construction policies empirically at the same budget.

## 9. Chronological training and backtest

Reserve the final 20% of eligible 6/47 draws as a locked holdout before any model selection. Save the exact date/index boundaries. Use earlier draws for development with a minimum 150-draw training history and expanding-window chronological validation folds.

Development procedure:
- Train only on prior draws.
- Tune a bounded set of configurations using chronological validation within the development period.
- Select one primary model and one-line policy using a predeclared objective, with proper scoring rules as tie-breakers when match events are sparse.
- Freeze feature list, hyperparameters, construction policy, seed policy and metrics.

Holdout procedure:
- Predict each holdout draw using only earlier observed draws.
- A predeclared expanding retraining schedule may incorporate earlier holdout results after they occur, as a real sequential deployment would, but must never retune configuration using holdout performance.
- Write each prediction before attaching its target.
- Evaluate once. If results inform a change, label the changed model exploratory and use future draws for its new confirmation.

No shuffled cross-validation, random train/test split or draw-number row split. Report evaluated draw counts rather than the full source count.

## 10. Metrics and uncertainty

Primary: per-line 3-plus rate and its absolute improvement over the uniform-random baseline on the locked holdout, at one line per draw.

Secondary: mean matches; exact-match histogram; 5-plus rate and event count; portfolio any-line 3-plus and 5-plus rates; marginal probability log loss and Brier score; calibration by probability bin; chronological fold stability.

Report numerator, denominator, line budget, regime and evaluated date range for every rate. Show uncertainty using draw-level resampling or a suitable block bootstrap as a sensitivity check. Report model-minus-baseline differences with paired draw-level comparisons. For rare outcomes use exact/binomial intervals where applicable; zero 5-match events is not proof of zero probability.

Use seeded Monte Carlo randomisation under the independent uniform-draw null to assess whether observed fixed-policy performance is unusual. Any repeated model selection needs its full selection procedure accounted for, or a clean holdout used after selection. Adjust secondary multiple comparisons and keep them separate from the primary claim.

## 11. Verification requirements

- Feature cutoff assertions for every prediction.
- Perturb future draw rows in a disposable copy: earlier predictions must remain unchanged.
- Correct effective pool and six distinct numbers in every line.
- Correct unique-line count and deterministic seed behaviour.
- Independent recomputation of intersections and match rates.
- Exact random-baseline formula reconciles with simulation.
- No repeated totals from draw/prize joins.
- Every method uses identical eligible evaluation dates and budgets.
- Holdout outputs contain no configuration selected from holdout performance.
- Dashboard filters and exports preserve population, regime, line budget and evaluated dates.

## 12. Deliverables

- Training/backtest pipeline with reproducible configuration and environment notes.
- Notebook explaining preparation, chronological boundaries, methods and results.
- Model artefacts with training cutoff and regime metadata.
- prediction_log.csv and draw-level evaluation_results.csv.
- baseline_simulation_summary.csv and model_comparison.csv.
- Model card documenting intended historical scope, missing inputs, leakage controls, calibration and uncertainty.
- Dashboard additions comparing model versus baselines, match distributions, chronological results and 3/5 outcomes at identical budgets.

Update the existing dashboard rather than creating another unrelated dashboard. Preserve its identity, data provenance and private access. Publication is authorised in this conversation; follow normal verification and current ownership checks.

## 13. Execution order and decisions

1. Validate source and freeze the chronological split.
2. Implement baseline simulation and exact odds checks.
3. Build leakage-safe features and minimal logistic model.
4. Evaluate development folds, then the bounded boosting candidate.
5. Select and freeze the primary model/policy.
6. Run the locked holdout once and independently reconcile results.
7. Publish the findings, including a no-advantage result if that is what the evidence shows.
8. Design prospective 6/45 testing only after reporting the historical experiment and its limitations.

Proceed first with one six-number line per draw and the 3-plus objective. Keep 5-plus and larger portfolios secondary. Do not promise better odds or profitable play from this plan.
