# Next phases — draft roadmap

Date: 9 October 2026. Status: proposed for review; implementation is not authorised by this document.

## Purpose and starting point

Build a reproducible historical study of Irish main Lotto, then assess whether any result merits prospective confirmation. A well-supported finding of no advantage is a successful research outcome.

The ingestion foundation exists. The latest recorded coverage in `docs/phase2-coverage.md` is zero accepted/staged draws, zero verified rule intervals, zero prize/jackpot records, two all-games annual metrics, and 14,162 calendar dates with unknown schedules. These are documented measurements, not freshly queried database counts. The external 527-draw snapshot is absent and must not determine sample sizes or split dates.

Recommendation: progress through acquisition, audit/freeze, AI model/data/method research, frozen baselines and evaluation protocol, training experiments, and prospective research in that order. Literature and source research can begin alongside acquisition; final dataset and model decisions require the audited population. Reporting follows the audit and experiment artifacts.

## Phase 2 completion — obtain and reconcile research inputs

**Outcome:** evidence-backed historical draws, rule intervals, prizes and jackpot context, with independently measured coverage.

- Recover the original exports and their provenance if available; otherwise obtain an export or source with documented permission for the intended collection.
- Review dated rules and schedules before assigning regimes or expected draw dates. Do not infer effective intervals from number appearances.
- Use the existing offline import/evidence/reconciliation workflow; add adapters only when the supplied format requires them.
- Backfill numbers first, then prizes and jackpot context. Missing enrichment must remain explicit and must not erase valid draw observations.
- Compare overlapping sources and resolve conflicting number sets explicitly. Keep evidence and unresolved observations.
- Re-run coverage by source, year, game, regime and field. Distinguish unknown schedules from missing scheduled draws.

**Gate:** permitted inputs imported idempotently; mandatory prize/rule/jackpot acquisition accounted for; conflicts and missing fields quantified; reconstruction in the isolated test database and evidence/database backup restoration verified. Best-effort public stories and extra annual metrics do not replace mandatory inputs.

**Dependency:** a permitted export or collection source and dated rule evidence. Acquisition can remain incomplete even when the software passes every test.

## Phase 3 — audit and freeze a reproducible dataset

**Outcome:** an immutable research snapshot with an inclusion policy, provenance manifest and audit report.

**Proposed work:**

- Extend `src/lotto_model/ingestion/report.py` with verified schedule coverage and snapshot eligibility reporting; preserve unknown-versus-missing distinctions.
- Add a focused snapshot module and CLI commands under the existing package. Confirm the existing `dataset_snapshots` schema before proposing a migration.
- Export accepted main-Lotto draws in stable date order, their rule metadata and source lineage. Exclude unresolved number conflicts and invalid rule assignments; record every exclusion reason.
- Preserve prize/jackpot completeness separately from number eligibility. Mark disputed enrichment rather than treating it as zero.
- Record hashes, schema/export version, source revision, extraction cutoff, row counts, date ranges and reconstruction instructions.
- Produce a reviewable report covering duplicates, schedule gaps, regime boundaries, provenance gaps and enrichment completeness.

**Acceptance checks:** repeated export of unchanged inputs yields identical content hashes; source corrections create a new snapshot; every included draw traces to evidence; exclusions reconcile with source counts; backup restore reproduces the snapshot. Synthetic tests cover unknown schedules, boundary dates, conflicting observations, missing enrichment and multiple games sharing a date.

**Gate:** audited snapshot rebuildable from preserved inputs; population and exclusions reviewed; any remaining gaps explicitly accepted for the historical study. No training before this gate.

## Phase 4A — research the AI model, training dataset and methodology

**Outcome:** an evidence-backed recommendation for the best-supported model, training dataset, training method and evaluation design for predicting six distinct main Lotto numbers. “Best” means strongest reproducible development performance under the agreed evaluation and resource budget; it must not be assumed from model complexity or a published accuracy claim.

**Required research:**

- Search current primary research papers, official model/library documentation and original dataset documentation. Keep a dated evidence register with direct links, methods, dataset sizes/regimes, validation design, reported results, reproducibility and limitations. Distinguish actual out-of-sample evidence from in-sample fit and unsupported prediction claims.
- Compare uniform/frequency baselines with regularised statistical models, tree ensembles and plausible neural/sequence models. Assess sample-size needs, target representation, calibration, compute cost and overfitting risk. Include neural models in the research comparison; implement them only if the evidence and available data justify their inclusion. No architecture is declared the winner before evaluation.
- Research candidate training datasets by source, permission, dated coverage, game, rule regime, missingness, provenance and update availability. Recommend the longest suitable verified history rather than assuming five years or the absent external snapshot. Undated records cannot train chronological forecasts; other lotteries/regimes require a separately justified transfer experiment and cannot silently enlarge the primary sample.
- Define six unordered main numbers as the target, distinguishing per-number marginal probabilities from a joint distribution over combinations. Compare target encodings and line-construction methods appropriate to the 3-plus objective; explain assumptions rather than equating marginal ranking with optimal match probability.
- Compare expanding versus rolling training windows, feature families, regularisation, retraining cadence and bounded hyperparameter selection using development data only. Fit all preprocessing and optional calibration within historical training folds. Allow external features only when their pre-draw availability is documented.
- Research statistical power and achievable precision for 3-plus and rare 5-plus outcomes using the actual eligible sample. Set minimum history, supervised warmup, validation folds, holdout size and prospective sample requirements before tuning. A minimum that permits software execution is not evidence that the study has enough power to detect a useful improvement.
- Specify chronological evaluation, equal-date/equal-budget baseline comparisons, leakage checks, uncertainty, null simulations and correction for multiple comparisons. Document what would establish promising performance and what would yield insufficient evidence or no demonstrated advantage.

**Deliverables:** `docs/ai-model-research.md` with citations and evidence register; a model comparison matrix; a training-dataset suitability matrix; a recommended training/evaluation protocol; a reproducible development benchmark plan; and a decision record explaining selected and rejected approaches, expected cost and remaining uncertainty.

**Gate:** research reviewed; actual training population verified; candidate shortlist, tuning/compute budget, feature/target definition, selection criteria and evaluation method agreed before protocol freeze. Revise the Phase 4/5 design specs and implementation plans to reflect those decisions before training. Existing logistic/boosting grids and sample thresholds are provisional starting proposals, not a research-established best model.

## Phase 4B — freeze the experiment and implement baselines

**Outcome:** a reproducible evaluation harness with verified null behaviour, before candidate tuning.

- Revise `docs/implementation-plan.md` against the frozen dataset. Remove assumed counts and record exact eligible regime, date/index boundaries and evaluated sample sizes.
- Select the initial historical regime from verified evidence. Preserve the proposed 6/47 study only if actual coverage supports it; assess small current-regime samples separately.
- Predeclare one line per draw and 3-plus main matches as primary. Keep 5-plus and portfolios of 5/10 unique lines secondary, compared at identical budgets.
- Lock the final 20% of eligible draws as holdout, using an explicit rounding rule and minimum-history check. Preserve the proposed 150-draw training minimum unless a revised protocol justifies a change before tuning.
- Implement exact hypergeometric odds, seeded uniform lines/portfolios and a smoothed historical-frequency baseline. Define deterministic ties, seeds and configuration records.
- Build chronological folds and prediction records that enforce earlier-draw cutoffs. Keep the holdout unevaluated during development.
- Specify the interval method, randomisation procedure, tuning budget, selection objective and handling of secondary comparisons before running experiments. Use at least 10,000 seeded null simulations as already proposed.

**Acceptance checks:** exact probabilities normalise; simulation agrees within a predeclared numerical tolerance; lines are distinct and eligible; portfolios have the exact unique-line count; seeds reproduce outputs; all policies share dates/budgets; changing future draws cannot alter earlier baseline predictions; regime boundaries never create cross-regime lag pairs.

**Gate:** written protocol reviewed and frozen; baseline and chronology checks pass; holdout access/evaluation is controlled and logged.

## Phase 5 — leakage-safe experiments and findings

**Outcome:** an inspectable historical result, including a negative result if supported.

- Implement historical frequency/recency/lag features with timestamps and training-only preprocessing.
- Train and compare the candidate shortlist justified by Phase 4A, within its frozen tuning and compute budget. Logistic and shallow boosting remain initial reference candidates; additional AI architectures require the research decision and revised protocol before implementation.
- Evaluate expanding development folds at draw level, including Brier score, log loss, calibration and match metrics.
- Select and freeze the primary model and line policy using development results. Persist configuration, dependencies, snapshot hash and training cutoff.
- Run the locked holdout once under the frozen sequential retraining policy; write each prediction before attaching its outcome.
- Independently reconcile intersections, denominators, rates and uncertainty. Report chronological stability and secondary comparisons separately.
- Deliver the selected AI model artifact and inference interface, prediction/evaluation exports, a reproducible notebook, comparison tables and a model card. The inference interface accepts only verified pre-draw history and effective rules, returns six distinct eligible mains plus probability/cutoff/model metadata, and preserves immutable issued predictions. Create reporting only from verified outputs; no existing dashboard is assumed.

**Acceptance checks:** future-row perturbation invariance; no preprocessing trained on validation/holdout; immutable issued predictions; metric recomputation independent of the model pipeline; identical comparison populations; reproducible artifacts from the frozen snapshot.

**Gate:** reconciled report with explicit limitations. A promising model requires a positive primary holdout improvement with the predeclared 95% interval excluding zero, supporting randomisation evidence and no leakage failures; prospective confirmation is still required. A failed candidate does not justify retuning against the same holdout.

## Phase 6 — prospective research, then optional manual play support

**Outcome:** timestamped, current-regime research predictions and evaluation on subsequently observed draws.

- Define a current-regime protocol from verified rules and available sample size. Do not represent historical results as validated current-regime performance.
- Issue immutable eligible lines before results arrive; preserve failures and missed issue windows.
- Refresh results through permitted access, retaining source evidence. Browser automation follows the same access policy as HTTP imports.
- Track prospective metrics and predetermined review windows without repeatedly selecting models from interim results.
- Scope optional spending tracking and manual-purchase preparation separately after per-draw/weekly limits, retail rules and desired interface are specified. Purchases remain manual.

**Gate:** cutoff immutability, current number eligibility, replayable result ingestion and prospective reporting verified. Optional play preparation also requires configured spending-limit enforcement and verified purchase rules.

## Delivery workflow for each implementation phase

1. Create a named feature branch before implementation.
2. Write and review that phase's spec and implementation plan; this roadmap does not replace them.
3. Implement only the approved scope, with meaningful unit and database integration checks.
4. Run application/runtime checks and the full relevant suite: `python -m uv run ruff check .`, `python -m uv run ruff format --check .`, `python -m uv run pytest -q`, and `git diff --check`. Start the isolated test database as documented in `docs/local-development.md`.
5. Merge with local `main`, then repeat runtime checks and tests on the merged state.
6. Once a phase is complete and verified (all checks pass on the feature branch and again on merged local `main`), push `main` and the phase branch to `origin` straight away, without waiting for a further request. Never push failing or unverified work. Never push data, evidence, snapshots, experiment outputs or `.env`; they stay outside Git under the existing repository policy.
7. Record the phase's decisions in `docs/implementation-decisions.md` and update the README status in the same push.

## Phase design and implementation documents

All documents below are drafts for review; planning does not establish real-data completion or authorise publication. Phase 4A research is now a prerequisite for finalising the Phase 4/5 documents. Their current 150-draw feature warmup, 25 supervised training draws and proposed minimum of 282 eligible draws are provisional design choices, not researched power requirements. Update them and the model shortlist from the research decision before freezing the protocol.

| Phase | Design spec | Implementation plan |
|---|---|---|
| 2 completion | [Acquisition](superpowers/specs/2026-10-09-acquisition-completion.md) | [Acquisition tasks](superpowers/plans/2026-10-09-acquisition-completion.md) |
| 3 | [Audit and snapshots](superpowers/specs/2026-10-09-data-audit-snapshot.md) | [Audit tasks](superpowers/plans/2026-10-09-data-audit-snapshot.md) |
| 4A | Required AI model/data/method research; deliver `docs/ai-model-research.md` | Evidence review and development benchmark design before training |
| 4B | [Protocol and baselines](superpowers/specs/2026-10-09-baselines-protocol.md) | [Baseline tasks](superpowers/plans/2026-10-09-baselines-protocol.md) |
| 5 | [Historical experiments](superpowers/specs/2026-10-09-historical-experiments.md) | [Experiment tasks](superpowers/plans/2026-10-09-historical-experiments.md) |
| 6 | [Prospective research](superpowers/specs/2026-10-09-prospective-research.md) | [Prospective tasks](superpowers/plans/2026-10-09-prospective-research.md) |

The opening coverage figures describe the earlier planning snapshot. Consult `docs/phase2-coverage.md` and a fresh database report for subsequent acquisitions; undated research combinations do not replace dated canonical history.

## Immediate next planning decision

Recommend preparing the Phase 3 audit/snapshot spec next while Phase 2 acquisition remains the execution dependency. Its contracts and synthetic validation can be designed now, but actual dataset freezing and modelling remain gated on accepted source data.

Decide whether the immediate priority is recovering/obtaining permitted historical inputs or designing the audit/snapshot subsystem. Exact model split sizes, a reporting interface and spending limits are deliberately not set without the required data or user requirements.

## Phase 7 — full backfill, model search and five-year evaluation

Requested 9 October 2026, to start after Phases 2–6 software is complete (see `docs/implementation-decisions.md`). This phase turns the verified tooling into an actual study.

**Outcome:** a complete, verified historical dataset; a documented comparison of several machine-learning models and prediction methods; and a report explaining how each performed on the draws of the last five years, targeting three or more main-number matches (not jackpots).

### 7.1 Verify, backfill and enrich the data

- Verify all existing data, then backfill the full main-Lotto history (dates, six mains, bonus, prizes, jackpot/outcome, rule regimes and schedules). Use only permitted sources: exports or permissions obtained from publishers, operator data provided for this use, or data the user supplies. Sites whose terms prohibit harvesting stay excluded (see `docs/phase2-coverage.md`).
- Add correlated context only where it is known before the draw and could plausibly inform the study. Examples: rule/pool changes, draw schedule and calendar events, prior jackpot size and rollover streak, ticket-sales or official aggregate metrics, and machine/ball-set identifiers if the operator publishes them. Record each source's provenance, timing and permission.
- Import through `lotto data batch`, then audit and freeze with `lotto audit snapshot`. Report coverage by year, regime and field, and list remaining gaps explicitly.

### 7.2 Prepare the training dataset

- Build the training table from the verified snapshot only: per-draw, per-number features computed from earlier draws, with regime boundaries and missing-draw gaps respected.
- Define the evaluation window as the last five years of eligible draws. Earlier history is used for training and development. Keep one regime per model, or add an explicit transfer step for regime changes (6/47 → 6/45).

### 7.3 Automated model and parameter search (leakage-safe)

- Tune parameters automatically, but only with chronological (walk-forward) validation inside the training/development period. Use a predeclared search budget (for example Bayesian or grid search with a fixed number of trials) and pick the best setting by log loss and 3-plus match rate on validation folds.
- The five-year evaluation draws are never used to choose parameters. Tuning "until predictions look good" on the same draws being reported would only memorise noise and give a falsely optimistic result. Each evaluated draw is predicted by a model trained only on earlier draws, with refits on a fixed schedule.
- Candidate model families: uniform random and frequency baselines; regularised logistic regression; gradient boosting (histogram GBM, and XGBoost/LightGBM if added to the lock file); random forest; simple neural networks (MLP). Sequence models (LSTM/transformer) run only as a clearly labelled experiment, because the Phase 4A research found no supporting evidence and a high overfitting risk at this sample size.

### 7.4 Prediction methods compared

- Top-six marginal probabilities (current primary policy).
- Probability-weighted sampling.
- Coverage-optimised portfolios of 5 and 10 lines (maximising distinct-number coverage).
- Frequency/recency heuristics ("hot", "cold" and "overdue" numbers) as explicit comparators.
- Each method's predictions, seeds, configuration and evaluation outcomes are saved immutably in the experiment ledger and exported (`prediction_log.csv`, `evaluation_results.csv`).

### 7.5 Reporting

- Update the report with, per model and method: the 3-plus hit rate over the five-year window against the exact random rate (about 1 in 47.6 under 6/47 and 1 in 42.0 under 6/45), confidence intervals, null-simulation p-values corrected for the number of models and methods tried, calibration, and stability by year.
- Name the best-performing model and method. State plainly whether its advantage over random selection is statistically distinguishable, given the power limits in `docs/ai-model-research.md`. If no model beats random, report that as the finding.

**Gate:** every result traces to a verified snapshot and frozen configuration. Tuning never touches the evaluation draws. Comparisons use identical draws and line budgets. Multiple-comparison correction covers every model and method tested.

**Dependency:** permitted full-history data (7.1). Without it, 7.2–7.5 can only run on synthetic data to verify the software.
