# Baselines and Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the chronological experiment and verify baseline behaviour without inspecting holdout results.

**Architecture:** A new research package reads verified snapshots, persists content-addressed protocols and evaluates development-only policies. Shared prediction/metric contracts carry forward into Phase 5.

**Tech Stack:** Python, existing NumPy/SciPy research extras, Pydantic, Typer and pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-baselines-protocol.md`.

## Global Constraints

- Python >=3.12,<3.13; existing research extras; no new dependencies.
- pool=47, minimum 282 draws, feature warmup 150, supervised warmup 25, common validation start 175, holdout ceil(0.20*n).
- 25-target development blocks; trailing partial requires >=10; at least two full blocks.
- Budgets 1/5/10; primary one-line 3-plus; root_seed=20261009; 10,000 simulations.
- No holdout evaluation; outputs private under data/experiments/.

## Review Focus

- Insufficient data and rule transitions must not create invalid folds (Task 1).
- Changes to holdout outcomes must not alter development predictions (Task 3).
- Duplicate lines and unstable seeds must never enter comparison outputs (Task 2).
- Impossible exact-odds terms and sparse 5-plus events require correct handling (Task 2).
- Comparison denominators must agree across methods and budgets (Task 3).

### Task 1: verified population and immutable protocol

**Files:** Create `src/lotto_model/research/{__init__,contracts,protocol}.py`, `tests/research/test_protocol.py`.

**Interfaces:** `load_population(snapshot: Path, rule_code: str) -> list[ResearchDraw]`; `build_protocol(draws: list[ResearchDraw], snapshot_digest: str) -> Protocol`; `freeze_protocol(protocol: Protocol, output_root: Path) -> Path`. ResearchDraw contains date, rule_code, pool, mains and gap flag; Protocol pins every choice in the spec and its digest. PredictionRecord contains all spec fields; EvaluatedRecord adds matched_mains/hit flags separately.

- [ ] Write `test_split_boundaries`: n=282 yields development [0,225), holdout [225,282), validation [175,200), [200,225); n=281 fails; n=283 yields holdout size 57. Mixed regimes and insufficient full folds fail. Snapshot tampering fails before population read.
- [ ] Write `test_protocol_immutability`: identical protocol returns same digest/path; changing seed/grid/snapshot creates another; existing changed bytes fail verification.
- [ ] Run `python -m uv run pytest tests/research/test_protocol.py -q`; expect missing-interface failures. Implement using Phase 3 verify_bundle; dates/indices from actual snapshot only.
- [ ] Run targeted tests; commit `feat: freeze chronological research protocols`.

### Task 2: exact odds, seeds and valid portfolios

**Files:** Create research/odds.py, policies.py, tests/research/test_odds.py, test_policies.py.

**Interfaces:** `match_pmf(pool: int) -> tuple[Fraction, ...]`; `derive_seed(protocol_digest: str, policy: str, target_date: date, budget: int, simulation_index: int, root_seed: int=20261009) -> int`; `uniform_portfolio(pool: int, budget: int, seed: int) -> tuple[tuple[int,...],...]`; `frequency_portfolio(history: list[ResearchDraw], budget: int, seed: int) -> tuple[tuple[int,...],...]`.

- [ ] Write `test_exact_pmf`: sum equals Fraction(1), pool=6 gives P(K=6)=1, pool=47 agrees with independent enumeration/formula, pool<6 fails.
- [ ] Write `test_seed_and_portfolios`: repeated inputs reproduce lines; budgets 1/5/10 have exact unique counts, six unique in-pool numbers each; equal frequency chooses [1,2,3,4,5,6]; altered future rows never affect historical-frequency inputs. Test impossible portfolio budget and attempt-cap error.
- [ ] Run `python -m uv run pytest tests/research/test_odds.py tests/research/test_policies.py -q`; expect failures. Implement spec's Fraction formula, SHA-256 seed derivation and PCG64 policies.
- [ ] Run tests and development synthetic Monte Carlo reconciliation using the exact tolerance in the spec; commit `feat: verify exact odds and seeded baseline portfolios`.

### Task 3: chronological runner, metrics and operations

**Files:** Create research/backtest.py, metrics.py, commands.py, tests/research/test_backtest.py, test_metrics.py; modify cli.py; create docs/baselines.md; revise docs/implementation-plan.md to refer to actual frozen protocol, removing assumed counts.

**Interfaces:** `run_development(protocol: Protocol, draws: list[ResearchDraw], policy: str, budget: int) -> list[PredictionRecord]`; `evaluate(predictions: list[PredictionRecord], targets: list[ResearchDraw]) -> list[EvaluatedRecord]`; `summarize(records: list[EvaluatedRecord]) -> dict`; `simulate_baselines(protocol: Protocol, draws: list[ResearchDraw]) -> dict`.

- [ ] Write `test_cutoffs_and_holdout_guard`: every max_input_date precedes target; targets belong only to validation folds; requested holdout execution raises ValueError; changing all future/holdout mains leaves earlier predictions identical.
- [ ] Write `test_metric_reconciliation`: line [1,2,3,4,5,6] against [1,2,3,7,8,9] yields matches=3, hit_3_plus=true, hit_5_plus=false; histogram sums to evaluated line count; portfolio any-line denominators count draws once; incomplete method/date/budget comparisons fail.
- [ ] Run targeted tests, implement runner/evaluation without mutable prediction attachment. Add `lotto research protocol SNAPSHOT --rule-code CODE`, `lotto research baselines PROTOCOL` and sanitized CLI failures; both refuse unverified protocol inputs.
- [ ] Verify real frozen protocol only after Phase 3 gate; use synthetic data for software checks now. No assumed external counts or holdout metrics in docs.
- [ ] Run research CLI/runtime checks, Ruff lint/format, full pytest and git diff --check. Commit, merge local main, repeat runtime/full tests, push only after success. Maintain no unrelated staging/discard.
