# Phases 2–6 implementation decisions

Date: 9 October 2026. Branch: `codex/phase-implementation`. This file records
the decisions taken while implementing the roadmap specs and plans without a
live reviewer. Each entry gives the ruling, the reason and the cost if it is
wrong. **Software completion is not data completion.** The research database
still has no accepted draws, so the Phase 2 acquisition, Phase 3 real
snapshot, real protocol freeze, the historical study and prospective issuance
all remain blocked on permitted inputs.

## What was delivered

| Phase | Delivered (synthetic verification) | Real-data gate still open |
|---|---|---|
| 2 completion | `lotto data batch`, `acquisition-status`, null-bonus support | Permitted dated export, rule/prize/jackpot evidence |
| 3 | `lotto audit report/snapshot/verify`, `dataset_snapshots` (0003) | Nonempty audited bundle, backup/restore review |
| 4A | `docs/ai-model-research.md` (evidence, power, decision record) | Reviewer acceptance of shortlist and power framing |
| 4B | `lotto research protocol/baselines`, exact odds, seeded baselines | Protocol frozen on a real snapshot |
| 5 | Features, six candidates, ledger (0004), holdout, nulls, reconcile, report, predict | Real development, freeze and once-only holdout |
| 6 | Prospective protocol/issue/evaluate/report (0005), shared draw lock | Reviewed current-regime protocol and deadlines |
| 6 optional play | Not implemented | User spending limits and verified prices |

## Rulings

1. **One feature branch for all phases.** The plans assumed one branch per
   phase. Phases 3–6 depend on each other's code. Cost: one larger review
   instead of five, mitigated by one commit per phase.
2. **Unknown bonus is stored as no bonus row.** Previously an observation
   without a bonus was staged as `invalid_numbers`, which contradicted the
   acquisition and audit specs ("missing bonus stays null"). A later compatible
   observation may fill it. A contradicting bonus is still a number conflict.
   Cost: draws exported with an empty bonus field. The bonus is not used by any
   model.
3. **`validate_batch` returns a `PreparedBatch`** (batch plus verified parsed
   records) rather than only `AcquisitionBatch`, so import never re-reads
   unverified bytes. Batch adapters are limited to `csv`/`observations`; the
   site-scraping `auto` adapter is refused for batches.
4. **`acquisition-status` always reports `complete: false`.** Completion is a
   human assessment (spec: "must never say phase 2 is complete merely because
   imports or tests pass").
5. **Identical (hash, URL) artifact rows count as one piece of rule evidence.**
   The plan said duplicate matches should fail as ambiguous. Rows with the same
   SHA-256 and URL hold identical bytes, and batch replays legitimately create
   them under different source codes. Cost: none for integrity. Ambiguity can
   only arise from different hashes, and exact binding resolves those.
6. **An empty schedule is unknown**, even for a verified rule. This follows the
   spec text ("an empty schedule is unknown, not proof of zero").
7. **Registry rows and all ledger rows are protected by a `reject_mutation()`
   trigger.** The spec only required the application to avoid updates. Tests
   remove rows with TRUNCATE, which does not fire row triggers.
8. **Integration tests that need committed rows TRUNCATE the isolated test
   database**, guarded by the existing `_test` name check and an emptiness
   check. Cost: no persistent fixtures in the test database (none existed).
9. **Uniform lines use the six smallest of `pool` i.i.d. uniforms** (an exactly
   uniform 6-subset) instead of `Generator.choice`, for speed. The seed
   derivation follows the spec exactly. Cost: none statistically. Seeds
   reproduce within this implementation.
10. **Frequency portfolios for budgets above 1 keep the top-six line first**,
    then add probability-weighted unique lines. That way the primary line sits
    inside every portfolio. The spec did not settle this.
11. **The candidate selection order stays as the spec defines it** (3-plus rate,
    then Brier, then log loss, then ID). Phase 4A proposed ranking by log loss
    first, because 3-plus events are too rare in development (about one expected
    hit). That change alters a predeclared rule, so it is left as an **open
    review item** and should be decided before any real protocol is frozen.
12. **`LogisticRegression` is built without `penalty=`**, because the parameter
    is deprecated in the installed scikit-learn 1.9. The default L2 matches the
    spec.
13. **The model artifact is JSON.** It holds logistic parameters, or a
    deterministic refit specification for boosting. No pickle/joblib file is
    ever written or loaded, which satisfies the spec's untrusted-artifact rule.
    `predict` refits from verified history. Cost: inference refits each time
    (seconds).
14. **A holdout identity in `failed` or `evaluating` status can be resumed**
    with its issued lines reused. It cannot be re-run as a fresh confirmatory
    run: a changed configuration is a new identity. Interruptions are therefore
    recoverable without regenerating predictions.
15. **Holdout baselines are recomputed deterministically at export** from
    seeds, not stored in the ledger. Their seeds and lines appear in
    `prediction_log.csv`.
16. **Secondary inference family:** the one-line 5-plus exact binomial test,
    plus one-sided paired-bootstrap p-values for budget-5 and budget-10
    any-line 3-plus against uniform, with Holm adjustment. All are labelled
    descriptive.
17. **The historical study is reported as bounded-effect** (from Phase 4A). The
    report states the minimum detectable rate, and "no demonstrated advantage"
    names the undetectable range instead of implying equality.
18. **Null refits run the full frozen pipeline per replicate**, as the spec
    requires, with one checkpoint file per replicate. This is computationally
    heavy (10,000 × holdout targets fits), so compute must be planned before
    the real run. The report marks inference "Not final" below 10,000.
19. **Prospective deadlines are protocol data.** Each one is a local time plus
    an IANA timezone, with optional aware overrides. No deadline or draw time
    was guessed. The placeholder in the docs is labelled as such.
20. **The draw advisory lock lives in `lotto_model.locks`** and is taken by
    `Repository.ingest` and prospective `issue`. Issuance reads
    `clock_timestamp()` only after acquiring it.
21. **Optional manual play preparation (plan Task 4) is not implemented.** Its
    prerequisites (explicit opt-in, EUR limits, verified prices and minimum
    lines) were not supplied, and inventing them is prohibited.
22. **Local merge only.** The work is merged into local `main` after checks,
    and is not pushed to `origin` without the user's confirmation.

## Open items for review

- Accept or amend the Phase 4A recommendations: the shortlist, no neural
  models, selection ordering (ruling 11), bounded-effect framing, and the
  282-draw minimum, which only detects about 4.5× uniform.
- Supply permitted historical exports with dated rule/prize/jackpot evidence,
  then run batch, audit, snapshot and protocol in that order.
- For Phase 6: a reviewed issue-deadline source and current 6/45 rule evidence.
  For optional play: spending limits and price evidence.
