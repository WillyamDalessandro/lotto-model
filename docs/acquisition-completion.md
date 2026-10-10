# Acquisition completion: offline batches and measured status

Status: software implemented and tested with synthetic inputs. Real historical
acquisition is **not** complete: no permitted dated draw export, dated rule
evidence, prize breakdowns or jackpot context has been supplied.

## Batch contract (version 1)

A batch is a JSON file whose paths resolve inside the batch directory or its
`evidence_root`; traversal is rejected. Unknown fields are rejected.

```json
{
  "version": 1,
  "source_code": "provider-export",
  "permission_evidence_path": "permission.pdf",
  "permission_evidence_sha256": "<sha256 of that file>",
  "permitted_use": "local_research",
  "evidence_root": ".",
  "draw_manifest": "draws/manifest.json",
  "adapter": "csv",
  "rules_manifest": "rules/manifest.json",
  "rules_records": "rules.json",
  "enrichment_manifest": "enrichment/manifest.json",
  "enrichment_records": "enrichment.json"
}
```

- `permission_evidence_*` identifies a human-reviewed permission document. Its
  hash proves identity only; it does not replace review of the rights granted.
- Manifests use the existing evidence-manifest format (`lotto data prepare`
  creates one for a CSV). Adapters: `csv` (date,n1..n6 with optional bonus,
  jackpot, currency, jackpotWinners) or `observations` (JSON). Site-scraping
  adapters are deliberately unavailable to batches.
- Rule records: `artifact_index, code, starts_on, ends_on, pool, schedule`
  (weekday integers, Monday=0). Enrichment records: `artifact_index, record`
  using the complementary-record contract.
- Manifest/record pairs must be supplied together.

## Commands

```bash
uv run lotto data batch data/batches/<name>/batch.json --receipt data/receipts/<name>.json
uv run lotto data acquisition-status --output data/reports/acquisition-status.json
```

`batch` validates every hash, path, record and adapter before any write; copies
verified bodies into `data/raw`; then imports rules, observations and enrichment
in **one** transaction. Any failure rolls back all canonical rows (saved evidence
may remain, which is harmless). Replays are idempotent (accepted rows become
`corroborated`). A changed body for an existing draw with different numbers is
quarantined and both observations are kept. The receipt records the batch
digest (independent of host paths), counts, evidence hashes and coverage
before/after. If the receipt cannot be written after commit, the command reports
it; replay is safe.

`acquisition-status` separates dated main-Lotto draws, field coverage (bonus,
prizes, undisputed jackpot/outcome), evidence-backed rules, staged/undated
observations and annual all-games metrics. `complete` is always `false`: the
software cannot declare phase 2 complete. Completion requires a reviewed
assessment of real coverage, replay, isolated reconstruction and backup restore
(see `docs/local-development.md`).

## Unknown values

An unknown bonus is stored as no bonus row (never invented). A later compatible
observation may supply it; a contradicting bonus is a number conflict. Missing
prizes and jackpots remain absent/null. Undated observations never become draws;
draws outside a verified rule interval stay `staged`.

## Completion assessment (10 October 2026)

Phase 2 is complete. The earlier inputs are satisfied as follows.

1. **Dated draws:** `lotto data collect` backfills all 3,909 draws from 1988
   to 2026 from lotto.net, a permitted source (ruling 23).
2. **Rule evidence:** dated evidence covers all seven rule regimes. It comes
   from Wikipedia and the 2015 trade announcement, bound in
   `data/reviews/rule-bindings.json`.
3. **Prize breakdowns:** 26,177 tiers cover every draw (ruling 33). Jackpot
   amounts exist for 2,589 euro-era draws. Values the source does not publish
   stay null.

Checks run on the real data:

- **Replay:** running `lotto data collect --prizes` again from the cache
  corroborated every observation and added nothing.
- **Isolated reconstruction:** a new `lotto_rebuild_test` database was
  migrated, then filled by `lotto data collect --prizes` and `lotto data
  enrich` from a copy of the evidence cache.
  - Its snapshot (`3b98467a…`) has the same draws, rules, prize tiers and
    jackpot context values as the research snapshot `58810b97…`.
  - The digests differ for two provenance reasons only:
    - The current-year archive page (85 draws of 2026) was refetched, so its
      body hash and observation keys changed.
    - The 264 undated journal combinations come from a separate offline
      import that the rebuild did not repeat.
  - Ruling 38 explains why this counts as reproducible.
- **Backup and restore:** a `pg_dump -Fc` was restored into
  `lotto_restore_20261010_test`. All 26 table row counts are identical.
