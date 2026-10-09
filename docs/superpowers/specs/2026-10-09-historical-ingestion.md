# Phase 2: historical collection and ingestion

Date: 9 October 2026. Status: expanded spec approved; [implementation plan](../plans/2026-10-09-historical-ingestion.md) prepared for review. No bulk collection or ingestion has run.

## Goal

Gather the longest accessible public Irish main Lotto history and complementary lottery context, preserve reproducible source evidence, and incrementally ingest validated draws into the existing local PostgreSQL database. Preserve incomplete older history as observations rather than inventing missing values. Training and a frozen research dataset belong to later phases.

## Complementary data scope

The [complementary data catalogue](../../complementary-data.md) is part of this spec. Required context includes published prize breakdowns, jackpot pools/outcomes, evidence-backed rules/prices and full calendar/schedule exceptions. Add chronological rollover context, prize-value summaries and descriptive number features as derived outputs with lineage. Public winning-ticket locations/channels and official period-level sales/prize/participation metrics are best-effort source acquisitions; report availability instead of inventing missing observations. Holidays and external weather/economic datasets remain outside this implementation; their optional scope question was not answered explicitly.

Use separate relations for ticket reports, effective rule attributes, calendar events and official period metrics. Capture source publication time separately from retrieval and effective dates. Preserve every original currency, prize type and location meaning. Do not confuse post-draw context with pre-draw predictors or annual aggregates with per-draw values.

## Source probe

Seven direct requests were made on 9 October using a declared research user agent. Response bodies and SHA-256 hashes are stored locally in ignored data/raw/phase2-probe; manifest.json records URL, UTC retrieval time, status and content type. This small probe establishes accessibility, not complete historical coverage or guaranteed future access.

| Source | Observed access | Proposed role |
|---|---|---|
| [Operator results](https://www.lottery.ie/draw-games/results/view?game=lotto&lang=en) | HTTP 200, HTML with recent results | Authoritative overlap check and incremental recent results |
| [Independent 2026 archive](https://irish.national-lottery.com/irish-lotto/results-archive-2026) | HTTP 200; 85 distinct linked draw dates, 3 January–7 October | Bulk draw numbers and jackpot context from annual pages |
| [Independent 1988 archive](https://irish.national-lottery.com/irish-lotto/results-archive-1988) | HTTP 200; 38 distinct linked draw dates, 16 April–31 December | Historical discovery and archived observations |
| [Alternative publisher](https://www.irishlottery.com/results/irish-lotto-result-07-10-2026) | HTTP 200 | Draw-detail fallback and comparison |

The archive advertises annual links for 1988–2026; intermediate years still need acquisition and validation. Advertised coverage is not imported coverage. The independent sites may share data or ownership: agreement between them must not be described as independent verification.

Both independent robots files return text disallowing /en/play/ and advertising sitemaps. The operator robots URL returned HTTP 200 HTML for a not-found application page, not valid robots directives. Record that ambiguity and check published access terms before automated collection; a malformed robots response is not evidence of permission. Do not visit play/account/checkout routes.

The [16 April 1988 detail](https://irish.national-lottery.com/irish-lotto/results-16-04-1988) shows six mains without a bonus, pound-denominated prize text, and dashes for winner counts. Preserve those distinctions. The site also includes generic modern boilerplate on this old page; extract dated result sections, not global footer statements.

The [operator change announcement](https://www.lottery.ie/news/press-releases/change-is-coming) supports 6/45 from 5 September 2026 and Monday draws from 7 September. The [regulator's 2015 report](https://www.rnl.ie/assets/PDFs/annual-reports/Annual-Report-2015-English.pdf) supports the September 2015 introduction of 6/47; exact historical boundaries and older rules require recorded evidence before canonical acceptance. Never derive the eligible pool from the largest observed number.

## Approach and alternatives

Recommended: collect annual pages first, then fetch draw details for prizes and gaps. This recovers numbers efficiently in tens of requests before thousands of enrichment requests. Cross-check the operator overlap after parsing; retain source disagreements.

A detail-page-only crawler gives rich records but multiplies requests before establishing basic coverage. Browser-first collection adds operating complexity while direct HTML currently works. Use HTTP adapters initially, with explicit manual evidence imports if access is blocked. Playwright public-result access remains a later phase unless a reviewed source-access need requires moving it forward.

## Scope and modules

Use httpx and Beautiful Soup with the existing Python stack. Source adapters discover links and parse their own documented HTML sections into source observations. A fetch/cache module enforces pacing and access policy, retains raw responses and writes manifests. An ingestion module owns transactional canonical writes and conflict handling. A coverage module reports what is actually present.

Commands:

- `lotto data discover`: inspect source availability, annual links and access-policy status without bulk collection.
- `lotto data collect --start-year 1988 --end-year 2026`: fetch allowed annual archives, persist parsed observations and ingest eligible records; checkpoint per URL.
- `lotto data enrich --start DATE --end DATE`: fetch missing prize/detail evidence for known dates with resumable limits. Dataset selection additionally supports rules, public ticket stories and official reports; scope and period are explicit per dataset.
- `lotto data import MANIFEST`: import saved source evidence offline, verify hashes, validate source identity and parse with the selected adapter.
- `lotto data report`: emit JSON coverage and discrepancy summaries, including accepted versus staged records.

Expose configurable request limits so the initial live run is bounded, followed by a resumable backfill. Defaults: one request at a time, at least two seconds between requests per host, 20-second timeout, at most three attempts on timeouts/5xx with increasing delay. Respect a longer published crawl delay and Retry-After. Stop a host on 401/403/CAPTCHA; persist the blocked status and continue only through an allowed fallback. No anti-bot bypass.

## Evidence, cache and resume

Raw bodies are immutable content-addressed files under data/raw. Retrieval events retain source, requested and final URL, UTC retrieval time, response status/type, body hash/path and ingestion-run ID. Validate pages semantically before calling them valid; HTTP 200 is insufficient. Manifests are versioned, portable and reference relative paths confined to the evidence directory. Hash mismatches, missing files and escaping paths fail before database writes.

Cache lookup keys source and normalised URL; verify cached bytes against their hash before reuse. Historical valid URLs are reused by default, and the current annual page refreshes on an explicit incremental run to discover new draws. An explicit refresh retains new evidence and old observations. Blocked/invalid cached pages never count as successful checkpoints.

Persist checkpoints and errors in PostgreSQL so an interrupted run can resume. No duplicate canonical draws, numbers or prizes on repeated runs. Successful observations are deduplicated by artifact, parser version and source draw identity; a changed body creates new evidence. Run counters distinguish fetched, cached, accepted, staged, conflicted, blocked and failed records. Close run status correctly on failures; retain completed work.

## Parsing and historical compatibility

Parse main Lotto separately from Plus games, advertisements and aggregate totals. Each observation includes ISO draw date, six mains when present, nullable bonus, original source text and link, optional jackpot/outcome and optional prize tiers. Numbers are unordered sets; do not infer physical order from sorted display.

Convert grouped integers and monetary decimals explicitly; retain original prize text and currency. Dashes and absent cells mean unknown, never zero. Preserve historical pound values with an explicit currency label whose interpretation is documented; do not write them into prize_eur or assume an exchange rate. Missing prizes or winners do not reject otherwise valid numbers.

Extend storage with draw_context, quality_issues, fetch_checkpoints and a portable retrieval-manifest mapping, plus rule_attributes, calendar_dates/events, winning_ticket_reports and official_period_metrics as defined in the catalogue. Add typed observation contracts that allow missing bonuses and unknown regimes without weakening the existing modern DrawInput. Keep such records staged until their applicable rules and required fields are known. Phase 2 must report this older coverage, even when it cannot yet accept those records into the modern model population.

## Rules and canonical transaction

Seed only evidence-backed rules with effective date intervals and source references. Distinguish the earlier 6/45 era from the 2026 6/45 era and the Monday schedule change. Prevent ambiguous/overlapping active rule intervals in ingestion validation. For each accepted draw validate exact game/rule linkage, effective date, six unique in-pool mains and rule-required bonus distinctness. Scheduled-date checks produce quality issues; documented postponements are permitted rather than discarded.

Phase 1's schema stores pending incomplete draws and enforces game/rule linkage but not complete accepted cardinality. Phase 2's accepted-record write path must enforce full contracts atomically. When older verified rules require no bonus, evolve the schema/contracts through a new migration; do not alter revision 0001 or manufacture a bonus. Until that change is justified, retain older claims as staged observations.

In one transaction, write the accepted observation reference, draw numbers, optional prize tiers and context. On validation failure leave the evidence intact, write an issue and avoid partial canonical acceptance. Money and counts retain nulls and Decimal semantics.

## Conflicts and corrections

Same numbers and bonus: keep corroborating source references and fill only previously unknown enrichment with provenance. Conflicting numbers/bonus: retain both observations, record the differing fields and quarantine the draw, excluding it from accepted coverage. Operator evidence may resolve the conflict through an explicit resolution event; do not silently overwrite independent evidence. If a previously accepted draw becomes disputed, update its status and record why. Prize-only disagreement leaves valid numbers accepted but marks the affected enrichment disputed; never combine incompatible amounts and winners into a fabricated tier.

## Coverage and completion

Report source observations and accepted draws separately by year, game and verified regime, with first/last dates, duplicates, missing bonus/prizes, conflicts, blocked URLs and unverified rules. Expected-date counts use verified schedules plus documented exceptions only. Unknown-rule years have unknown expected coverage, not zero missing draws. Never present source link counts as proof of completeness.

Phase 2 is complete when the pipeline is reproducible, live acquisition has produced a measured dataset including the required complementary context, repeated ingestion leaves canonical counts unchanged, cached imports rebuild the same records in an isolated database, conflicts and invalid responses are tested, and all actual coverage/gaps are documented. Include a coverage row for every complementary dataset, even when empty or unavailable. If access prevents complete history, deliver the functioning pipeline and explicitly report the limit; do not claim full collection.

## Validation and delivery

Tests use small saved fixtures representative of annual/detail/operator pages, early missing-bonus results, mixed currencies, unknown winners and malformed/blocked HTML. Include shared jackpots, missing prize tiers, mixed cash/ticket semantics, rollover gaps, overlapping ticket stories and annual metrics whose scope differs from main Lotto. HTTP retry/pacing tests use a local stub, not live websites. PostgreSQL integration tests cover atomicity, idempotence, rule boundaries, correction evidence, quarantine, enrichment conflicts and offline reconstruction. Test-only synthetic fixtures never enter the research DB.

Run a bounded live probe/import followed by the resumable historical backfill, report actual counts and hashes, and back up acquired evidence/database. Run runtime commands and the entire suite before local main merge; repeat runtime and tests after merge, then push according to project instructions. Local data and credentials remain ignored. No model, betting action or private player information is part of this phase.
