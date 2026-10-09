# Historical Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the current session. Steps use checkbox syntax for tracking. Request a fresh whole-branch review before merge.

**Goal:** Collect the accessible Irish Lotto history and complementary lottery context into local PostgreSQL with evidence, resumable fetching and measured coverage.

**Execution status, 9 October:** ingestion foundation implemented and verified;
historical acquisition and phase completion remain incomplete. Reviewed archive
and operator policies prevent the planned automated backfill. Two open-government
annual metrics were collected; calendar dates retain unknown schedules. See
[actual coverage](../../phase2-coverage.md). Implemented adapters live in one
parsers.py module, and reviewed access policy lives in fetch.py. Curated imports
replace automatic story/report table extraction for this milestone. No dated
rule intervals were seeded without reviewable evidence.

**Architecture:** Source-specific parsers produce validated observations without network or database access. A content-addressed evidence store and bounded HTTP client preserve retrievals; a transactional repository reconciles observations with canonical records. CLI workflows connect those components and emit inspectable coverage and enrichment reports.

**Tech Stack:** Existing Python 3.12/uv, PostgreSQL 18, SQLAlchemy/psycopg, Alembic, Pydantic/Typer; add httpx and beautifulsoup4. pytest/Ruff remain the verification tools.

**Spec:** [Approved ingestion spec](../specs/2026-10-09-historical-ingestion.md), including [complementary catalogue](../../complementary-data.md).

## Global constraints

- Main Lotto only; Plus sections may remain in raw evidence but are not canonical main-game records.
- One request at a time, at least two seconds per host, 20-second timeout and at most three transient attempts. Honour longer crawl delays and Retry-After.
- Stop a host on access denial or CAPTCHA. Do not visit account, play or checkout routes.
- Preserve original prize text/currency, nullable unknowns, publication time when known and field-level source lineage.
- Modern accepted draws require six distinct eligible mains, separate eligible bonus and verified effective rule. Unknown historical rules/bonus semantics stay staged.
- No fabricated winner counts, currencies, ticket identifiers, historical publication times or per-draw sales.
- Holidays, weather and economic datasets are outside this implementation. Derived lottery calendar remains included.
- No model training or purchases. Data, backups and credentials remain ignored by Git.
- Full runtime/test checks before local main merge, repeated after merge, then push as already authorised.

## Review focus

- HTML error pages, advertisements and Plus results must not become accepted main Lotto draws.
- Offline manifests must reject escaping paths, mismatched hashes and unsupported source identities before mutation.
- Interrupted or repeated acquisition must preserve evidence and avoid duplicate canonical records.
- Conflicting numbers quarantine formerly accepted draws; a disputed enrichment field must not silently overwrite evidence.
- Unknown regimes, historical currencies and incomplete rollover history must remain explicitly unresolved.

## Task 1: Observation contracts and source parsers

**Files:** src/lotto_model/ingestion/contracts.py, sources.py, parsers/archive.py, parsers/detail.py, parsers/operator.py; tests/ingestion/test_parsers.py and small fixtures under tests/fixtures/ingestion; pyproject.toml and uv.lock.

**Interfaces:** `Observation` contains game, draw_date, six mains, nullable bonus, source_url, optional jackpot amount/currency/outcome and `PrizeObservation` records. `PrizeObservation` contains tier, nullable winners/Decimal amount, currency, original text and prize type. `parse_archive(body: bytes, url: str) -> list[Observation]`, `parse_detail(body: bytes, url: str) -> Observation`, `parse_operator(body: bytes, url: str) -> list[Observation]`. Unsupported or semantically invalid pages raise `ParseError`.

- [ ] Add locked HTTP/parser dependencies and establish a green existing-suite baseline against the isolated test service.
- [ ] Write parser tests using small saved real-page sections plus synthetic error variants: 1988 no bonus, current seven numbers, annual 2026 links, Plus contamination, HTTP-200 CAPTCHA, wrong draw date, missing tier cells, zero versus unknown winners, EUR/pound values and mixed ticket/cash prize text. Observe failures before implementation.
- [ ] Implement source-specific section selection, explicit date parsing, number contracts and Decimal currency parsing. Retain ambiguous pound symbols as unresolved source currency until evidence establishes the denomination. Reject duplicate dates with incompatible values inside one page.
- [ ] Assert the operator 7 October 2026 fixture produces mains `{3,17,26,29,37,42}` and bonus `38`; assert the 1988 fixture retains bonus/winners as null and does not assign EUR.
- [ ] Run parser tests, the existing full suite and Ruff; commit the parser deliverable.

## Task 2: Evidence store and polite acquisition

**Files:** ingestion/evidence.py, fetch.py, policy.py; tests/ingestion/test_evidence.py, test_fetch.py and test_policy.py.

**Interfaces:** `Artifact` holds requested/final URL, retrieval timestamp, HTTP status/type, SHA-256, relative body path and semantic status. `EvidenceStore.write(body: bytes, metadata: dict) -> Artifact`; `EvidenceStore.load_manifest(path: Path) -> list[Artifact]` verifies all files before returning. `Fetcher.fetch(url: str, refresh: bool = False) -> Artifact` uses an injected httpx client and clock/sleep for deterministic tests. `AccessPolicy` owns host/path permissions and source review status.

- [ ] Write failing tests for stable body hashes, unchanged cached bytes, corrupt evidence, directory traversal, absolute paths and symlink escapes. Assert invalid imports create no database records.
- [ ] Implement versioned JSON manifests with portable relative body paths and append-preserved retrieval events; verify bytes on cache reads. Save bodies even when semantically invalid, but do not treat them as successful checkpoints.
- [ ] Write local-stub HTTP tests for 500 retry then success, timeout exhaustion, 429/Retry-After, host pacing, redirects to unsupported/play hosts, CAPTCHA/403 stopping a host, invalid robots HTML and cache reuse without requests.
- [ ] Implement bounded fetching, descriptive user agent and policy checks before each redirected request. Cache policy evidence with its review time; discovery reports unresolved access policy explicitly. Read published source terms and record the access decision before a live bulk run.
- [ ] Run focused and full tests; commit. Live sites are excluded from automated tests.

## Task 3: Versioned storage and atomic reconciliation

**Files:** migrations/versions/0002_ingestion.py; ingestion/repository.py, rules.py; tests/integration/test_ingestion.py; update tests/integration/test_database.py to resolve current migration head instead of hard-coding 0001.

**Interfaces:** `Repository.record_artifact(artifact: Artifact, run_id: int) -> int`; `Repository.ingest(observation: Observation, artifact_id: int, parser_version: str) -> IngestResult`. `IngestResult` distinguishes accepted, corroborated, staged, quarantined and enrichment conflict. `resolve_rule(connection, game: str, draw_date: date)` returns one evidence-backed applicable regime or a staged reason.

- [ ] Write failing integration tests for new evidence/context/issue/checkpoint tables, idempotent import, atomic rollback, mismatched rule/game, temporal boundaries, missing historical rules, and accepted numbers requiring provenance.
- [ ] Add migration 0002 without editing 0001. Add draw_context, quality_issues, fetch_checkpoints, rule_attributes, calendar_dates/events, winning_ticket_reports and official_period_metrics. Extend observation deduplication with a source-record key plus artifact/parser version; record requested/final URLs and publication timestamps separately. Retain original-currency amounts separately from prize_eur.
- [ ] Load only verified rule intervals. Record evidence for 2015 6/47 start and 2026 6/45/schedule changes; do not silently seed older eras from secondary guesses. Keep observations available even if rule evidence is incomplete.
- [ ] Implement a transaction that validates effective rules with DrawInput, writes accepted draw/numbers/context/prizes together and retains missing values. Unknown regimes and incomplete required bonuses remain staged, not erroneous synthetic draws.
- [ ] Write failing tests for incompatible numbers, newly disputed accepted draws, operator resolution with a resolution event, prize-only disagreements, shared jackpot pool versus per-winner prize and duplicate evidence references. Implement explicit quarantine/resolution and source-linked enrichment values.
- [ ] Verify migration from 0001 with synthetic data preserved, empty-database upgrade, repeated upgrade and full-suite success; commit.

## Task 4: Complementary datasets and derived context

**Files:** ingestion/complementary.py, calendar.py, derived.py; tests/ingestion/test_complementary.py, test_derived.py; tests/integration/test_complementary.py.

**Interfaces:** `build_calendar(start: date, end: date, rules: list, exceptions: list) -> list[dict]`; `derive_context(draws: list[dict]) -> list[dict]`. Complementary import contracts identify dataset, source evidence, event/publication/effective dates, period/game scope, unit and value. `Repository.ingest_complementary(record, artifact_id)` stores those typed records idempotently.

- [ ] Write failing tests for calendar dates without draws, rule/schedule changes, rescheduled draws, unknown-schedule periods and ISO-year boundaries. Implement only evidence-backed scheduling; exceptions require their own source.
- [ ] Write failing tests for rollover gaps, unknown preceding wins, zero-winner prizes, shared jackpots, mixed cash/ticket payouts, currency separation, duplicate draw/prize joins and previous-draw overlap. Implement derived outputs retaining input identifiers and definition version. Do not label face-value totals as allocated funds.
- [ ] Add rule-attribute import for effective prices, minimum purchase, caps and prize semantics with evidence. Nullable unsupported attributes remain unknown.
- [ ] Add bounded operator-story discovery and structured public ticket/location imports tied to saved evidence. Preserve purchase-county versus online-player-county meaning; deduplicate overlapping stories conservatively. Automated acceptance requires explicit draw linkage; ambiguous mentions remain staged. Never import personal names.
- [ ] Inventory operator/regulator report links and preserve accessible reports. Import explicitly evidenced annual metrics with report period, game/all-games scope, currency/unit and publication time; use a provenance-bearing curated import when automatic table extraction is unreliable. No synthetic per-draw allocation.
- [ ] Test overlapping stories, missing claim dates and annual metrics that cannot be joined as draw-grain values. Run the full suite; commit.

## Task 5: CLI, reporting and resumable live backfill

**Files:** ingestion/workflows.py, report.py, commands.py; src/lotto_model/cli.py; tests/ingestion/test_workflows.py, test_commands.py; docs/ingestion.md and docs/phase2-coverage.md; README.md.

**Interfaces:** `discover`, `collect`, `enrich`, `import` and `report` under `lotto data`. Collect accepts start/end years, refresh and max-requests. Enrich accepts date range, dataset and max-requests. Report returns a versioned JSON object with source/regime/year counts plus every complementary dataset's coverage and missingness reasons.

- [ ] Write failing tests for offline cache rebuild, zero duplicate draws on a repeated run, resumed incomplete runs, end-year/date validation, bounded request budgets and sanitised CLI errors. Implement run lifecycle and per-URL checkpoints using the prior tasks' interfaces.
- [ ] Add report tests asserting accepted/staged/conflicted counts differ correctly, unknown expected coverage stays null, missing bonuses/prizes are explicit and all catalogue datasets appear even when empty. Export calendar/derived summaries with evidence references and definitions.
- [ ] Run a bounded live collection against reviewed sources, independently compare operator overlap and inspect stored provenance; fix any source-layout differences with regression fixtures before continuing.
- [ ] Backfill accessible annual pages from 1988 through 2026 with checkpoints, then missing detail pages for prizes/context. Acquire complementary rule/story/report evidence within explicit limits. Preserve all gaps and blocked statuses; resume as needed rather than restarting the entire scrape.
- [ ] Import the resulting manifest into an isolated test database and reconcile accepted records, numbers and optional context against research DB exports. Repeat research import to prove unchanged canonical counts.
- [ ] Record actual dataset and field coverage, earliest/latest dates, rule verification, complement completeness, unresolved conflicts and source-access limitations in docs/phase2-coverage.md. Save database/evidence backups outside Git.
- [ ] Run CLI runtime commands, `uv run pytest -q`, Ruff lint/format and `git diff --check`; request whole-branch review and resolve important issues. Commit verified work.
- [ ] Merge with local main, repeat runtime and full-suite checks, then push. Report actual coverage and limitations; do not claim all-history completion when a source/field remains inaccessible.

## Execution and scope rulings

Implement in this session, consistent with phase 1. The tasks share evidence and repository interfaces, so do not parallelise writes. Large enrichment backfills may take hours at the required pacing; communicate measured progress and use checkpoints throughout. A source-access failure does not authorise bypassing its restrictions or replacing unknown facts with estimates.

This plan covers collection and complementary context. Phase 3 independently audits and freezes the resulting dataset; modelling remains deferred.
