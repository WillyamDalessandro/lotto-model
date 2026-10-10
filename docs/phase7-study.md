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

## Training-data combinations (6/47)

The evaluation stayed fixed: the same 522 draws of 6/47 (September 2021 to
September 2026), the same chance comparison and the same 52-test Holm family.
Only the training data changed. Tuning still used only the 100 draws before
the window. Pooled games ended in 2015 or earlier, so no future draw leaked
in. Pooled rows carry an extra base-rate feature (6/pool) because the number
ranges differ (ruling 41).

```bash
uv run lotto research study data/snapshots/<digest> --rule-code 6/47 --training-window 250
uv run lotto research study data/snapshots/<digest> --rule-code 6/47 --pool-with 6/42 --pool-with 6/45
uv run lotto research compare data/studies/<a> data/studies/<b> ...
```

| Training data | Best by numbers matched (vs chance) | Best one-line 3+ (vs chance) | Best 10-line 3+ (vs chance) | Best model log loss minus uniform | Significant |
|---|---|---|---|---|---:|
| all earlier draws of the regime | forest/weighted 0.797 vs 0.766 (Holm 1.00) | boosting/top6 2.9% vs 2.1% | boosting 21.1% vs 19.3% | +0.00014 | 0 |
| the latest 250 earlier draws of the regime | mlp/weighted 0.816 vs 0.766 (Holm 1.00) | boosting/top6 2.7% vs 2.1% | logistic 23.0% vs 19.0% | +0.00011 | 0 |
| the latest 500 earlier draws of the regime | boosting/weighted 0.808 vs 0.766 (Holm 1.00) | mlp/top6 2.9% vs 2.1% | logistic 20.9% vs 19.2% | +0.00012 | 0 |
| all earlier draws of the regime plus all draws of 6/45 | mlp/top6 0.820 vs 0.766 (Holm 1.00) | forest/weighted 3.3% vs 2.1% | mlp 21.1% vs 19.0% | +0.00016 | 0 |
| all earlier draws of the regime plus all draws of 6/42, 6/45 | forest/weighted 0.822 vs 0.766 (Holm 1.00) | forest/weighted 3.3% vs 2.1% | mlp 19.3% vs 19.0% | +0.00010 | 0 |
| all earlier draws of the regime plus all draws of 6/36, 6/39, 6/42, 6/45 | forest/coverage10 2.151 vs 2.130 (Holm 1.00) | forest/top6 2.9% vs 2.1% | boosting 20.5% vs 19.3% | +0.00012 | 0 |

- **No combination produced a significant result.** Every Holm p-value is
  1.00.
- **Every model's probabilities stay worse than uniform** (positive log-loss
  gap) with every training set. More data, older data and only recent data
  all fail to improve on "every number equally likely".
- **The winning model changes with every training set** (forest, MLP,
  boosting, forest, forest). The best one-line rate stays between 2.7% and
  3.3%, against 2.1% by chance. One-line 3.3% is 17 hits in 522 draws, which
  is within what the best of 26 methods reaches by luck.
- **Training on recent draws only did not help.** A drift or a recent bias
  in the machines would have shown up here.
- **Pooling more history did not help either.** About 2,400 extra draws from
  1990 to 2015 only add more independent random outcomes.

## Software verification

A run on synthetic uniform draws of the same size (1,158 draws) also reported
no advantage. That run took 221 s. The test suite covers leakage (tuning is
unchanged when evaluation outcomes are altered), reproducibility (identical
manifests on rerun), exact null rates and coverage portfolios for every pool.

## Next steps

- Prospective tracking (Phase 6) on the current 6/45-2026 regime is the only
  clean confirmation of any idea, because future draws cannot have been tuned
  on.
- Prize breakdowns are now backfilled (snapshot `58810b97…`). They matter for
  cost and return analysis, not for number prediction. The draws are
  unchanged, so these results stand.

## Does the prize or jackpot matter? (6/47, 1,148 draws)

**Jackpot size does not affect which numbers are drawn.**

| Test | Result |
|---|---|
| Jackpot size vs sum of the numbers drawn | Spearman -0.03, p = 0.37 |
| Jackpot size vs how many numbers drawn are 31 or under | Spearman 0.00, p = 0.89 |
| Number frequencies, high-jackpot vs low-jackpot draws | chi-square p = 0.60 |

**The numbers drawn strongly affect how much each winner is paid.** Many
players choose dates (1 to 31), so when the draw contains many of those
numbers, more people win and each share is smaller.

| Tier | More numbers of 31 or under drawn means |
|---|---|
| Match 3 | lower prize (Spearman -0.84) |
| Match 4 | lower prize (Spearman -0.81) and more winners (+0.47) |
| Match 5 | lower prize (Spearman -0.51) and more winners (+0.42) |

| Numbers drawn that are 31 or under | 0–1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Median Match 4 prize | about €62–64 | €62 | €60 | €54 | €45 | €35 |

Choosing numbers above 31 does not change the odds of matching. It does
raise the expected payout when a line wins, because fewer people share the
prize. This is the only lever the data supports. It is about value per win,
not about predicting numbers. Ticket price is not stored in the snapshot
and cannot affect a mechanical draw.
