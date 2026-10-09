# Phase 2 measured coverage

As of 9 October 2026: ingestion foundation implemented; historical acquisition
incomplete. No historical draw dataset is present in the research database.

| Dataset | Research database coverage | Reason / next input |
|---|---|---|
| Accepted / staged draws | 0 / 0 | A permitted draw export or collection source is required |
| Prizes / jackpots | 0 / 0 | Depend on draw/source evidence |
| Verified rule intervals / attributes | 0 / 0 | Require reviewed dated evidence; no guessed intervals seeded |
| Calendar dates | 14,162 dates, 1988-01-01 through 2026-10-09 | All schedules unknown; no accepted draws observed |
| Public winning-ticket metadata | 0 | Operator story harvesting disabled; curated import available |
| Official period metrics | 2 metrics for 2021, all National Lottery games | Online sales share and prizes won as share of ticket sales |
| Derived number / prize / rollover rows | 0 | No accepted draw input |

The official metrics come from the [Comptroller and Auditor General report,
chapter 19](https://www.audit.gov.ie/en/find-report/publications/2022/19-exchequer-receipts-from-national-lottery-ticket-sales.pdf),
paragraphs 19.10 and 19.11. [The government catalogue](https://data.gov.ie/dataset/exchequer-receipts-from-national-lottery-ticket-sales)
declares CC BY 4.0. Values are 16.6% online sales and 55.6% prizes won / ticket
sales. They describe annual all-games activity and cannot be assigned to an
individual Lotto draw. Exact publication time is unknown. The PDF, catalogue
metadata, URL, retrieval time and SHA-256 are saved locally.

## Acquisition limits discovered

The [historical archive terms](https://irish.national-lottery.com/terms), section
3.1.7, prohibit harvesting; [the alternative publisher's terms](https://www.irishlottery.com/terms-and-conditions)
contain the same restriction. [Operator terms](https://www.lottery.ie/legal/terms-and-conditions)
permit personal reference but require permission for extraction/integration.
Those hosts are disabled for automated ingestion. Existing small discovery
snapshots remain local and were not ingested as a historical dataset.

Other candidates did not provide an accessible approved export: PickMySix and
the author-shared S3 JSON returned 403, while a CSV provider required an account.
No account was created and no access restriction was bypassed. A government
catalogue search found no draw-result dataset. The previously described external
527-draw collection is not in this repository.

## Remaining completion gates

Obtain permitted draw exports and dated rule evidence; import/backfill them;
measure actual year/regime/field completeness; compare overlapping sources;
reconstruct in the test database; and preserve evidence/database backups. Prize,
rule and jackpot acquisition are mandatory phase 2 deliverables, so phase 2 is
not complete. Model training remains deferred. Public stories and additional
official report metrics remain best-effort acquisitions.

Operational JSON is generated with `lotto data report`; it is intentionally
ignored rather than committed as a misleading permanent snapshot.
