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

## Phase 7 rulings (10 October 2026)

Branch: `codex/phase7-study`. The user directed that the Phase 2 ingestion must
fill the full dataset itself ("use python or web scrap"), that the best result
is the one that matches the most winning numbers, and that all available data
be used instead of the 282-draw minimum.

23. **Draw source: lotto.net yearly archives.** Its disclaimer allows personal
    use and has no harvesting or extraction prohibition. robots.txt allows the
    paths. The terms of irish.national-lottery.com, irishlottery.com and
    lottery.co.uk prohibit data harvesting (lottery.co.uk is now on the
    restricted list), and lottery.ie requires permission. Collection is 41
    requests at a 5-second crawl delay. Past years are cached and never
    refetched; only the current year is refreshed. Data stays local and is
    never pushed. Cost if wrong: the evidence store would need replacing with
    an operator-licensed export, with no schema change.
24. **Rule evidence: the Wikipedia article (CC BY-SA), checked phrase by
    phrase**, plus the August 2015 trade announcement for the 6/47 start
    (3 September 2015). Every phrase listed in `ingestion/backfill.py` must
    appear verbatim in the saved body, so a rewritten article stops the
    backfill.
25. **The 2006 boundary is not guessed.** Wikipedia says only "November 2006".
    6/42 ends on 31 October and 6/45 starts on the first Saturday, 4 November.
    The Wednesday 1 November 2006 draw stays staged as `unverified_rule`.
26. **Fixed €500,000 second draws (1994–1998) are skipped.** Some archive
    pages list a second fixed-jackpot draw after the main Lotto draw on the
    same date. The parser keeps the first (main) entry and rejects any other
    duplicate pattern.
27. **Pre-euro jackpots are not imported.** The archive shows pre-2002
    jackpots already converted to euro, and the conversion basis is unknown.
    Numbers and outcomes are kept.
28. **Schedule exceptions are reviewed calendar events.** There are 23 dated
    exceptions (Christmas Day moves and five other moved draws). Each is bound
    to its yearly archive page in `data/reviews/rule-bindings.json`.
29. **Studies run per rule regime, using all of each regime's draws.** Numbers
    and pool sizes differ between regimes, so pooling them would mix
    different games. The 6/47 study is primary. The 6/45 (2006–2015) and 6/42
    (1994–2006) studies are independent replications on their own last five
    years. The 282-draw minimum is a protocol gate only; the study uses every
    eligible draw.
30. **Tuning is leakage-safe.** It uses a predeclared grid (18 settings across
    logistic, gradient boosting, random forest and MLP), scored walk-forward on
    the 100 draws before the evaluation window. Selection is by lowest log
    loss, then the 3-plus rate. The 3-plus rate alone, over 100 draws, has
    about two expected hits and would select noise. The evaluation window
    (the last 1,826 days) never informs any choice.
31. **"Best" means most winning numbers matched.** Each source and method is
    ranked by mean main numbers matched on its best line per draw, relative to
    the chance mean for the same line count, with the 3-plus rate as the
    tiebreak. Both metrics are tested against chance. One Holm family covers
    both metrics for every source and method.
32. **The 40% target is reported as infeasible by prediction.** One random
    line hits 3+ with probability 2.1%. Ten coverage lines reach only about
    19%. Reaching 40% needs about 25 or more lines per draw, which is spending,
    not prediction. The study reports what each method actually achieves.
33. **Prize breakdowns come from lotto.net per-draw pages.** Only the first
    table under "Prize Breakdown" is read; that is the main Lotto draw. The
    Lotto Plus tables that follow are ignored. The numbers on each page are
    reconciled with the accepted draw, and a disagreement would quarantine
    it. Pre-2002 amounts stay unassigned (ruling 27). The "-" cells on old
    pages are unknown values, never zero. The crawl delay is 3 seconds:
    robots.txt sets none, and that is about one request every 3 seconds for a
    one-off backfill.
34. **Phase 5 runs on snapshot `a3ea572d…`, the same draws Phase 7 used.** The
    six candidates and the selection rule were fixed in Phase 4, and selection
    uses development folds only, so no tuning reaches the 230-draw holdout.
    The holdout is no longer unseen by the analyst, however: the Phase 7
    five-year window contains it. Phase 6 prospective records are therefore
    the only clean confirmation.
35. **Phase 6 starts with one uniform arm.** Its deadline is 19:45
    Europe/Dublin, from the saved Wikipedia body ("Ticket sales for Lotto close
    at 7:45 p.m. local time on draw nights"). It started on 12 October 2026
    under 6/45-2026 (Monday, Wednesday and Saturday draws). No model arm runs:
    there are 15 draws of the current game, the trained models are for 6/47,
    and Phase 7 found no model better than chance. No deadline overrides were
    set; holiday changes need reviewed evidence. Results arrive through
    `lotto data collect`.
36. **Baseline simulations and null replicates run in parallel.** Each
    simulation and each null replicate draws from its own seed, derived from
    its index, so splitting the work across processes leaves every number
    unchanged. Tests check that parallel and sequential runs give equal
    results. Without this, 10,000 baseline simulations (about 4.7 hours) and
    10,000 null refits would not finish in a working session.
37. **Phase 5 inference stops at 100 null refits.** Each refit repeats the
    230-draw holdout training, and takes about 1.5 minutes even in parallel.
    The 10,000 refits the protocol needs for a final verdict would take about
    10 days. The report therefore stays "Not final". The exact uniform
    comparison and the Clopper-Pearson interval do not depend on the refits,
    and they already show no demonstrated advantage. More refits can be
    resumed later with `lotto research nulls --count 10000 --workers N`.
38. **Reconstruction is judged on values, not digests.** A snapshot digest
    covers provenance: evidence hashes, observation keys and counts of
    staged, undated records. A rebuild that refetches the current year's
    page therefore always gets a new digest, even when no value has
    changed. Phase 2 reproducibility is accepted because the draws, rules,
    prize tiers and context are identical once those provenance fields are
    removed. Past-year pages are cached, so their provenance is identical
    too.
