# Phase 2 implementation decisions

This is the verified ingestion-foundation milestone, not completion of historical
acquisition. A fresh reviewer found no critical issues and six important issues;
the final implementation addresses each with focused regressions and the full
suite. Source-policy restrictions remain an acquisition constraint.

## Rulings made

- Use the existing approved feature branch in the shared checkout, consistent
  with phase 1. Cost if wrong: less filesystem isolation than a separate worktree;
  the branch preserves a separate reviewable history.
- Keep the small adapters together in parsers.py and access policy in fetch.py,
  rather than the plan's separate files. Cost if wrong: refactor if adapters grow.
- Disable automated acquisition from reviewed restricted archives/operator hosts.
  Cost: the historical backfill cannot run until permitted exports or source
  permission are available; phase 2 remains incomplete.
- Use curated, hash-pinned government report facts and manual complementary
  imports for this milestone. Cost: two annual metrics collected; story discovery
  and comprehensive report-table extraction are still unavailable.
- Merge the tested foundation under the user's authorized workflow while keeping
  data completion gates explicit. Cost: modelling cannot begin from the currently
  empty draw dataset.

## Review outcomes

The parser now verifies main-game context and rejects ambiguous detail lists.
Resolved number disagreements survive replay. Disputed prize tiers are excluded
from totals and prize semantics participate in reconciliation. A compatible,
more complete single observation can replace partial enrichment with its own
lineage. Coverage includes staged observations by source/game/year/status.
Artifacts and observations validate source identities before import mutation.
Malformed CSV rows are controlled errors; cash subtotals without known cash
tiers remain unknown.

The reviewer set aside full historical collection, historical rule-date accuracy,
independent legal interpretation, model quality/betting/external features and
concurrent writers. The rulings stand: collection is incomplete; no rule dates or
models are claimed; source access follows the reviewed policy; ingestion is
sequential. Costs are unavailable draw data and unsupported later/concurrent work.
There are no deferred minor findings from this review.

Verification: 89 tests pass against the isolated PostgreSQL test service. Ruff
lint/format and Git whitespace checks pass. Research database runtime checks,
repeat official-metric import and backup restore passed. The restored database
contains migration 0002, two annual metrics and 14,162 unknown-schedule dates.
Post-merge checks must pass before pushing.
