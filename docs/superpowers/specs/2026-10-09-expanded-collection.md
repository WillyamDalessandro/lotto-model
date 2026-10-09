# Phase 2 collection continuation

This continues the approved historical-ingestion scope after the user's instruction
to continue collecting data. It does not change the model or purchase scope.

Collect two newly reviewed public sources for private, unpublished analysis:

- The JSE dataset submitted by Philip J. Boland and Yudi Pawitan contains 234
  student selections, 264 actual Irish Lotto 6/42 winning combinations, and 264
  simulations. Import only group 2, preserving original row order and the reported
  1994-09-24 to 1997-03-08 period. Individual dates and bonuses are absent: do not
  infer them or insert these records into canonical dated draws.
- RNL key commercial metrics contain five tables of annual all-games figures.
  Preserve section, original text, units, rounding precision and source identity.
  Convert amounts reported in millions to EUR with Decimal. Preserve contradictory
  statements in separate records and report conflicts by semantic metric and period.

Save bytes, retrieval timestamps, hashes, documentation and reviewed usage policies.
JSE allows teaching use with attribution and requires contributor consent for
published reuse; private analysis does not establish publication rights. RNL allows
attributed personal copies, prohibits commercial use/separate publication without
authorization, and reserves third-party rights. No open license is claimed. Raw
copies and database rows remain local and ignored; commit code and documentation
only. Fail closed if reviewed policy or academic documentation/data changes.

Use the existing bounded fetcher, transactions and ingestion schema. Undated results
remain staged with a missing-date quality issue, distinct from dated history and
excluded from derived time-series features. Identical replays must be idempotent;
changed payloads under the same evidence/parser/record identity must fail.

Success is measured by actual imported rows, conflict/missingness reports, repeat
collection without duplicates, live database health, and the full test suite.
Historical phase 2 remains incomplete until dated draw, rule, jackpot and prize
coverage are available. No restricted archive harvesting or invented dates.
