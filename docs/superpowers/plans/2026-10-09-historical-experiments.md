# Historical Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the frozen candidate study once and deliver a reproducible, independently reconciled finding.

**Architecture:** Feature/model modules consume frozen snapshots/protocols; a transaction-backed experiment ledger separates issuance from evaluation. Reporting reads final verified outputs and never tunes models.

**Tech Stack:** Existing NumPy, SciPy, scikit-learn, pandas/Jupyter/matplotlib research extras; SQLAlchemy/Alembic, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-historical-experiments.md`.

## Global Constraints

- Python >=3.12,<3.13; existing research extras; six configurations; chronological evaluation only.
- 150-draw feature warmup; 25 supervised training draws; candidate start index 175; minimum population 282.
- Explicit reviewed protocol revision for candidate-compatible dates; never modify frozen baseline protocols.
- No publication, deployment, betting claims or extra tuning.
- Exactly 10,000 null refits/paired bootstrap replicates; uncertainty choices pinned by Phase 4.

## Review Focus

- Initial candidate evaluation must have supervised training data (Task 1).
- Missing scheduled draws must invalidate lag continuity without inventing data (Task 1).
- Nonconvergence and single-class training must fail visibly (Task 2).
- Interrupted holdout execution must reuse frozen predictions rather than reevaluate choices (Task 3).
- Rare/zero events and dependent number rows must not produce misleading uncertainty (Task 4).

### Task 1: candidate-compatible protocol and timestamped features

**Files:** Create research/features.py, tests/research/test_features.py; extend research/contracts.py, protocol.py and test_protocol.py.

**Interfaces:** `feature_rows(history: list[ResearchDraw], target_date: date, pool: int) -> FeatureBatch`; FeatureBatch carries ordered columns, number-indexed values, max_input_date and lag validity. `training_rows(draws: list[ResearchDraw], end_index: int) -> tuple[FeatureBatch, ndarray]` creates rows from indices >=150 and <end_index only.

- [ ] Write `test_training_start`: target 175 has 25 supervised draws/1175 number rows; target 150 is not candidate evaluable; n=282 yields development=225 and two full candidate folds [175,200),[200,225). Earlier baseline-only protocols are rejected without explicit revision.
- [ ] Write `test_feature_cutoffs_and_gaps`: future perturbation preserves prior features; target labels never enter rows; last-1/2/3 validity fails across gaps; never_seen has recency=100 and flag=true; weekday/day delta uses preknown dates.
- [ ] Run `python -m uv run pytest tests/research/test_features.py tests/research/test_protocol.py -q`; expect intended failures. Implement exact spec columns, chronology and explicit protocol revision support.
- [ ] Run tests; commit `feat: build leakage-safe candidate features`.

### Task 2: fixed candidate fits and development selection

**Files:** Create research/models.py, selection.py, tests/research/test_models.py, test_selection.py.

**Interfaces:** `fit_candidate(config: CandidateConfig, features: FeatureBatch, labels: ndarray, seed: int) -> FittedCandidate`; `predict_marginals(model: FittedCandidate, features: FeatureBatch) -> ndarray`; `select_candidate(scores: list[CandidateScore]) -> CandidateConfig`.

- [ ] Write `test_fixed_grid_and_fit_scope`: exactly six configs and spec parameters; scaler statistics use training only; prediction is length 47 in [0,1]; invalid/single-class/nonconverged fits fail with diagnostic. Write tie-break test for 3-plus, Brier, log-loss, ID ordering.
- [ ] Write `test_common_development_population`: all models and baselines use indices >=175 in retained folds with matching dates/budgets; changing holdout outcomes leaves selection unchanged.
- [ ] Run targeted model/selection tests; expect failures; implement fixed grid with no additional search/calibration. Serialize chosen config and hashes before holdout.
- [ ] Run targeted tests; commit `feat: select bounded candidates chronologically`.

### Task 3: immutable issuance and resumable holdout ledger

**Files:** Create research/ledger.py, experiment.py, next unused migration `<revision>_experiments.py`, tests/integration/test_experiments.py.

**Interfaces:** `claim_experiment(connection: Connection, identity: str, frozen: dict) -> int`; `issue_predictions(connection: Connection, experiment_id: int, records: list[PredictionRecord]) -> None`; `record_evaluations(connection: Connection, experiment_id: int, records: list[EvaluatedRecord]) -> None`; `run_holdout(engine: Engine, frozen_path: Path) -> Path`.

- [ ] Write `test_ledger_immutability`: experiments store digests/status/config, predictions have exact unique issuance key, trigger rejects UPDATE/DELETE, evaluation is separate; incomplete portfolio rolls back.
- [ ] Write `test_resume_reuses_predictions`: failure after issuance but before scoring resumes with same lines and no second issue; changed configuration is rejected; two concurrent claims cannot run the same identity; completed run returns existing verified results without fitting again.
- [ ] Run `python -m uv run pytest tests/integration/test_experiments.py -q`; expect failures. Create next-head migration and transaction/status logic; distinguish historical simulated cutoff from actual execution timestamp.
- [ ] Run tests including migrations and future-perturbation holdout runner test; commit `feat: persist frozen holdout issuance and resume`.

### Task 4: inference, independent reconciliation and findings

**Files:** Create research/inference.py, reconcile.py, reporting.py; tests/research/test_inference.py, test_reconcile.py; `notebooks/historical-experiment.ipynb`, docs/historical-experiments.md; extend research/commands.py.

**Interfaces:** `infer_primary(records: list[EvaluatedRecord], pool: int, protocol: Protocol) -> dict`; `run_null_replicates(frozen: dict, count: int, checkpoint_root: Path) -> dict`; `reconcile_outputs(output: Path) -> dict`; `write_findings(output: Path, reconciled: dict) -> Path`.

- [ ] Write `test_sparse_intervals`: zero events yields a nonzero upper bound; improvement interval is exact rate interval minus p0; Monte Carlo p with zero exceedances is 1/10001; Holm adjustment family is complete. Calibration includes probability 1 in last bin.
- [ ] Write `test_null_and_bootstrap_units`: null pipeline refits on simulated earlier history only; bootstrap samples draw groups; resumed seed-indexed replicates equal uninterrupted output and no duplicates. Smaller counts are allowed for unit fixtures only; final reports require 10,000.
- [ ] Write `test_independent_reconciliation`: recompute raw number intersections without runner metric helpers; corrupted count, denominator, budget/date mismatch and artifact hash fail final reporting.
- [ ] Run targeted tests, implement spec inference and report labels. Notebook reloads verified exported results and regenerates report tables/figures; it does not tune or rerun holdout.
- [ ] Add `lotto research develop PROTOCOL`, `freeze DEVELOPMENT_DIR`, `holdout FROZEN_DIR`, `reconcile OUTPUT_DIR`, `report OUTPUT_DIR`. Validate all hashes and sanitize failures; never publish.
- [ ] Run synthetic end-to-end runtime and full Ruff/pytest/whitespace checks; commit, merge local main, repeat checks, push only code/docs after success. Run actual study only after reviewed real-data gates, report counts and limits honestly.
