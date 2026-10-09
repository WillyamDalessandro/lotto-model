# Phase 7 study: models and methods over the last five years

Run on 10 October 2026 against the audited snapshot
`a3ea572d5deacd3cd80336a8cc682d55f4e8c25c4979b789c9b8572d1744766d` (3,909
real draws, 1988–2026). Outputs are local under `data/studies/<config digest>/`
and are not pushed: `findings.md`, `summary.csv`, `yearly.csv`,
`calibration.csv`, `tuning.csv`, `predictions.csv`, `evaluation.csv` and
`manifest.json`.

```bash
uv run lotto research study data/snapshots/<digest> --rule-code 6/47
```

## What was tested

- **Data:** every eligible draw of each rule regime. 6/47 (1,148 draws) is the
  primary study. 6/45 (2006–2015, 922 draws) and 6/42 (1994–2006, 1,263 draws)
  are independent replications. Pools differ between regimes, so they are not
  mixed (ruling 29).
- **Evaluation window:** the last five years (1,826 days) of each regime, 522
  draws each. Every evaluated draw is predicted by a model fitted only on
  earlier draws, refitted every 25 draws.
- **Automatic tuning:** 18 predeclared settings across four model families
  (logistic regression, gradient boosting, random forest, MLP neural network).
  Each setting is scored walk-forward on the 100 draws before the window. The
  evaluation draws never influence any choice (ruling 30).
- **Sources of number probabilities:** the four tuned models, smoothed
  historical frequency, and uniform (chance).
- **Prediction methods:**
  - top-six line;
  - probability-weighted line;
  - 5-line and 10-line coverage portfolios;
  - hot, cold and overdue heuristics;
  - 1, 5 and 10 random lines.
- **Scoring (ruling 31):** "best" means the most winning main numbers matched
  on the best line per draw, compared with chance for the same number of
  lines. The 3-plus hit rate is the second test. One Holm correction covers all
  52 tests per regime.

## Results

| Regime (window) | Best observed by numbers matched | Matched vs chance | Its 3+ rate vs chance | Holm p (matched) | Any significant? |
|---|---|---|---|---|---|
| 6/47 (Sep 2021 to Sep 2026) | forest / weighted line | 0.797 vs 0.766 | 1.5% vs 2.1% | 1.000 | No |
| 6/45 (Sep 2010 to Sep 2015) | MLP / weighted line | 0.874 vs 0.800 | 3.4% vs 2.4% | 0.833 | No |
| 6/42 (Oct 2001 to Oct 2006) | heuristic / hot numbers | 0.958 vs 0.857 | 3.6% vs 2.9% | 0.108 | No |

Best 3-plus rates reached, all within chance after correction:

| Regime | One line (chance) | Best 10-line portfolio (chance) |
|---|---|---|
| 6/47 | 2.9%, boosting top6 (2.1%) | 21.1%, boosting coverage10 (19.3%) |
| 6/45 | 3.4%, MLP weighted (2.4%) | 23.6%, logistic coverage10 (21.6%) |
| 6/42 | 4.8%, frequency top6 (2.9%) | 28.2%, forest coverage10 (24.0%) |

The probability calibration ranking was identical in all three regimes:
uniform chance probabilities had the lowest log loss and Brier score.
Every trained model and the frequency baseline scored slightly worse than
assuming every number is equally likely.

## What this means

1. **No model or method predicts winning numbers better than chance.** None of
   the 156 tests across three regimes survived correction. The trained models'
   probabilities are worse than uniform, so the models learned nothing
   transferable.
2. **The "best" method changes in every regime** (forest, then MLP, then hot
   numbers). A real edge would repeat; this pattern is what luck looks like
   when 26 methods compete.
3. **The 40% target.** No method reaches it. The ceiling is set by how many
   lines are played, not by the model. One line hits 3+ on 2.1–2.9% of draws.
   Ten coverage lines reach about 19–24% by chance. At about 2% per line,
   roughly 25 or more lines per draw are needed to cross 40%. That is the cost
   of buying more lines, not a better prediction.
4. **Coverage portfolios change the shape, not the odds.** Spreading numbers
   across non-overlapping lines raises the expected numbers matched on the
   best line. For 6/47 with 10 lines, chance gives 2.13 matched for coverage
   lines and 2.03 for random lines. The chance of 3-plus on some line stays
   about the same (19.3% and 19.1%). This is arithmetic, not prediction, and
   the chance column already accounts for it.
5. **Power limits.** With 522 draws per window, a one-line 3-plus rate would
   need to be around 4.5% or more (about double chance) to be detected after correction
   reliably. Smaller real effects cannot be excluded, but none of the
   observed differences is consistent across regimes.

## Software verification

A run on synthetic uniform draws of the same size (1,158 draws) also reported
no advantage. That run took 221 s. The test suite covers leakage (tuning is
unchanged when evaluation outcomes are altered), reproducibility (identical
manifests on rerun), exact null rates and coverage portfolios for every pool.

## Next steps

- Prospective tracking (Phase 6) on the current 6/45-2026 regime is the only
  clean confirmation of any idea, because future draws cannot have been tuned
  on.
- Prize breakdowns (about 3,900 per-draw pages) remain to be backfilled. They
  matter for cost and return analysis, not for number prediction.
