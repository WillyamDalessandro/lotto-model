# Prospective research

Status: research ledger implemented and tested with synthetic rules and results
in the isolated test database. No real prospective protocol is registered and no
lines have been issued. Optional manual play preparation (spending limits) is
**not implemented**: it needs user-supplied per-draw/weekly EUR limits and
verified price and minimum-line evidence, and none were supplied.

## Protocol (reviewed JSON, version 1)

```json
{
  "start_date": "2026-10-12",
  "rule_code": "6/45",
  "pool": 45,
  "schedule": [0, 2, 5],
  "rule_evidence_sha256": "<sha256 of the saved rules evidence>",
  "schedule_evidence_sha256": "<sha256 of the saved schedule evidence>",
  "deadline_local_time": "19:45:00",
  "deadline_timezone": "Europe/Dublin",
  "deadline_evidence": "where the issue deadline comes from (reviewed)",
  "deadline_overrides": {"2026-12-24": "2026-12-24T12:00:00+00:00"},
  "arms": [{"id": "uniform", "policy": "uniform", "budgets": [1, 5, 10]}],
  "result_source_policy": "permitted saved exports via lotto data batch",
  "review_window": 100
}
```

The deadline time above is a placeholder. A real protocol must take its issue
deadline from reviewed evidence, never from a guess. Each target's deadline is
an explicit timezone-aware instant: the local time in `deadline_timezone` (DST
handled by `zoneinfo`) or an aware override. The protocol must match exactly one
verified rule (code, pool, schedule, and evidence hash among valid artifacts at
the rule's evidence URL) that covers its start date. A model arm must be
`experimental` and carry a reviewed current-regime contract (`frozen`,
`rule_code`, `pool`, `reviewed: true`). 6/47 models are never silently applied
to 6/45. Any change gives a new digest, so revisions are new protocols.

## Commands

```bash
uv run lotto prospective protocol data/prospective/reviewed-protocol.json
uv run lotto prospective issue data/prospective/<digest> --target-date 2026-10-12 --arm uniform
uv run lotto data batch data/batches/<results>/batch.json
uv run lotto prospective evaluate data/prospective/<digest>
uv run lotto prospective report data/prospective/<digest>
```

`issue` runs in one transaction. It takes the draw advisory lock (the same lock
that canonical ingestion takes), reads `clock_timestamp()` after acquiring it,
and refuses unscheduled dates, dates before the start and dates without a
single covering verified rule. If a result already exists it records
`missed: result_available`. At or after the deadline it records
`missed: deadline_passed`. Otherwise it inserts complete eligible portfolios
(seeded uniform lines; at pool 45, numbers 46/47 never appear). Repeating the
call returns the existing identical issue. Generation errors are recorded as
`failed`. Missed and failed records are never backfilled. All prospective rows
reject UPDATE/DELETE.

`evaluate` scores lines only against accepted, evidence-backed results.
Quarantined results count as disputed. A corrected accepted result (new
evidence key) appends a new revision, and issued lines never change. Re-running
is idempotent.

`report` shows, per arm: scheduled dates since the start (denominator),
coverage (completed / pending / disputed / missed / failed / unrecorded) and
completed-issue performance from the latest revisions. Missed issues are never
scored as losses. The default review window is 100 completed draws. The report
is descriptive: it makes no confirmatory claim without a separately reviewed
power and stopping protocol.

No scheduler, browser automation, purchase, payment or ticket submission is
created. Results refresh through permitted offline imports only.

## Real run status (10 October 2026)

- Protocol `3152d204…` runs under 6/45-2026 with a single uniform arm
  (ruling 35).
- Three issues are recorded: 12, 14 and 17 October 2026, 48 lines in total.
- `lotto prospective evaluate` and `lotto prospective report` were both run.
  All 48 lines are pending, with 0 completed draws, because none of the
  target draws has happened yet.
- The review window is 100 completed draws, about eight months at three
  draws a week. Phase 6 is an ongoing process by design. Results can be
  added only after each draw, never before (ruling 40).

The cycle after each draw is:

```bash
uv run lotto data collect
uv run lotto prospective evaluate data/prospective/<protocol>
uv run lotto prospective report data/prospective/<protocol>
uv run lotto prospective issue ...   # the next draw, before 19:45 Europe/Dublin
```
