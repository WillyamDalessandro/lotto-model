# Phase 4A — AI model, training dataset and methodology research

Date: 9 October 2026. Status: research draft for review. The shortlist, protocol changes and budgets below are **provisional** pending review and a verified Phase 3 snapshot. Nothing here authorises training, and no model is declared best before evaluation.

All web sources were accessed on 2026-10-09. Numerical results in section 5 were computed in this session with the project environment (Python 3.12, SciPy 1.18.1, scikit-learn 1.9.1, NumPy 2.5.3); the script is reproduced in Appendix A.

## 1. Summary of findings

1. **No credible out-of-sample evidence exists that any model predicts lottery main numbers better than uniform selection.** Extended searches for peer-reviewed LSTM/neural lottery-prediction papers returned none. The two arXiv items found are a self-declared satire (E7) and an in-sample backtest without a random baseline (E8). Blogs and code repositories surfaced by search were either inaccessible (HTTP 403) or not evaluable, and none is cited as evidence.
2. **Fairness-testing literature mostly finds draws consistent with uniformity** (Canada 6/49, 1,798 draws, E1; Romania 6/49, 2,706 draws, E3), with isolated historical anomalies in other games (E2) and laboratory evidence that small ball-mass differences can bias an air-mix machine (E5). Detecting a historical anomaly after the fact is not evidence of an exploitable, persistent, forecastable bias.
3. **Power is the binding constraint.** Under 6/47, p0 = P(≥3 matches) = 75,249/3,579,191 ≈ 0.02102 (1 in 47.6). The provisional 282-draw minimum gives a 57-draw holdout, which detects (80% power, one-sided α = 0.05) only a rate of about 0.095, i.e. **4.5× uniform**. Even 4,000 holdout draws detect only about 1.29×. A 10% relative lift needs roughly 30,000 draws. **The 282-draw minimum and a 20% holdout cannot detect any realistic improvement**; the historical study can at best rule out large effects.
4. **≥5 matches is effectively unmeasurable**: p0 ≈ 2.3×10⁻⁵ (1 in 43,472). With 4,000 draws the expected uniform count is 0.09 events.
5. **Recommendation:** keep uniform and smoothed-frequency baselines plus regularised logistic and shallow boosting as the provisional shortlist. **Do not implement neural/sequence models**: there is no supporting evidence, the data are a few hundred draws, and the comparative forecasting literature (E10) and random-data studies (E9) point to overfitting and false discoveries at this scale.
6. Re-frame the historical study as a **bounded-effect (screening) study** reporting what improvements can be excluded, with any "promising" claim deferred to prospective confirmation.

## 2. Evidence register

Classification: **OOS** = genuine chronological out-of-sample evaluation against a stated baseline; **IS** = in-sample fit or backtest whose parameters/choices used the evaluated data; **Unsupported** = claim without an evaluable validation design; **Reference** = method/library documentation (no empirical claim about lotteries); **Fairness** = test of draw uniformity (not prediction).

### 2.1 Lottery randomness and fairness testing

| ID | Source (direct link) | Method | Dataset / regime | Validation design | Reported result | Reproducibility | Limitations | Class |
|---|---|---|---|---|---|---|---|---|
| E1 | Genest, Lockhart & Stephens, "χ² and the lottery", *The Statistician* 51(2), 243–257, 2002 — [PDF](https://www.sfu.ca/~lockhart/Research/Papers/GenestLockhartStephensJRSSD02.pdf) | Pearson X² for equiprobability of single numbers and subsets (c = 1..6); derives correct asymptotic law (weighted sum of χ²) because draws are without replacement | Canada Lotto 6/49, first 1,798 draws, 12 Jun 1982 – 14 Apr 2001 | Hypothesis test on full history; power curves from 10,000 Monte Carlo repetitions | Six-ball p-values 0.104–0.633 for c = 1..6; no rejection at 5%. Seven-ball (with bonus) c = 1 gives p = 0.044 before multiplicity | Formulae explicit; data from private websites of the time | Aggregate tests "not designed to detect" serial dependence; power invalid if machine/balls change | Fairness |
| E2 | Coronel-Brizio, Hernández-Montoya, Rapallo & Scalas, "Statistical auditing and randomness test of lotto k/N-type games", arXiv:0806.4595 (2008; *Physica A* 387(25)) — [arXiv](https://arxiv.org/abs/0806.4595) | Hypergeometric means/covariances of sorted draw order statistics; quadratic-form Q test, CLT and 5,000-replicate Monte Carlo p-values | Mexican Melate (N = 39/44/47/51; 555/992/330/211 draws) and Italian Lotto 5/90 Rome wheel (450/788/359/315 draws), 1984–2007 | Per-period hypothesis tests | Melate N = 51: Q = 18.25, p = 0.0056; Italian 1984–1993: Q = 31.17, p < 10⁻⁵; other periods consistent with fairness | Method fully specified | Eight period tests, no multiplicity adjustment; retrospective detection, no forecasting evaluation | Fairness |
| E3 | Ungar, "Investigating Randomness and Fairness in the Romanian 6/49 Lottery", *Revista Economica* 77(1), 13–24, 2025 — [IDEAS abstract](https://ideas.repec.org/a/blg/reveco/v77y2025i1p13-24.html) | χ² frequency test, cumulative frequencies, Monte Carlo simulation | Romania 6/49, 2,706 draws, 8 Aug 1993 – 16 May 2024 | Hypothesis test on full history | χ² = 62.61, p = 0.0766; no significant deviation at 5% | Abstract only read | Whether χ² was corrected for sampling without replacement (cf. E1) not verified from the abstract | Fairness |
| E4 | Grant, "Uncovering Bias in Order Assignment", arXiv:2103.11952 (*Economic Inquiry* 61(1), 82–98, 2023) — [arXiv](https://arxiv.org/abs/2103.11952) | Three "untargeted" tests for randomness of an ordering | Powerball draw order, American Idol order, ballot order (TX, WV) | Hypothesis tests | Deviations found for ballots; abstract reports no Powerball result | Abstract only read | Order tests, not number prediction | Fairness |
| E5 | Pinitsoontorn, Buathong & Srisodaphol, "Is it possible to cheat the lottery draw by weighing?", *Asia-Pacific J. Sci. Technol.* 19(6), 804–818 — [article](https://so01.tci-thaijo.org/index.php/APST/article/view/83061) | Model air-blown machine, foam balls 0–9; χ² / one-sample proportion tests | 1,000 draws per configuration; re-analysed subsets of 50/200/500 | Controlled physical experiment | Balls 1% or 5% lighter: unfair (p < 0.05); heavier: not detected; conclusions changed with sample size | Laboratory set-up described | Model machine, 10 balls; not an operator machine; no prediction | Fairness |
| E6 | Boland & Pawitan, "Trying To Be Random in Selecting Numbers for Lotto", *J. Statistics Education* 7(3), 1999 — [data file](https://jse.amstat.org/datasets/lotto.txt) | Teaching dataset comparing human, real and simulated selections | 234 student, 264 actual Irish Lotto 6/42 winning combinations (24 Sep 1994 – 8 Mar 1997), 264 simulated | None (teaching data) | Not a prediction study | Fixed public file | Individual draw dates absent (see `docs/superpowers/specs/2026-10-09-expanded-collection.md`); 6/42 regime | Fairness / data |
| E20 | National Lottery, "Change is coming" — [press release](https://www.lottery.ie/news/press-releases/change-is-coming) | Operator announcement | Pool 47 → 45 from Sat 5 Sep 2026; last 47-ball draw Wed 2 Sep; Monday draws from 7 Sep; jackpot odds 1 in 10.7m → 1 in 8.1m | — | Regime change confirmed | Operator page | Does not itself state historical rule intervals | Reference |
| E21 | Irish Post, 9 Oct 2017 — [article](https://www.irishpost.com/news/irish-lotto-accused-fixing-draw-light-blamed-ball-appearing-show-two-numbers-136297) | News report of operator statement | — | — | Operator states ball weight/size are checked before each draw and the draw is independently observed by auditors (KPMG) | Secondary source | 2017 statement; current procedure not verified | Reference |

### 2.2 Published lottery-prediction claims (critical assessment)

| ID | Source | Method | Dataset | Validation design | Reported result | Assessment | Class |
|---|---|---|---|---|---|---|---|
| E7 | Birk, "SmileyNet — Towards the Prediction of the Lottery by Reading Tea Leaves with AI", arXiv:2407.21385 (2024) — [arXiv](https://arxiv.org/abs/2407.21385) | Neural network "forecasting" coin flips from simulated tea-leaf images; bits combined to encode 6/49 numbers | Simulated images; German 6/49 used only as a worked example | Small simulated test set (e.g. 200 cases for baselines) | 72% coin-flip accuracy; derived jackpot probability | The author states it is "a satirical accumulation of misconceptions, mistakes, and flawed reasoning" for teaching. Useful as a checklist of failure modes, not evidence | Unsupported (satire) |
| E8 | Nkomozake, "Predicting Winning Lottery Numbers", arXiv:2403.12836 (2024) — [arXiv](https://arxiv.org/abs/2403.12836) | Compound-Dirichlet-Multinomial model; parameters by MLE / moments / "main diagonal" | South Africa 6/52 (1,971 draws), Oklahoma Cash 5 (4,642), Vermont Pick 3 (5,844) | Code compares model predictions with historical draws; no stated chronological holdout, no random baseline | Average "time difference" between ≥3-number hits of 105 draws on 6/52; 5- and 6-number intervals extrapolated because none occurred; a progressive-staking "3-strategy" claimed profitable | Not OOS. For comparison a uniform 6/52 line hits exactly 3 about once per 67 draws (computed here), so the reported figure does not indicate an advantage. Staking escalation does not change per-ticket odds | IS / Unsupported |
| — | Search for peer-reviewed LSTM/transformer lottery-prediction papers (standard and extended web searches, 2026-10-09) | — | — | — | None found. Results were blogs, Medium posts (HTTP 403 when opened), code repositories and one conference page (e3s-conferences.org, HTTP 403). None was evaluable; none is cited as evidence | Absence of evidence recorded as a search outcome | — |

### 2.3 Machine-learning methodology evidence

| ID | Source | Method | Data | Validation design | Result relevant here | Limitations | Class |
|---|---|---|---|---|---|---|---|
| E9 | Cheng & Petrides, "Evaluating The Predictive Reliability of Neural Networks in Psychological Research With Random Datasets", *Educ. Psychol. Meas.* 85(1), 2025 — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11572089/) | Monte Carlo: Keras MLPs trained on pure-noise predictors/outcomes | n = 50, 100, 200, 500; 3–10 predictors | 80:20 train/test, early stopping | On random binary outcomes, "decision errors" (spurious test performance, e.g. balanced accuracy ≥ 0.6) were common at small n (31.9% in one n = 50 condition); authors recommend ≥ 500 for BA ≥ 0.6 | Ordinal predictors, small architectures, single split | OOS (simulation) |
| E10 | Makridakis, Spiliotis & Assimakopoulos, "Statistical and Machine Learning forecasting methods: Concerns and ways forward", *PLOS ONE* 13(3): e0194889, 2018 — [article](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0194889) | 8 statistical vs 10 ML methods incl. MLP, RNN, LSTM | 1,045 M3 monthly series, 81–126 observations | Last 18 observations held out; sMAPE/MASE | ML methods "dominated across both accuracy measures" and all horizons; computational requirements "considerably greater" | Business series, not lotteries; methods as of 2018 | OOS |

### 2.4 Official library and statistical-method documentation

| ID | Source | Relevant content | Implication for this project |
|---|---|---|---|
| E11 | scikit-learn 1.9.1, [`LogisticRegression`](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) | `C` is inverse regularisation strength; regularisation applied by default; default solver `lbfgs`, `max_iter=100`. **`penalty` deprecated in 1.8, removed in 1.10; use `l1_ratio` and `C`** | The Phase 5 spec's `penalty='l2'` must be revised (omit `penalty`; L2 is the default with `l1_ratio=0`) and the scikit-learn version pinned |
| E12 | scikit-learn 1.9.1, [`HistGradientBoostingClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html) | Defaults `max_leaf_nodes=31`, `learning_rate=0.1`, `min_samples_leaf=20`, `l2_regularization=0`; `early_stopping='auto'` enables when n > 10,000; "much faster" than `GradientBoostingClassifier` for n ≥ 10,000 | Pooled training rows (draws × 47) exceed 10,000 once more than ~213 training draws accumulate, so the spec's explicit `early_stopping=False` is necessary for deterministic, holdout-free fitting |
| E13 | scikit-learn, [Probability calibration guide](https://scikit-learn.org/stable/modules/calibration.html) | Calibrator should be fit on data independent of the training data; isotonic "more prone to overfitting, especially on small datasets"; isotonic ≥ sigmoid only with "greater than ~ 1000 samples"; Brier/log loss mix calibration with resolution | Keep "no calibration" in version 1; if added, sigmoid only, fitted inside chronological training folds |
| E14 | scikit-learn 1.9.1, [`TimeSeriesSplit`](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) | Train on earlier, test on later; successive training sets are supersets (expanding); `max_train_size` caps window; `gap` excludes samples before test | Use as a reference pattern; the project's custom block folds (draw-indexed, regime-aware) remain necessary because each draw spans 47 rows |
| E15 | Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed., §5.10 — [online](https://otexts.com/fpp3/tscv.html) | "Evaluation on a rolling forecasting origin"; residual accuracy is optimistic compared with genuine forecasts | Supports per-target expanding refits and forbids in-sample accuracy claims |
| E16 | SciPy 1.18, [`scipy.stats.hypergeom`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html) | Parameterisation (M, n, N); pmf C(n,k)C(M−n,N−k)/C(M,N); `sf` "sometimes more accurate" than 1 − cdf | Used for section 5; matches exact rational computation |
| E17 | SciPy 1.18, [`scipy.stats.binomtest`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html); installed 1.18.1 docstring of `BinomTestResult.proportion_ci` | One-sided `alternative='greater'`; `proportion_ci(method='exact')` is Clopper-Pearson (default) | Primary interval implementable without new dependencies |
| E18 | Clopper & Pearson, "The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial", *Biometrika* 26(4), 404–413, 1934 — [OUP](https://academic.oup.com/biomet/article-lookup/doi/10.1093/biomet/26.4.404) | Bibliographic landing page only | Primary citation for the exact interval |
| E19 | statsmodels 0.15.0, [`multipletests`](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html) | `holm`: "step-down method using Bonferroni adjustments" | statsmodels is not a project dependency; Holm is a few lines to implement and test against this reference. Primary paper: Holm (1979), *Scand. J. Statist.* 6(2), 65–70 — the [JSTOR page](https://www.jstor.org/stable/4615733) did not render and an open scanned PDF was unreadable, so only its bibliographic details were confirmed (via search) |

Searches or fetches that failed: e3s-conferences.org paper (403), Medium articles (403), lotterydaily.com (403), IRIS UniGe (expired certificate; the same work was read on arXiv), CAUSEweb (certificate error; the JSE data file was read directly), JSTOR Holm (did not render).

## 3. Model comparison matrix

Rows describe what each family needs and risks for this problem: a few hundred to about a thousand draws, 47 binary inclusion labels per draw, and a null of exact uniformity. No family is preferred before evaluation.

| Family | Target representation | Sample-size needs | Calibration | Compute | Overfitting risk | Evidence for lotteries | Status |
|---|---|---|---|---|---|---|---|
| Uniform random (seeded) | Exact uniform over C(47,6) combinations | None (exact) | Exact by construction: Brier 0.1114, log loss 0.3819 per number (6/47) | Negligible | None | Correct model under fair draws (E1, E3) | Mandatory baseline |
| Smoothed historical frequency | Per-number marginal, (count + 6/47)/(history + 1) | Any; shrinks toward uniform | Near-uniform; mild over-dispersion early | Negligible | Low; one implicit choice (smoothing) | Equivalent to the "hot numbers" heuristic tested by fairness studies; no OOS gain shown | Mandatory baseline |
| Regularised pooled logistic (L2) | Per-number marginal from shared coefficients on ~15 history features | Hundreds of draws × 47 rows; few parameters, so stable | Generally reasonable; check with 10 bins | Seconds per refit; ~O(targets × configs) refits | Low–moderate; controlled by `C` grid | None found | Provisional candidate |
| Shallow boosting (HGB, 3–15 leaves) | Per-number marginal; interactions between history features | More than logistic; leaf minimum 47 rows constrains it | Can be over-confident; no calibration in v1 | Seconds–minutes per refit | Moderate; fixed small grid | None found | Provisional candidate |
| Neural/sequence (MLP, LSTM, transformer) | Usually a 47-way multi-label output per draw, or a sequence of sorted numbers (the latter wrongly imposes order on an unordered set) | Thousands of independent sequences or more; one series of a few hundred draws is far below that (E9 shows spurious test performance on random data at n ≤ 500) | Poor without held-out calibration data, which this sample cannot spare (E13) | GPU or long CPU runs; many hyperparameters, seeds and stopping rules (E10: "considerably greater") | High: many parameters, seed variance, implicit multiple testing through architecture search | None OOS; published items are satire (E7) or IS/unsupported (E8, blogs) | Research only; **not implemented** |
| Joint-combination models (e.g. Dirichlet-multinomial, E8; Plackett–Luce) | Distribution over sets | Joint structure needs far more data than marginals | Hard to verify (most combinations never observed) | Moderate | High | IS only | Not shortlisted |

## 4. Training-dataset suitability matrix

Facts are from `docs/phase2-coverage.md`, `docs/data-collection.md`, `docs/superpowers/specs/2026-10-09-expanded-collection.md` and E6/E20. Measured research-database coverage is currently **zero accepted dated draws**.

| Candidate | Permission | Dated coverage | Regime | Missingness | Provenance | Update availability | Suitability |
|---|---|---|---|---|---|---|---|
| External 527-draw export (described in `docs/data-collection.md`) | Assembled from independent archives whose terms prohibit harvesting; permission for reuse not documented | 9 Oct 2021 – 7 Oct 2026 per the description | 512 × 6/47, 15 × 6/45 | Described as complete for its window; unverifiable because **absent from the repository** | Cached pages and recovery JSON outside the repo; some caches were soft-error/CAPTCHA pages | None (one-off) | Not usable until recovered with provenance and permission; must not set sample sizes or split dates |
| Independent archives (irish.national-lottery.com, irishlottery.com) | Terms (s. 3.1.7 and equivalent) prohibit harvesting; hosts disabled for automated ingestion | Multi-year archives exist | Mixed regimes | Unknown | Third-party | Would require permission | Unsuitable without written permission |
| Operator (lottery.ie) | Personal reference permitted; extraction/integration needs permission | Recent results; historical depth unverified | Current 6/45 plus historical | Unknown | Authoritative | Yes, with permission | Preferred source if a permitted export or licence is obtained |
| PickMySix, author S3 JSON, CSV provider | 403 / account required; not obtained | — | — | — | — | — | Not available (no account created, no restriction bypassed) |
| Government open data (data.gov.ie) | CC BY 4.0 where present | No draw-result dataset found | — | — | — | — | Not available |
| JSE Boland & Pawitan (E6) | Teaching use with attribution; published reuse needs contributor consent | Period 24 Sep 1994 – 8 Mar 1997 only; **no per-draw dates** | 6/42 | Dates and bonuses absent | Fixed academic file, hashed locally | None | Cannot train chronological forecasts; usable only for fairness/null sanity checks |
| RNL annual metrics, C&AG chapter 19 | Attributed personal copy; CC BY 4.0 (catalogue) | Annual, all games | — | Not draw-level | Official | Annual | Not model inputs |
| Other lotteries (e.g. Canada 6/49, Romania 6/49, Melate; E1–E3) | Not reviewed; not acquired | Long histories reported in literature | Different pools and machines | Unknown | Varies | Varies | Only as a separately justified transfer/fairness experiment; never pooled into the primary sample |
| Prospective 6/45 draws (from 5 Sep 2026) | Permitted ingestion route still required | ~3 draws/week (≈156/year) | 6/45 | Accrues prospectively | Operator | Yes | The only route to confirmation; years of accrual needed (section 5) |

**Recommendation:** use the longest **verified single-regime** dated history (expected to be 6/47 Lotto), with its start date established from dated rule evidence rather than inferred from number appearances. Do not assume five years. The 6/47 start date is not verified in this repository.

## 5. Statistical power and achievable precision

### 5.1 Exact null probabilities (one fixed line, hypergeometric)

P(K = k) = C(6,k)·C(N−6,6−k)/C(N,6); exact rationals and `scipy.stats.hypergeom.sf` agree.

| Pool | P(≥3) exact | ≈ | 1 in | P(≥5) exact | ≈ | 1 in |
|---|---|---|---|---|---|---|
| 47 | 75,249 / 3,579,191 | 0.021024 | 47.56 | 247 / 10,737,573 | 2.300×10⁻⁵ | 43,472 |
| 45 | 6,471 / 271,502 | 0.023834 | 41.96 | 47 / 1,629,012 | 2.885×10⁻⁵ | 34,660 |

Uniform 5- and 10-line portfolios (distinct lines, 200,000 simulated draws, pool 47): any-line ≥3 rates 0.102 and 0.192, close to 1 − (1 − p0)^b; any-line ≥5 ≈ 1.2×10⁻⁴ and 2.3×10⁻⁴.

### 5.2 Minimum detectable improvement, ≥3 matches, one line per draw

Exact one-sided binomial test of H0: p = p0, α = 0.05, power 0.80. "c" is the smallest hit count with P(X ≥ c | p0) ≤ 0.05. The last two columns use the Phase 4 rule (two-sided 95% Clopper-Pearson lower bound > p0, effectively one-sided α = 0.025).

**Pool 47 (p0 = 0.02102)**

| Holdout draws n | Expected uniform hits | c | Actual α | MDE rate p1 | Absolute gain | Relative | CP rule: c | CP rule: p1 (relative) |
|---|---|---|---|---|---|---|---|---|
| 57 (= ceil(0.2 × 282)) | 1.20 | 4 | 0.032 | 0.0946 | +0.074 | 4.50× | 5 | 0.115 (5.47×) |
| 103 (= ceil(0.2 × 512)) | 2.17 | 6 | 0.022 | 0.0757 | +0.055 | 3.60× | 6 | 0.076 (3.60×) |
| 105 | 2.21 | 6 | 0.024 | 0.0743 | +0.053 | 3.53× | 6 | 0.074 (3.53×) |
| 500 | 10.5 | 17 | 0.038 | 0.0405 | +0.020 | 1.93× | 18 | 0.043 (2.03×) |
| 1,000 | 21.0 | 30 | 0.036 | 0.0344 | +0.013 | 1.64× | 31 | 0.036 (1.69×) |
| 4,000 | 84.1 | 100 | 0.048 | 0.0270 | +0.006 | 1.29× | 103 | 0.028 (1.32×) |
| 10,000 | 210 | 235 | 0.047 | 0.0248 | +0.004 | 1.18× | 240 | 0.025 (1.20×) |

**Pool 45 (p0 = 0.02383):** n = 57 → p1 0.0946 (3.97×); 105 → 0.0743 (3.12×); 500 → 0.0449 (1.88×); 1,000 → 0.0376 (1.58×); 4,000 → 0.0302 (1.27×).

Draws needed for given relative lifts (normal approximation, same α and power): pool 47 — 1.05× ≈ 117,000; 1.10× ≈ 29,700; 1.20× ≈ 7,700; 1.50× ≈ 1,300. Pool 45 — 1.10× ≈ 26,100; 1.20× ≈ 6,700. At ~156 current-regime draws a year, 1,000 prospective draws take about 6.4 years and 4,000 about 26 years.

### 5.3 What a "realistic" improvement looks like

Under a hypothetical, perfectly known physical bias in which six specific balls are each *w* times as likely to be drawn as the others (Wallenius non-central hypergeometric model, pool 47), and the line is exactly those six balls:

| w | Marginal inclusion (fair 0.1277) | P(≥3) | Lift |
|---|---|---|---|
| 1.05 | 0.133 | 0.0237 | 1.12× |
| 1.10 | 0.138 | 0.0264 | 1.26× |
| 1.20 | 0.148 | 0.0324 | 1.54× |
| 1.50 | 0.176 | 0.0537 | 2.55× |
| 2.00 | 0.218 | 0.0979 | 4.66× |

The 57-draw holdout detects only the equivalent of every chosen ball being about **twice** as likely as the rest. That is an *oracle* figure: a real model must also estimate which balls are favoured from the same small history. Biases of that size would be obvious in frequency tests of the kind in E1–E3, which in long histories find none. Realistic advantages, if any, are at most a few per cent and cannot be detected by any historical Irish sample.

### 5.4 Secondary outcomes and more sensitive statistics

- **≥5 matches:** expected uniform events are 0.0013 (n = 57), 0.0024 (105), 0.012 (500), 0.023 (1,000) and 0.092 (4,000). A single event at n ≤ 1,000 is "significant" only for p1 ≥ 70× p0. Report counts and exact intervals only; the outcome is **effectively unmeasurable** and must not drive selection.
- **Mean matches** (null mean 36/47 = 0.766, SD 0.772) uses every draw and is more sensitive to marginal bias. Normal-approximation MDE: +0.254 at n = 57 (oracle w ≈ 1.43), +0.189 at 103, +0.086 at 500, +0.061 at 1,000 and +0.030 at 4,000 (w ≈ 1.05). It is still far from detecting realistic effects, but is a better development selection statistic than sparse 3+ counts.
- **Precision obtainable:** if a 103-draw holdout shows the uniform-expected 2 hits, the 95% Clopper-Pearson upper bound is 0.068 (3.25× p0); with 1,000 draws and 21 hits it is 0.032 (1.52×). The historical study can therefore *exclude large advantages*, but cannot show the absence of small ones.
- **Development folds:** with 282 draws the common validation period is indices 175–225, i.e. 50 targets with about **1.05 expected 3+ hits**. Choosing among six configurations by pooled 3+ rate is then almost entirely noise; ties fall through to Brier and log loss. With 512 draws there are 234 validation targets (~4.9 expected hits).

**Key finding:** the provisional 282-draw minimum and 20% holdout let the software run but **cannot detect any realistic improvement**. Any plausible verified 6/47 history (hundreds to low thousands of draws) leaves the primary test able to detect only lifts of roughly 1.6× to 4.5×. A "no demonstrated advantage" result will be uninformative about small effects and must be reported as bounded, not as equality.

## 6. Target definition and line construction

- **Target.** Each draw is an unordered set of six distinct main numbers from the effective pool (bonus excluded). Under the fair-draw null the joint law is uniform over C(N,6) sets and every line has exactly the same P(≥k) (section 5.1).
- **Marginal encoding (recommended for v1).** 47 binary labels per draw, number_in_draw[t,j], predicted as p_j. The labels are dependent (they always sum to 6), so the p_j do not define a joint distribution. Rows from one draw are one evaluation unit; resample and test at draw level.
- **Joint encodings (not recommended for v1).** A distribution over sets (Dirichlet-multinomial, Plackett–Luce, Wallenius-type weighted urn) needs many more parameters and data. Sequence encodings of sorted numbers impose a false order on the set.
- **Line construction for ≥3 matches.** Top-6 marginal maximises the expected number of matches Σ p_j over the line, not necessarily P(≥3). Under a weighted-urn (Wallenius) model with weights monotone in p_j, top-6 does also maximise P(≥3), because raising any line member's weight increases its stochastic inclusion. That is an assumption, not a fact: it fails if the model implies negative co-occurrence among top numbers. Alternatives — sampling lines from a fitted joint model, Monte Carlo estimation of P(≥3) for candidate lines under a stated joint model, or diversified portfolios — require an explicit, tested joint assumption. With the available power none of these can be distinguished empirically, so v1 keeps top-6 with ascending-number ties as primary and treats other constructions as secondary.
- **Portfolios.** Diversification (low overlap) raises the any-line ≥3 rate at a fixed budget only through reduced overlap; it never raises single-line odds. Compare at identical budgets only.

## 7. Recommended training and evaluation protocol (provisional)

1. **Population.** Longest verified single-regime dated history from the Phase 3 snapshot. No pooling of 6/42, 6/45, other lotteries or undated rows. Replace the 282-draw *execution* minimum with an explicit power statement in `protocol.json` (MDE at the realised holdout size) and label the study "screening/bounded-effect" when the holdout MDE exceeds 2× p0.
2. **Chronology.** Keep a final 20% locked holdout and expanding windows (E14, E15) refitted per target. A rolling window (cap, e.g. 300 draws) may be a pre-declared secondary sensitivity check; under stationarity it only reduces data. Same-regime lag pairs only; gap flags preserved.
3. **Features.** Keep the frozen Phase 5 history-only feature set (windows 10/25/50/100, recency, lags, smoothed frequency, weekday, elapsed days). External features only with documented pre-draw availability. No pair/triple searches.
4. **Candidates and budget.** Uniform, smoothed frequency, logistic `C ∈ {0.01, 0.1, 1.0}` (L2 via defaults; drop the deprecated `penalty` argument, E11), HGB `max_leaf_nodes ∈ {3, 7, 15}` with `early_stopping=False`. Six configurations total; no further search. Compute cost: for 512 draws, about 337 targets × 6 configurations ≈ 2,000 small refits in development plus holdout refits — CPU minutes. The 10,000 null-history refits of the selected pipeline dominate (on the order of 10⁶ refits) and need checkpointed batching; benchmark one replicate before freezing.
5. **Preprocessing/calibration.** Scaling fitted on training rows only; no calibration in v1 (E13). If calibration is later justified, sigmoid only, inside chronological training folds.
6. **Selection.** Because 3+ events are too sparse in development (section 5.4), consider revising the selection order to pooled draw-level log loss, then Brier, then mean matches, then development 3+ rate. Uniform is the selection reference: if no candidate beats uniform log loss in development, record that and still run the frozen primary for completeness. This is a proposed revision for review, not yet adopted.
7. **Primary inference.** Unchanged: holdout one-line 3+ rate vs exact p0; 95% Clopper-Pearson interval (E17, E18); one-sided null-history Monte Carlo p with 10,000 replicates. Also report the upper bound as "largest improvement not excluded".
8. **Secondary and multiplicity.** Holm (E19) across one family: mean matches, ≥5, 5/10-line portfolios, frequency-vs-model contrasts. ≥5 is descriptive.
9. **Leakage checks.** Future-row perturbation invariance, `max_input_date < target_date`, training-only scaling, cross-regime lag rejection, and identical target dates and budgets for every policy.
10. **Decision language.** "Promising" only with a positive primary improvement, CP interval excluding zero, null p ≤ 0.05 and no validation failures; still pending prospective confirmation. Otherwise "no demonstrated advantage; improvements above X× excluded at 95%".

## 8. Development benchmark plan (reproducible)

| Step | Content | Pass criterion |
|---|---|---|
| B0 Synthetic null | Generate ≥ 1,000 uniform 6/47 histories of the realised length (seeded per the Phase 4 scheme); run every policy | Mean 3+ rate within Monte Carlo tolerance of p0; model log loss not better than uniform beyond noise; false "promising" rate ≈ nominal α |
| B1 Synthetic planted bias | Same, with six balls weighted w ∈ {1.1, 1.5, 2.0} | Detection rates match section 5 power within simulation error; confirms the pipeline can find real signal |
| B2 Real development folds | Frozen snapshot, folds from index 175, six configurations | Report log loss, Brier, calibration bins, mean matches, 3+ counts with denominators; select per item 7.6 |
| B3 Compute budget | Time one development pass and one null-history replicate | Projected 10,000-replicate cost recorded before freeze |
| B4 Freeze | Persist protocol, snapshot and lock hashes | Holdout untouched |

Seeds, environment lock, configuration JSON and outputs are stored under the protocol digest, as in the Phase 4 spec.

## 9. Decision record

| Decision | Status | Rationale | Expected cost | Remaining uncertainty |
|---|---|---|---|---|
| Uniform + smoothed-frequency baselines | Selected | Exact null and the natural "hot number" heuristic (E1–E3) | Negligible | None material |
| Regularised logistic (3 configs) | Selected, provisional | Low variance, interpretable, cheap; adequate for marginal targets | Minutes of CPU | API change (E11) needs a code/spec edit |
| Shallow HGB (3 configs) | Selected, provisional | Tests non-linear history interactions with tight capacity | Minutes of CPU | Possible over-confidence; calibration deferred |
| Neural/sequence models (MLP, LSTM, transformer) | **Rejected for implementation** | No OOS evidence (E7, E8, search outcome); data are one short series; spurious-performance risk at n ≤ 500 (E9); weaker and costlier than statistical methods on short series (E10); large implicit search space | Would need GPU-days and much larger tuning budgets | Revisit only if (a) a simple model shows a confirmed prospective advantage and (b) a verified dataset of thousands of same-regime draws exists |
| Joint-set models (CDM, Plackett–Luce) | Rejected for v1 | IS-only evidence (E8); unverifiable with available data | Moderate | Could be a future secondary construction study |
| Transfer from other lotteries/regimes | Deferred | Different machines, pools, and permissions not reviewed | Acquisition effort | Requires its own protocol |
| Training population | Longest verified single-regime history; size unknown | Phase 2 coverage is zero dated draws | — | Actual n determines every MDE above |
| 282-draw minimum, 20% holdout | Retain as execution floor only; add explicit power reporting | Section 5: cannot detect realistic improvement | — | Reviewer decision on "screening" framing |
| Selection criterion | Proposed change to log loss first | 3+ events too sparse in development | — | Needs review before freeze |

**Overall expectation:** the most likely outcome is "no demonstrated advantage" with wide bounds. The historical study is still worth running for leakage-safe infrastructure and to exclude large effects, but it cannot validate a small edge. Only a long prospective 6/45 record could narrow the bounds, over years rather than months.

## Appendix A — power computation (reproducible)

```python
from fractions import Fraction
from math import comb
from scipy.stats import binom, hypergeom


def p_at_least(pool: int, k: int) -> Fraction:
    return sum(
        Fraction(comb(6, i) * comb(pool - 6, 6 - i), comb(pool, 6)) for i in range(k, 7)
    )


def mde(
    n: int, p0: float, alpha: float = 0.05, power: float = 0.8
) -> tuple[int, float]:
    c = next(c for c in range(n + 2) if binom.sf(c - 1, n, p0) <= alpha)
    lo, hi = p0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if binom.sf(c - 1, n, mid) >= power else (mid, hi)
    return c, hi


p0 = float(p_at_least(47, 3))  # 0.0210242...
assert abs(p0 - hypergeom.sf(2, 47, 6, 6)) < 1e-12
for n in (57, 103, 105, 500, 1000, 4000):
    print(n, mde(n, p0))
```

The Wallenius lifts in section 5.3 use `scipy.stats.nchypergeom_wallenius(47, 6, 6, w).sf(2)`; the Clopper-Pearson rule uses `scipy.stats.beta.ppf(0.025, x, n - x + 1) > p0`.
