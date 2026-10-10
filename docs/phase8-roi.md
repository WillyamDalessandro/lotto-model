# Phase 8: context datasets, model selection and return on investment

Run on 10 October 2026 against snapshot `58810b97…`, which includes prizes
and jackpots. Outputs are local under `data/studies/` and `data/reports/`.

## 1. Datasets and models tested (selection stage)

- **Data:** 6/47 draws up to 19 June 2024. The evaluation window was the last
  1,000 days: 286 draws.
- **Tuning:** each of the four model families (logistic, boosting, forest,
  MLP) was tuned on the 100 draws before the window.
- **Context features**, all known before each draw (ruling 42):
  - jackpot: the advertised jackpot, rollovers, and days since the jackpot
    was last won;
  - holiday: days to the nearest Irish public holiday, and a flag for within
    3 days;
  - prize: the previous draw's Match 3 winners, Match 4 prize and Match 5
    prize.

| Training data | Best by numbers matched (vs chance) | Best one-line 3+ (vs chance) | Best 10-line 3+ (vs chance) | Best model log loss minus uniform | Significant |
|---|---|---|---|---|---:|
| all earlier draws of the regime; context: jackpot; draws up to 2024-06-19 | mlp/top6 0.846 vs 0.766 (Holm 1.00) | boosting/top6 2.4% vs 2.1% | forest 20.6% vs 19.5% | +0.00021 | 0 |
| the latest 250 earlier draws of the regime; context: jackpot, holiday, prize; draws up to 2024-06-19 | boosting/weighted 0.818 vs 0.766 (Holm 1.00) | boosting/top6 3.5% vs 2.1% | boosting 24.1% vs 19.4% | +0.00033 | 0 |
| all earlier draws of the regime; context: prize; draws up to 2024-06-19 | mlp/weighted 0.808 vs 0.766 (Holm 1.00) | forest/top6 2.8% vs 2.1% | logistic 19.9% vs 19.5% | +0.00021 | 0 |
| all earlier draws of the regime; draws up to 2024-06-19 | mlp/top6 0.853 vs 0.766 (Holm 1.00) | boosting/top6 3.1% vs 2.1% | logistic 19.9% vs 19.5% | +0.00020 | 0 |
| all earlier draws of the regime plus all draws of 6/45; context: jackpot, holiday, prize; draws up to 2024-06-19 | mlp/weighted 0.811 vs 0.766 (Holm 1.00) | mlp/top6 2.8% vs 2.1% | mlp 20.6% vs 19.5% | +0.00019 | 0 |
| all earlier draws of the regime; context: holiday; draws up to 2024-06-19 | mlp/weighted 0.867 vs 0.766 (Holm 0.68) | mlp/top6 3.1% vs 2.1% | logistic 19.9% vs 19.4% | +0.00021 | 0 |
| all earlier draws of the regime; context: jackpot, holiday, prize; draws up to 2024-06-19 | forest/weighted 0.850 vs 0.766 (Holm 1.00) | forest/top6 2.8% vs 2.1% | logistic 19.9% vs 19.5% | +0.00018 | 0 |
| all earlier draws of the regime plus all draws of 6/42, 6/45; draws up to 2024-06-19 | mlp/top6 0.790 vs 0.766 (Holm 1.00) | boosting/weighted 2.8% vs 2.1% | logistic 20.6% vs 19.1% | +0.00010 | 0 |

- **Pre-registered rule:** pick the highest one-line 3+ rate among 64
  candidates (8 datasets, 4 models, 2 one-line methods).
- **Winner:** boosting, top-six line, trained on the latest 250 draws with all
  context. It hit 3+ on 10 of 286 draws (3.5%), against 2.1% by chance.
- **No result was significant** after correction. Every dataset's best model
  scored 2.4% to 3.5%. A spread like that is expected by luck.

## 2. Confirmation on unseen draws

The winner ran once on the 230 draws from 22 June 2024 to 2 September 2026.
Its hyperparameters were retuned on the 100 draws before that window, as
the rule requires.

| Candidate | 3+ hits | Rate | Chance | 95% interval | p (greater) |
|---|---|---|---|---|---|
| Selected: boosting/top6, 250 draws plus context | 5/230 | 2.17% | 2.10% | 0.71% to 5.00% | 0.53 |
| One random line | 6/230 | 2.61% | 2.10% | 0.96% to 5.59% | 0.36 |

**The 3% target was not reached.** The 3.5% in selection was luck. On unseen
draws the model scored the same as chance, and below one random line.
Adding prize, jackpot and holiday data did not help, which is expected:
the balls do not know the jackpot or the calendar (see the Phase 7 prize
analysis).

## 3. Return on investment: current game (6/45, three draws a week)

`lotto research roi data/snapshots/<digest>` builds this report. The full
tables are in `data/reports/roi-fair.md`.

Inputs:
- price EUR 2 per line (ruling 43);
- median prizes paid in the 15 draws of the new game;
- next jackpot EUR 2,000,000, because the jackpot was won on 7 October;
- about 534,000 lines sold per draw, estimated from Match 3 winners. That
  gives an expected jackpot share of 96.8%.

| Plan | Cost | Chance of a big prize (Match 5+Bonus or jackpot) | Chance of the jackpot | Expected net |
|---|---:|---|---|---:|
| 1 line, 1 draw | EUR 2 | 1 in 1,163,580 | 1 in 8,145,060 | -EUR 1 |
| 1 line, every draw for 1 year (156) | EUR 312 | 1 in 7,459 | 1 in 52,212 | -EUR 228 |
| 10 lines, every draw for 1 year | EUR 3,120 | 1 in 746 (0.13%) | 1 in 5,222 | -EUR 2,278 |
| 100 lines, every draw for 1 year | EUR 31,200 | 1 in 75 (1.33%) | 1 in 520 (0.19%) | -EUR 22,775 |
| Enough lines for a 50% chance in one draw | EUR 1.6 million (806,532 lines) | 50% | 9.9% | -EUR 1.18 million |

- **Expected return:** at the current EUR 2 million jackpot, a EUR 2 line
  returns EUR 0.54 on average, which is 27 cents per euro.
- **Break-even:** the advertised jackpot must reach about EUR 14.3 million
  before a line returns its price on average. The cap is EUR 16 million.
  At the cap the return is about EUR 1.10 per euro, if the sales estimate
  holds. In practice a bigger jackpot sells more lines and is shared more
  often, so this is optimistic.
- **The ideal number of lines.** Return per euro is the same for 1 line or
  1,000 lines, because distinct lines add chances and cost in proportion.
  - Below the break-even jackpot, the best expected return comes from
    playing nothing.
  - Near the cap, each line has a small positive expectation. Almost all of
    it is the jackpot, which one line wins once in 8.1 million draws.
  - The only way to raise the chance of a big prize is to buy more lines,
    and the cost rises in step.
- **What-if:** suppose the unconfirmed 3.5% held and lifted every tier by a
  factor of 1.67 (`data/reports/roi-whatif.md`). A line would still return
  only EUR 0.90 per EUR 2 at the current jackpot, and break-even would need
  EUR 7.6 million.
- **The one lever the data supports** is choosing numbers above 31. It does
  not change any probability. It raises the prize per win, because fewer
  players share it.
