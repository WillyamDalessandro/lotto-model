# Data audit and reproducible snapshots

Status: software implemented and verified with synthetic data in the isolated
test database. No real research snapshot exists: the research database has no
accepted draws (see `docs/phase2-coverage.md`). Passing tests does not make the
historical dataset ready.

## Commands

```bash
uv run lotto audit report --start 1988-04-16 --end 2026-10-09 --evidence-root data --bindings data/reviews/rule-bindings.json
uv run lotto audit snapshot --start 1988-04-16 --end 2026-10-09 --evidence-root data --bindings data/reviews/rule-bindings.json
uv run lotto audit verify data/snapshots/<content_sha256>
```

- `report` reads one REPEATABLE READ view and prints JSON (counts, exclusions
  with reason codes, unresolved issues, schedule coverage, warnings, blocking
  conditions, `snapshot_ready`). It writes nothing to canonical tables or the
  registry. Without `--bindings`, every rule is reported as unverified.
- `snapshot` audits, builds the bundle, writes it under a temporary sibling,
  verifies it, renames it to `<output-root>/<content_sha256>` and registers it
  in `dataset_snapshots` (insert-or-return). An existing bundle is verified and
  reused, never overwritten.
- `verify` needs no database or network. It rejects symlinks, unsafe or unlisted
  paths, hash/size or digest mismatches, ineligible rows, count mismatches and
  draws without verified lineage/evidence.

## Rule-evidence bindings (reviewed by a person)

```json
{"version": 1,
 "rules": [{"rule_code": "6/47", "artifact_sha256": "<sha256>", "source_url": "https://..."}],
 "calendar_events": ["lotto:2026-12-25"]}
```

A binding states that the cited saved body supports that rule's exact interval,
pool and schedule. Software checks identity and integrity only. The binding URL
must equal the rule's recorded `evidence_url`. Artifact rows sharing the same
hash and URL are treated as the same evidence (identical bytes). Calendar events
are used only when listed, and each must carry `game="lotto"`, `day` and a
boolean `scheduled`; conflicting events block snapshots.

## Choosing `--evidence-root`

Database body paths are absolute or relative; every one must resolve inside the
evidence root. Use a common ancestor (typically `data`). Missing, escaped or
corrupted evidence excludes the affected draw (`invalid_evidence`) or omits the
affected enrichment (counted under `enrichment_omitted`).

## Eligibility and coverage

Reason codes: `invalid_status`, `invalid_mains`, `invalid_bonus`,
`observation_mismatch`, `number_conflict`, `unverified_rule`, `rule_mismatch`,
`invalid_evidence`. All applicable reasons are listed. Unknown bonus is allowed.
Disputed prizes/jackpots are exported with `disputed=true` and never drop an
otherwise eligible draw.

Schedule coverage uses verified rules plus listed events only. Each date is
expected, not scheduled, or unknown. An empty schedule is unknown. Missing
scheduled dates and unknown days are reported gaps, not exclusions. Eligible
draws on non-scheduled dates block snapshot creation until a reviewed exception
event is bound. Overlapping verified rules and zero eligible draws also block.

## Bundle contents (schema 1)

`draws.csv`, `rules.json`, `enrichment.json`, `audit.json`, `lineage.json`,
`evidence/<sha256>.body` and `manifest.json`. Content files are canonical
(sorted keys, compact JSON, ISO dates, UTC `Z`, decimal strings, LF). No
database IDs, run IDs, host paths or current times enter content files.
`content_sha256` hashes the path-to-hash map of all content files (manifest
excluded); the manifest carries descriptive extraction time and source revision.

## Retry and reconstruction

If registration fails after publication, rerun the same command: the verified
bundle is reused and registered once. Interrupted temporary directories are
removed. Rebuilding equivalent observations (same evidence bytes and retrieval
times) with different database IDs and evidence locations yields the same
content digest; a corrected source produces a new digest while earlier bundles
still verify. Registry rows reject UPDATE and DELETE.

Snapshots live under ignored `data/snapshots`; back them up with the database
and raw evidence. Never commit or publish bundles.
