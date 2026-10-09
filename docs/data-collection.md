# Data collection and preparation

This document records how the Irish Lotto dataset used for the initial analysis was assembled. It describes the actual collection workflow, including manual/web-assisted recovery, rather than claiming a fully automated operator feed.

## Scope and snapshot

Collected on 8 October 2026. The requested five-year window was 8 October 2021–7 October 2026 inclusive; the first actual draw was 9 October 2021.

- 527 main Lotto draws, exported newest first.
- Six main winning numbers and one bonus per draw.
- Eight prize tiers per draw: 4,216 prize records.
- 512 draws under 6/47 and 15 under 6/45.
- Lotto Plus 1, Lotto Plus 2 and raffles were excluded.
- Winner counts describe winning entries, not necessarily distinct people.

The work started with a 90-day extract. It was split into a draw table and a prize table to avoid repeating the winning numbers for each tier, then expanded to five years. The original 90-day values were compared with the corresponding expanded records.

## Sources

| Source | Use | Authority |
|---|---|---|
| [Irish National Lottery results archive](https://irish.national-lottery.com/irish-lotto/results-archive-2026) | Annual draw dates, numbers, full jackpot amounts and Won/Roll outcomes; individual draw prize breakdowns | Independent results publisher |
| [IrishLottery.com](https://www.irishlottery.com/) | Alternative historical draw and prize-breakdown pages | Independent results publisher |
| [National Lottery](https://www.lottery.ie/) | Recent-result cross-checks, game information and published winner stories | Operator |
| [September 2026 change announcement](https://www.lottery.ie/news/press-releases/change-is-coming) | 6/45 start and Monday draw introduction | Operator |
| [October 2024 6/47 rules PDF](https://cdn1.lottery.ie/uploads/Issue_9_RULES_LOTTO_6_OF_47_OCT_2024_29_10_de7a5bf535.pdf) | Historical prize-type and rules reference | Operator |
| [2025 winner roundup](https://www.lottery.ie/news/winners-stories/2025-the-year-of-our-biggest-national-lottery-win-ever-and-more) | Public jackpot ticket locations for 2025 | Operator |

The collection did not use an official bulk API. Most historical results came from independent archives, not an exhaustive operator audit. Operator rules PDFs are references for their published periods; the October 2024 PDF does not prove every clause applied throughout the entire five-year window.

## Collection steps

1. Retrieve and cache yearly archive pages for 2021–2026.
2. Extract individual draw dates from result links, restrict them to the requested window, deduplicate and sort descending.
3. Retrieve individual result pages and extract the six mains, bonus and main Lotto prize table.
4. Read each prize tier's published prize text and winner count.
5. Recover missing/inaccessible records through alternative result pages and web-search/open results.
6. Merge the recovered structured records with directly parsed pages.
7. Export the two core tables and run coverage and consistency checks.

Primary URL patterns were:
- Annual archive: `https://irish.national-lottery.com/irish-lotto/results-archive-YYYY`
- Individual draw: `https://irish.national-lottery.com/irish-lotto/results-DD-MM-YYYY`
- Alternative draw: `https://www.irishlottery.com/results/irish-lotto-result-DD-MM-YYYY`

### Access problems and recovery

Direct bulk requests encountered HTTP 403 responses. Some cached responses were soft-error or CAPTCHA pages rather than draw results. These must not be accepted merely because a file exists or an HTTP request returned content.

The collection switched to web-assisted retrieval and an alternative publisher to complete missing records. Recovered records were stored as structured JSON and then consumed by the collector. No CAPTCHA-solving workflow is part of the reproducible pipeline.

The original collector depends on this recovered JSON and cached pages. It is not a self-contained fresh download command. A future production pipeline must implement explicit page validation, source fallbacks, retry/backoff and provenance for every retrieval.

## Extraction and normalisation

Dates were converted to ISO `YYYY-MM-DD`. Numbers were exported as six sorted main values plus a separately named bonus; their positions are sorted ranks, not physical draw order.

HTML entities and tags were removed from table text. Euro amounts and winner counts had grouping commas removed before numeric conversion. Tier labels were standardised, for example `Match 5 plus Bonus` to `Match 5 + Bonus`. Original prize text was retained in `prize_as_published`.

The published per-winner prize was preserved even when the winner count was zero. A displayed prize with zero winners is not an amount actually awarded.

Historical Match 2 + Bonus prizes required a clarification after reviewing the operator rules: the face value can represent a Quick Pick ticket or cash alternative. The initial collector note describing retail versus online redemption was too narrow and was corrected during enrichment. The actual cash-versus-ticket redemption mix is unknown.

## Core tables

| File | Grain / key | Contents |
|---|---|---|
| `irish_lotto_draws_5_years.csv` | One row per `draw_date` | Main numbers, bonus, source URL and enriched draw-level fields |
| `irish_lotto_prizes_5_years.csv` | One row per `(draw_date, prize_tier)` | Winning entries, prize per entry, original published text, prize type and derived tier values |

Join on `draw_date`. Do not sum draw-level jackpot amounts after expanding the draw table into its eight tier rows.

CSV format: UTF-8 with BOM; ISO dates; EUR monetary values; blanks for unknown/not applicable values. The first collector used floating-point values for parsed published amounts; enrichment used decimal arithmetic for monetary totals. Published whole-euro amounts are not a guarantee of audited payment precision.

## Enrichment

### Jackpot and rollover context

The yearly archives supplied the full available jackpot and Won/Roll outcome. On shared jackpots the pool is distinct from the amount per winning entry.

Chronological processing calculated consecutive no-jackpot-win draws before and after each draw, the strictly preceding jackpot-win date, days since that win and jackpot change from the previous draw. Earlier 2021 archive rows were used as context so the first exported draw's existing rollover streak was not incorrectly reset to zero. Context rows did not extend the exported coverage.

A rollover counter is based on whether the jackpot was won. It does not imply that the available jackpot increased at every draw; caps and reserve rules can affect amounts.

### Prize values

- Tier face value = winner count × published prize per winning entry.
- Zero winners produce zero awarded face value.
- Draw face value = sum of the eight tier face values.
- Cash-only-tier value excludes the historical mixed Quick Pick/cash tier.
- The mixed tier's actual cash value is left unknown when there are winners.

The separately exported prize-fund table contains these calculated published values. It is not the operator's allocated prize fund, ticket-sales revenue or an audited cash-payout ledger.

### Rules and calendar

Rule intervals represent the observed number pool and draw schedule:
- 6/47, Wednesday/Saturday through 4 September 2026.
- 6/45 starts 5 September 2026.
- Monday/Wednesday/Saturday starts 7 September 2026.

The calendar contains all 1,825 days between the first and last exported draws, including days with no draw. It includes calendar/ISO periods and scheduled/observed draw flags. Public holidays were not added.

### Winning-ticket metadata

Operator winner stories and published roundups supplied public retailer/town/county or reported online-player county. The table contains 49 jackpot-winning entries across 46 winning draws; public locations were verified for 16 entries. Remaining metadata is blank and marked not verified, not a claim that no public source exists.

Retail county means purchase location; online county means the player's county as reported. The per-draw entry index is synthetic, not an official ticket identifier. Private identities were not collected.

### Descriptive number features

Main-number sum, odd count, adjacent consecutive pairs and overlap with the previous draw were calculated from the exported numbers. These are descriptive post-draw fields. For model training, target-draw features must not be used as pre-draw predictors; lag/rolling features must be rebuilt with strict historical cutoffs.

## Related exports

- `irish_lotto_game_rules.csv`
- `irish_lotto_jackpot_winning_tickets.csv`
- `irish_lotto_prize_fund_5_years.csv`
- `irish_lotto_calendar_5_years.csv`
- `irish_lotto_number_features_5_years.csv`
- `irish_lotto_dataset_README.md`

These names refer to the delivered dataset files; this document does not imply they or the original collection scripts have been committed to this repository.

## Validation performed

- 527 unique draw dates and all expected scheduled draws in the selected window.
- Eight distinct main Lotto prize tiers per draw; no duplicate draw/tier keys.
- Seven distinct eligible numbers per draw, including the bonus.
- Rule-pool and weekday compatibility.
- Jackpot Won/Roll outcome agrees with Match 6 winner counts.
- On winning dates, the full jackpot agrees with winner count × per-entry jackpot amount, allowing whole-euro rounding.
- Original dates, numbers, winner counts and per-entry amounts preserved during enrichment.
- Original 90-day extract agrees with the corresponding expanded records.
- Tier face values reconcile with draw totals.
- Calendar draw flags reconcile with the draw table.
- Export ordering remains descending by date.

These establish internal consistency and coverage, not exhaustive independent verification of every source fact.

## Provenance and reproducibility limits

Per-record source URLs identify the result pages; jackpot context has its own archive URL. Filled ticket metadata has operator source URLs. `retrieved_on` describes the collection/enrichment date and does not assert that every historical record was audited against the operator that day.

Working collection artefacts were:
- `collect_lotto.py`: cached HTML and recovered structured data to core CSVs.
- `lotto_cache/`: annual/individual pages and recovery JSON.
- `enrich_lotto.py`: rules, jackpots, rollovers, prize semantics and ticket metadata.
- `add_related_tables.py`: calendar, prize-value and number-feature exports.

The source sites can change, block automated requests or remove pages. The recovery JSON and cached evidence are required to faithfully reproduce this exact snapshot. The original scripts include workspace-specific paths and require refactoring before becoming a repository pipeline.

A production ingestion phase should add a source manifest with retrieval timestamps, hashes and source classification; validate every response before caching; reconcile overlapping sources; preserve disagreements; emit deterministic CSVs; and retain enough evidence to rebuild the snapshot. Fetch only new/missing records using reasonable rate limits rather than repeatedly scraping the entire history.

No missing winner counts or prizes were filled using estimates. Per-draw ticket sales, player number selections, comprehensive claim dates and the actual mixed-prize cash redemption breakdown were not established and remain unavailable.
