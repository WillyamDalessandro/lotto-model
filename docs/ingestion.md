# Evidence-backed ingestion

Run commands from the repository root after following local-development.md.

```powershell
python -m uv run lotto db migrate
python -m uv run lotto data discover
python -m uv run lotto data official
python -m uv run lotto data calendar 1988-01-01 2026-10-09
python -m uv run lotto data report --output data/reports/phase2-coverage.json
```

`official` fetches two reviewed public government resources, checks the CC BY 4.0
catalogue licence, validates PDF bytes and pins the reviewed report hash before
importing curated metrics. A changed report requires a fresh review. It preserves
annual all-games scope and unknown publication time. Repetition reuses saved
evidence and does not duplicate metrics. It does not extract every report table.

## Local draw exports

The supplied CSV must have `date,n1,n2,n3,n4,n5,n6` columns. Dates use ISO
`YYYY-MM-DD`; `bonus,jackpot,currency,jackpotWinners` are optional. Unknowns are
empty cells. Currency must come from the source, rather than an assumed default.
CSV ingestion does not currently import prize-tier columns.

```powershell
python -m uv run lotto data prepare C:/path/to/export.csv --root data/raw/imports
python -m uv run lotto data import data/raw/imports/manifest.json --adapter csv
```

`prepare` validates the complete CSV and saves immutable bytes. Import verifies
all hashes and paths before writing, copies evidence to its local store, and
commits each artifact atomically. Previously committed artifacts survive an
interruption; rerunning is safe. Retrieval events and parser-versioned source
observations remain inspectable. A different parsed payload for the same
artifact/version/key is rejected. Use a new parser version for a parser correction.

Accepted modern draws require a verified effective rule and six distinct mains
with a distinct bonus within its pool. Data with unknown rules or missing bonuses
remain staged. Staging does not mean the original result is false.

## Rules and complementary imports

Rules are deliberately not pre-seeded from current assumptions. `data rules`
accepts a verified evidence manifest and a JSON list of definitions:

```json
[{"artifact_index": 0, "code": "reviewed-regime", "starts_on": "2026-01-01",
  "ends_on": null, "pool": 45, "schedule": [0, 2, 5]}]
```

This is a schema example, not evidence that this interval is correct. Weekdays
use Python's Monday=0 convention. Overlapping intervals are rejected. This
implementation supports the modern six-main/one-bonus contract; older rule
semantics remain staged.

`data enrich MANIFEST RECORDS` accepts a JSON list containing `artifact_index`
and `record`. A record has `dataset`, `record_key`, optional `published_at` and
`payload`. The four supported datasets are `rule_attributes`, `calendar_events`,
`winning_ticket_reports` and `official_period_metrics`. Required dimensions are
validated by ComplementaryRecord. Records link to raw evidence. Changed facts
under the same key/artifact are rejected; new evidence retains a separate version.
These are curated imports, not automatic story scraping or conflict resolution.

Number disagreements quarantine canonical draws; no source silently overwrites
accepted numbers. The repository's explicit `resolve_numbers` API requires an
operator observation, retains conflicting observations and records resolution.
Ordinary offline imports have manual authority and cannot resolve disagreements.
Compatible, more complete enrichment can replace a partial tuple only when one
observation supplies all its previously known values. No synthetic cross-source
tuple is created. Prize disagreements remain issues and source observations;
disputed tiers are excluded from monetary summaries. Jackpot disagreement
marks its context disputed and excludes it from derived outcomes.

## Coverage and evidence

The report lists actual dataset counts, source-record field missingness, prize
missingness, rule intervals, unresolved issues and checkpoints. Full expected
historical coverage stays null until historical schedules/exceptions are verified.
Calendar dates without an evidenced schedule have `scheduled=null`; a calendar
row does not establish that a draw happened. Rebuild after importing rules/events.

Derived descriptors are post-draw research context. Prize totals are partial
published face values grouped by currency, never allocated funds or per-draw
sales. Rollover streaks remain unknown without verified continuity. Publication
time and prediction-time availability are not inferred from retrieval time.

Manifests contain portable relative paths. Database artifact paths identify the
local evidence files; preserve the evidence tree alongside database backups.
Raw bodies, reports and backups are ignored by Git. Ingestion HTTP defaults deny
unreviewed hosts, enforce HTTPS and reviewed routes, check redirects, stop access
denials/CAPTCHAs, bound retries and pace requests. Long Retry-After values defer
the run. Historical `collect` currently exits with a source-policy explanation.

## Full-history backfill

`lotto data collect [--start-year 1988] [--end-year YYYY] [--max-requests 100]`
works in three steps:

1. It fetches the reviewed rule evidence and the lotto.net yearly archives into
   `data/raw/backfill`. Each request waits 5 seconds. Every response is
   checked for content, and past years are reused from the cache.
2. It registers the seven reviewed rule intervals (`RULES` in
   `ingestion/backfill.py`).
3. It imports exactly the selected archive bodies through the normal evidence
   import, writing the manifest to `data/raw/backfill-import/manifest.json`.

Rerunning is idempotent; only the current year is refetched. Source policy and
measured coverage are in [phase2-coverage.md](phase2-coverage.md).
