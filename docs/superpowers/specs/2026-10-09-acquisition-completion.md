# Phase 2 completion: dated historical acquisition

Date: 9 October 2026. Status: draft for review.

## Goal and boundary

Complete the historical inputs needed by the Phase 3 audit: dated main-Lotto numbers, verified rules/schedules, prizes and jackpot context. Extend existing offline ingestion only where supplied permitted inputs require it. Existing research-source imports remain complementary: undated combinations cannot become dated draws; annual all-games figures cannot become draw-level predictors.

No new source is assumed accessible or licensed. This design makes acquisition repeatable but cannot manufacture missing inputs. Do not contact providers, create accounts, harvest restricted sites or publish data as part of this phase.

## Input contract and workflow

Use the existing evidence manifest, draw CSV preparation/import, curated complementary records and rule registration commands. Introduce an acquisition batch JSON with version=1, source_code, permission_evidence_path, permission_evidence_sha256, permitted_use, evidence_root, draw_manifest, adapter, rules_manifest/rules_records, enrichment_manifest/enrichment_records. Paths resolve within the batch directory or supplied evidence root; reject traversal. permitted_use must be `local_research`. A reviewed permission document identifies source, covered files, usage conditions and review date; its presence/hash does not substitute for human review of rights.

All optional manifest/record pairs must be supplied together. Validate every path, hash, source identity, adapter and record before mutation. Import reviewed rules first, observations second, enrichment third, using one transaction and the existing repository. Files are preserved before the transaction; failure may leave saved evidence but no partial canonical import. Do not fetch network content from a batch. Existing permitted source-specific collectors keep their own reviewed policies.

Replaying identical batch contents is idempotent. A changed body creates new evidence; conflicting numbers are quarantined and never automatically accepted. Use existing operator-backed explicit resolution, preserving both claims. Missing prizes/jackpots remain null. Rule dates require evidence, not inference from observed number ranges.

## Reporting and completion

Write a batch receipt with content digest, imported/corroborated/staged/quarantined counts, evidence hashes and coverage before/after. Separate undated and annual complementary counts from canonical dated draws. Missing bonus does not imply an invented bonus. Measure prize/jackpot presence and fields, not just table counts.

`lotto data batch BATCH_PATH [--receipt PATH]` applies reviewed offline inputs. `lotto data acquisition-status [--output PATH]` reports measured availability and outstanding mandatory datasets. It must never say phase 2 is complete merely because imports or tests pass. Completion requires reviewed dated draw/rule/prize/jackpot coverage and a documented acquisition assessment, idempotence, disagreement handling, isolated reconstruction and evidence/database backup restore. Partial or unavailable inputs remain explicit.

Python >=3.12,<3.13; existing runtime dependencies; sequential writers. No migration unless implementation review finds a concrete need. Output receipts/data stay under ignored data/. Research data is never replaced with synthetic test fixtures.

## Verification

Test malformed batches, unsafe paths, invalid evidence, transaction rollback, exact replay, source corrections, conflicting numbers, unknown regimes, undated records, missing enrichment and all-games scope. Runtime and full tests run before local-main merge and again after it; push only on success. A real acquisition milestone remains blocked until permitted inputs exist even if software is ready.
