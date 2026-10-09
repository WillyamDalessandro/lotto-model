# Complementary data catalogue

Date: 9 October 2026. Status: proposed phase 2 extension, not collected. This catalogue extends the historical draw pipeline; it does not claim any of these datasets exist locally.

## Required lottery context

| Dataset | Grain and fields | Source and collection | Acceptance and use |
|---|---|---|---|
| Prize breakdowns | One draw/tier: winners, published prize, currency, original text, cash/ticket/mixed prize semantics | Draw detail pages; operator overlap checks | Preserve unknowns; do not assume eight tiers across all history; post-draw descriptive only |
| Jackpot context | One draw: available pool, published Won/Roll outcome, cap/must-win status when explicitly documented | Annual archives, dated operator notices and result pages | Pool differs from per-winner prize; unknown outcome stays null |
| Rollover history | One draw: prior streak, prior known jackpot-win date, elapsed days, prior available pool, pool change | Derived chronologically from validated jackpot observations | Require sufficient preceding context; gaps or unknown outcomes make dependent fields unknown |
| Rules and prices | One game/effective interval: pool, main/bonus counts, tiers, ticket price, minimum purchase, schedules, claim window, cap and allocation rules | Operator rules PDFs, dated change announcements and regulator records | Evidence-backed intervals; a recent rule PDF does not establish older rules |
| Calendar and exceptions | One civil date and dated exception events: ISO week/year, weekday, scheduled/observed draw flags, elapsed days, reschedules/cancellations | Derived from verified rules and operator/regulator exception notices | Generate dates with no draw too; unknown schedules stay unknown |
| Public winning-ticket context | One reported entry/event: draw, synthetic entry key, channel, retailer, town/county, location meaning, claim/publication date when explicitly reported | Operator winner stories and annual roundups | No personal identities; unknown channel/location stays null; partial public coverage only |
| Prize-value summaries | One draw/currency: tier face values, total face value, cash-only-tier subtotal, unresolved mixed-prize amount | Derived from validated prizes and winner counts | A derived published-value total is not operator allocated fund, ticket sales or audited payout |
| Historical number descriptors | One draw: sum, odd count, adjacent pairs, previous-draw overlap | Derived from accepted numbers | Descriptive post-draw fields; model predictors require separately rebuilt strictly lagged values |
| Official aggregate context | One report/period/game scope: published sales, prizes, participation and channel totals, where disclosed | Operator and regulator annual reports | Preserve annual/game/all-games scope; never allocate annual totals to individual draws |
| Provenance and availability | One dataset/source/period or field: source URL, hash, retrieval/publication time, authority, coverage, conflict and missingness reason | Shared evidence manifest and coverage queries | Distinguish not published, inaccessible, not yet collected, invalid and conflicted |

Prize details, jackpot context, rules and calendar are mandatory ingestion deliverables. Public ticket metadata and official aggregate reports are best-effort acquisitions within the same phase, with discovered/published coverage reported honestly. Derived summaries must not fill missing source facts.

## Candidate calendar enrichment

Irish public holidays are proposed as an additional date dimension, subject to the user's scope selection. Use [Workplace Relations Commission information](https://www.workplacerelations.ie/en/what_you_should_know/public-holidays/) and dated official notices. Do not apply today's holiday set retroactively: the [government notice](https://www.gov.ie/en/department-of-the-taoiseach/press-releases/government-agrees-covid-recognition-payment-and-new-public-holiday/) records a one-off holiday in March 2022 and a new recurring holiday from 2023. Distinguish the actual holiday date from a workplace substitute day. Do not infer historical holidays without evidence.

Weather, economic indicators, population and other external datasets are not yet committed scope. If selected, define their source, geographic grain, measurement period, release time and research hypothesis first. Observed draw-day weather or a revised economic series must not become a predictor that pretends it was available before the draw. More columns alone are not evidence of number predictability.

## Source inventory

- [Operator draw results](https://www.lottery.ie/draw-games/results/view?game=lotto&lang=en): recent numbers and prize tiers.
- [Historical annual archives](https://irish.national-lottery.com/irish-lotto/results-archive-2026): numbers, pools and outcomes; detail links for tiers.
- [Alternative detail publisher](https://www.irishlottery.com/results/irish-lotto-result-07-10-2026): complementary published prize text and fallback evidence; may share an upstream source with the archive.
- [Operator change announcement](https://www.lottery.ie/news/press-releases/change-is-coming): dated 2026 pool/schedule/price changes.
- [Operator annual reports](https://www.lottery.ie/about/annual-reports): inventory report links and actual disclosed aggregates before committing metric coverage.
- [2025 operator winner roundup](https://www.lottery.ie/news/winners-stories/2025-the-year-of-our-biggest-national-lottery-win-ever-and-more): public winning-ticket locations; discover linked stories for evidence, without treating a roundup as a comprehensive register.
- [Regulator 2015 report](https://www.rnl.ie/assets/PDFs/annual-reports/Annual-Report-2015-English.pdf): game changes, official aggregate context and historical operational exceptions.

These pages were checked during planning. Specific report tables, historical rules, location rows and metric coverage have not yet been extracted or audited.

## Storage and time semantics

Add dedicated relations rather than duplicating draw-level values across prize rows:

- `draw_context`: one draw with accepted pool/outcome and field-level observation references.
- `rule_attributes`: effective-dated prices, caps, tier/prize semantics and supporting evidence, linked to rule regimes.
- `calendar_dates` and `calendar_events`: dates, verified schedule flags and documented exceptions; optional official holidays.
- `winning_ticket_reports`: reported ticket/channel/location events, each with evidence and publication time. Distinguish retail purchase county from reported online-player county. Story mentions are not inherently unique winning entries; deduplicate overlapping stories without inventing ticket identifiers.
- `official_period_metrics`: report, metric, period, game scope, unit/currency, published value and publication date; never join as if draw-grain data.
- Derived views/exports for rollover, prize values and number descriptors, with input snapshot/configuration lineage. Snapshot management remains phase 3.

Currency is explicit. Historical Irish-pound monetary observations must not enter EUR fields without a separately defined conversion methodology. Original amount, symbol and text are always retained; ambiguous symbols remain unresolved.

Store `published_at`, `retrieved_at`, `effective_from/to` and event date separately where applicable. If the actual publication time is unknown, mark it unknown: a retrieval timestamp does not establish historical pre-draw availability. Advertised pre-draw jackpots may be used prospectively only when saved before the draw; retrospectively sourced final pools are descriptive by default.

## Quality and reporting

Reconcile available pool versus winning jackpot shares with explicit rounding tolerance; exclude zero-winner published prize amounts from awarded-value totals. Verify tier totals without duplicating draw-level context after joins. Compute prior rollover context only across known outcomes, and do not reset an incomplete series to zero. Test shared jackpots, missing tiers, mixed-prize winners, currency changes and unknown previous outcomes.

Coverage output must list every catalogue dataset even when empty: earliest/latest period, eligible population, populated-field counts, percentage with evidence, missing/conflicted counts and why fields are absent. Public-location coverage is relative to known winning entries only when the source establishes an entry count; otherwise report it by draw/event. Prize tier completeness uses the effective rules, not a blanket eight-tier requirement.

Examples of unavailable data that must remain explicitly unavailable unless a verifiable publication is found: individual player number selections, per-draw ticket sales, actual cash-versus-ticket redemption mix, comprehensive claim dates, private player identities, and physical machine/ball-set or draw-order metadata not published by a source.

Collection is broader than prediction: winner locations, claims, payout summaries and target-draw descriptors describe outcomes. Keep them available for audit and reporting, but prohibit them as same-draw predictors. Model design remains a separate phase with explicit feature cutoffs and evidence-backed hypotheses.
