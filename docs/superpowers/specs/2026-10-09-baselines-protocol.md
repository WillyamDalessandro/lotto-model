# Phase 4: frozen protocol and baselines

Date: 9 October 2026. Status: draft for review; numerical choices below are proposed protocol decisions, not findings.

## Goal and prerequisites

Implement a verified null comparison and chronological development harness before training candidates. Consume only a Phase 3 verified snapshot and an explicitly chosen rule_code with pool=47. Require at least 282 eligible draws in one verified regime; otherwise emit insufficient_data. A different regime or minimum requires a reviewed protocol revision, never silent fallback. Undated data and prize/context values are not inputs.

## Frozen chronology

Sort regime draws chronologically, preserve observed ordering and carry gap flags. n_holdout=ceil(0.20*n), with the final n_holdout draws locked; preceding rows are development. Feature warmup is 150 draws, followed by 25 supervised training draws. Common baseline/candidate development validation begins at index 175, using successive nonoverlapping blocks of 25 targets; retain a final partial block only if it has >=10 targets. At least two full blocks are required. Indices are zero-based and intervals half-open; persist exact dates/indices in protocol.json.

Gaps are visible: frequency windows count observed draws, never fabricated observations. A lag pair crossing a missing scheduled draw is flagged; Phase 5 lag features must mark discontinuity. Rule transitions never share feature histories.

Freeze protocol version, snapshot digest, population, split, candidate families/search grid, feature definitions, line policy, metrics, retraining, uncertainty and seed policy before tuning. Store canonical JSON plus SHA-256; immutable directory under data/experiments/<protocol_digest>. Any change creates a new version. Preparing the protocol may identify holdout dates/counts, but development commands must refuse holdout evaluation. This is a local procedural safeguard, not security against someone reading the source snapshot.

## Baselines and policies

Primary: one six-number line per draw; hit_3_plus. Secondary: hit_5_plus and budgets 5/10. A portfolio is an unordered set of unique valid lines; compare methods only on identical target dates/budgets. Deterministic ties choose smaller numbers.

Uniform portfolios sample distinct six-number combinations uniformly using seeded rejection of duplicates. Frequency baseline uses the prior observed history: p_j=(count_j+6/47)/(history_count+1); one-line selection chooses the six largest p_j. Secondary frequency portfolios use probability-weighted sampling without replacement within a line and reject duplicate lines, with an explicit 100,000-attempt cap/error. No overlap optimisation in this initial protocol.

Derive each RNG seed as the first 16 hex characters of SHA-256(canonical JSON [root_seed,protocol_digest,policy,target_date,budget,simulation_index]), converted to an integer. root_seed=20261009. Use NumPy Generator(PCG64); pin the environment lock. Do not use Python's randomized hash(). Store the derived seed and selected lines.

For fixed line K, compute P(K=k)=C(6,k)C(N-6,6-k)/C(N,6) with impossible combinations treated as zero, k=0..6. Validate pools >=6. Return exact rational probabilities internally; convert to float only for reporting. N=47 initially.

Run 10,000 seeded random portfolio simulations on development only; use full portfolio draws, preserving overlap. For the single-line Monte Carlo reconciliation require abs(simulated_rate-exact_p) <= 5*sqrt(exact_p*(1-exact_p)/trial_count)+1/trial_count, with trial_count counting simulated target draws, not lines. Rare 5-plus rates are reported with event counts; this numerical tolerance is a validation rule, not a claim of significance.

## Metrics and interfaces

Predictions carry protocol/snapshot digest, target date, policy, budget, line index, six mains, seed and max_input_date. max_input_date < target_date. Evaluation appends outcomes to separate records, never edits issued lines. Report exact-match histogram, mean matches, 3/5-plus per-line and any-line portfolio rates with numerator/denominator/regime/date range. Compare whole draws, not draw-number rows.

Phase 5 selection: six configurations, logistic C in [0.01,0.1,1.0], boosting max_leaf_nodes in [3,7,15]; other parameters and features are fixed by its spec. Select highest pooled development one-line 3-plus rate, then lowest Brier, then lowest log loss, then stable candidate identifier. Retrain expanding history for every target. No calibration fitting or identity effects in version 1.

Primary inference: compare holdout 3-plus rate to exact single-line null p0. Use a 95% Clopper-Pearson interval for model rate and subtract p0 for the improvement interval. Report paired model-versus-seeded-baseline draw differences using 10,000 paired draw bootstrap replicates; circular block length 5 is a sensitivity analysis. It is not the primary interval.

Null evidence in Phase 5: 10,000 sequential null-history replicates of the frozen selected pipeline, with no retuning. Simulate independent uniform six-number draws across its history and targets, refit on simulated past at each target, and compute the same holdout statistic. Monte Carlo p=(1+count(null_stat>=observed_stat))/(10001). Secondary hypothesis tests use Holm adjustment in one family spanning nonprimary model/policy/budget/threshold comparisons; descriptive scores remain clearly labeled.

## Completion

Python >=3.12,<3.13; existing research extras; no new dependencies. No holdout result in this phase. Success requires exact-odds reconciliation, seed reproducibility, game/regime/date/budget parity, cutoff and future-perturbation tests, approved frozen protocol and complete runtime/full tests before and after local merge. Phase 5 consumes this protocol unchanged.
