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

## Remaining real-data inputs

1. A permitted dated main-Lotto export (with provenance and permission record).
2. Dated rule/schedule evidence for every regime covered by that export.
3. Prize breakdowns and jackpot/outcome context, or an explicit statement that
   they are unavailable.
