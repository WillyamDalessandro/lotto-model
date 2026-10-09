# Phase 3: data audit and reproducible snapshots

Status: draft for review. Date: 9 October 2026.

## Intent and scope

Create an inspectable, immutable main-Lotto dataset from existing evidence-backed ingestion records. This supports the historical research question without assuming the absent 527-draw dataset exists. Implementing and testing with synthetic data is possible now; freezing a real research dataset remains dependent on Phase 2 acquisition.

This phase adds auditing, export, verification and a snapshot registry. It does not collect new sources, train models, select holdout boundaries, publish data or implement purchasing. Undated academic combinations and all-games annual metrics remain outside the dated draw population.

## Architecture

Use a focused `lotto_model.audit` package for typed contracts, consistent database reads, eligibility decisions, portable bundle serialization and registry operations. Register a new `lotto audit` CLI group. Reuse existing contracts and schedule derivation where their semantics match; do not use global `calendar_dates.observed` as evidence of main-Lotto coverage.

Read each audit/export from one PostgreSQL REPEATABLE READ transaction. Canonical tables are not modified. Snapshot registration is the only database write. Evidence bodies are hash-checked when read and copied into the bundle, so subsequent path changes cannot invalidate a finished snapshot.

Runtime: Python >=3.12,<3.13, PostgreSQL, SQLAlchemy, Pydantic and Typer; no new runtime dependency. Outputs remain under ignored `data/` by default. No raw evidence is committed or published.

## Inputs and rule evidence

Require inclusive `start` and `end` dates, with start <= end. Game is fixed to `lotto` for version 1; unsupported games fail explicitly.

Require a reviewed JSON rule-evidence binding file for snapshot creation: `{"version":1,"rules":[{"rule_code":"...","artifact_sha256":"...","source_url":"..."}],"calendar_events":["record-key"]}`. Each applicable rule must resolve to exactly one valid saved artifact by hash and URL; reject duplicates and ambiguity. The binding attests that the cited body supports that exact database interval, pool and schedule; the software verifies identity and integrity, not the truth of a human rule interpretation. Export those rule values alongside the binding. For a report without bindings, report rule evidence as unverified.

Only explicitly listed calendar events are used. They must carry `game="lotto"`, a valid date and boolean `scheduled`, and valid hash-checked artifact evidence. Reject conflicting events. Existing unscoped events must be reviewed and replaced or explicitly enriched before inclusion; do not silently apply them to every game. An empty schedule is unknown, not proof of zero scheduled draws.

Absolute database evidence paths must resolve inside a supplied `evidence_root`; relative paths resolve against it. Reject path escape, missing files and hash mismatch. Operators choose a common ancestor if evidence lives in multiple local subdirectories.

## Population and eligibility

The audit reports all canonical main-Lotto draws within the requested dates and separately counts relevant staged/undated observations. Observation counts are not draw counts. Unknown or malformed dates are reported separately, never assigned guessed dates.

An eligible draw must be accepted, have six distinct mains within the effective pool, a rule belonging to the same game and covering its date, no unresolved `number_conflict`, and an accepted observation whose game/date/mains agree with the canonical row. Bonus may be null; when present it must be distinct and eligible. Require valid body evidence for that observation and a reviewed rule binding. Exclude invalid rows with all applicable reason codes. Canonical data stays untouched.

Other unresolved issues remain visible. Disputed prize tiers and jackpot context do not invalidate otherwise eligible numbers; export them with `disputed=true`, exclude them from summaries, and preserve unknown values as null. Prize/context evidence must be verified when those records are included. Unverifiable enrichment is omitted and counted with a reason, rather than silently becoming zero.

For each date compute expected scheduling from verified effective rules and scoped reviewed exceptions. Report expected draws, eligible observed draws, missing scheduled dates, unexpected observed dates and unknown-schedule dates. An unexpected eligible draw requires a reviewed exception before snapshot creation. Overlapping rules and contradictory exceptions block creation. Missing scheduled draws and unknown schedule coverage are listed gaps; they do not automatically disqualify otherwise verified observations, but the audit must expose them for later experiment design.

Zero eligible draws blocks snapshot creation, with a controlled diagnostic. A report on an empty database remains valid.

## Bundle contract and reproducibility

Schema version is 1. A snapshot directory contains:

- `draws.csv`: game, draw_date, rule_code, main_1 through main_6 sorted ascending, bonus, observation_key; ordered by game/date.
- `rules.json`: intervals, pools, schedules and portable evidence references; sorted by rule code.
- `enrichment.json`: prize/context records, decimal amounts as strings, missingness and dispute flags; stable draw/tier order.
- `audit.json`: population counts, exclusions, issues and schedule gaps; stable reason/date order.
- `lineage.json`: source code, URL, artifact hash, retrieval time, parser version, record key and observation payloads; includes selected and conflicting observations relevant to exported/excluded draws, rule bindings and reviewed exceptions.
- `evidence/<sha256>.body`: deduplicated required evidence bodies.
- `manifest.json`: requested range, game, schema version, file hashes/sizes, content digest, source Git revision and extraction time.

Define observation_key as SHA-256 of canonical JSON containing source code, URL, artifact hash, parser version and record key. Retain original IDs only as diagnostic metadata outside content identity; exports must not depend on surrogate IDs or host paths.

Canonical JSON uses UTF-8, sorted keys, compact separators, ISO dates, UTC timestamps with `Z`, decimal strings and one terminal LF. CSV uses UTF-8, LF, fixed column order, standard CSV quoting and empty fields for null. No run IDs, current timestamps, database IDs or absolute paths enter hashed content files. Preserved source retrieval times are source metadata, not newly generated timestamps.

content_sha256 is SHA-256 of canonical JSON mapping each content file's relative path to its SHA-256, excluding manifest.json. Manifest extraction time and source revision are descriptive metadata outside that digest. Re-exporting unchanged inputs produces the same content digest; relevant corrections produce a new digest. Byte-for-byte identity is required for content files, not fresh manifest timestamps.

Create under a temporary sibling directory and publish by rename to `<output_root>/<content_sha256>`. Never overwrite an existing bundle. If that directory already exists, verify it and return it; corrupt existing content fails. Register only verified final bundles. Registry key is content_sha256; retain the first creation timestamp and path. A valid bundle left after a database registration failure can be registered by retry. Failed temporary directories are removed safely within the designated output root.

Add a new migration after the latest revision for `dataset_snapshots`: id, unique 64-character lowercase-hex content_sha256, schema_version, game, starts_on, ends_on, included_draws > 0, manifest_path, created_at UTC. No change to frozen older migrations. The application exposes insert-or-return, never an update/delete command for finished snapshots.

## CLI and failure behaviour

`lotto audit report --start YYYY-MM-DD --end YYYY-MM-DD --evidence-root PATH [--bindings PATH] [--output PATH]` produces JSON without writes to canonical data or registry.

`lotto audit snapshot --start YYYY-MM-DD --end YYYY-MM-DD --evidence-root PATH --bindings PATH [--output-root data/snapshots]` creates/verifies/registers a bundle and prints path, digest and included count.

`lotto audit verify PATH` validates manifest schema, safe relative paths, exact listed content files, hashes/sizes, content digest, row counts, eligibility and internal lineage without a database connection or network. It rejects symlinks, path traversal and unlisted content. Nonzero exit on failure; sanitized messages must not reveal credentials or source body contents.

## Completion and delivery

Tests cover eligibility, evidence failures, game isolation, unknown schedules, boundary dates, disputed enrichment, stable identity after database restore, atomic output/retry and tampering. Run runtime help/report/verify checks and the full relevant test suite before and after merging with local main; push only after success.

Software completion requires synthetic reconstruction into the isolated test database and identical content hashes. Actual Phase 3 completion additionally requires a nonempty audited historical bundle, preserved evidence/database backups, successful restore/re-export and review of remaining coverage gaps. Passing synthetic tests alone does not declare the real research dataset ready.
