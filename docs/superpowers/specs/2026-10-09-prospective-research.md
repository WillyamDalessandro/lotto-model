# Phase 6: prospective research and optional manual play preparation

Date: 9 October 2026. Status: draft for review.

## Goal and prerequisites

Record genuinely pre-result current-regime predictions and measure them prospectively. Require the historical report, verified current rules/schedule, permitted refresh path and a separately reviewed prospective protocol. Historical promising status is not current-regime validation. Start with a uniform research baseline; an experimental model may run as a labeled separate arm only after its current-regime feature/training contract is reviewed. Never transfer incompatible 6/47 probabilities to 6/45 silently.

## Protocol and issue rules

Protocol includes version, start date, rule_code/pool, schedule evidence, per-draw issue_deadline as an explicit timezone-aware instant, policy/arm identifiers, line budgets, root_seed, training constraints, result source policy and review window. No guessed draw time or purchasing cutoff. Validate eligible pool from evidence; no 46/47 in a verified pool=45 output.

Use database server UTC time as issuance authority. Atomically check now < issue_deadline, no accepted target result already exists and current rule covers the target date before insertion. Lock the draw/session identity so result ingestion and issuance cannot race; integrate the same lock in canonical ingestion. Missed or failed issuance is recorded, never backfilled. Generate complete portfolios atomically with immutable lines and seed/cutoff metadata. A target with unknown schedule/deadline refuses issuance.

A prospective protocol is immutable after its first issue. Same-date retries return the existing identical issue; a changed policy/budget/line fails. Policy revisions create new arms/protocols with forward start dates, preserving prior failures and outcomes. Model records carry training endpoint < target date and verified artifact/environment hashes.

## Result refresh and reporting

Refresh through the existing permitted evidence importer. Source access limits apply equally to HTTP and any future browser adapter; browser automation is optional and requires a separately reviewed source-specific adapter, not a generic bypass. No scheduled automation is created by this implementation request.

Score only accepted evidence-backed results. Quarantined outcomes stay pending/disputed; corrected results append evaluation revisions keyed by result evidence, preserving previous scores and the issued line. Reimport is idempotent. Distinguish issued draws, missed scheduled draws, pending outcomes and disputed outcomes. Show both completed-issue performance and overall coverage; never score missed issues as fabricated losses or silently drop them.

Default review window is 100 completed draws, descriptive reporting only. Do not claim confirmed advantage from interim p-values. Any confirmatory prospective claim requires a separately reviewed power/stopping/multiple-testing protocol before its first evaluated window. Display one-line 3-plus primary, secondary 5-plus/portfolios and current regime/date ranges; keep arms separate and label experimental ones.

## Optional manual play preparation

This is a separate opt-in component after the research ledger works. Require user-supplied per-draw and weekly EUR limits, verified price per line, minimum purchase lines, effective price/rule dates and a manual ledger. Unknown limits/prices disable preparation. Money uses Decimal, EUR cents, nonnegative values; weekly boundary uses Europe/Dublin ISO Monday through Sunday, including DST.

Reserve preparation cost atomically against both limits, including existing reservations and confirmed manual spending. Reject over-limit preparation; retry cannot reserve twice. Manual confirmation converts a reservation to spent; cancellation releases it; no refund inference. Changing limits below commitments blocks further preparations and leaves history intact. Research budget of one line is not necessarily a valid retail purchase; enforce reviewed minimum lines. No ticket submission, payment, auto-purchase or claims of expected profit.

## Completion

Python >=3.12,<3.13; existing runtime/research dependencies, no publication. Verify immutable and race-safe issue checks, late windows, eligible lines, rule changes, result corrections and missed-draw accounting. Optional play completion additionally requires explicit budgets/prices and atomic limit/DST tests. Run runtime/full tests before/after local-main merge then push code/docs. Completion of software does not constitute prospective evidence.
