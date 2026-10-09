# Phase 2 measured coverage

As of 10 October 2026, the full main-Lotto draw history has been backfilled by
the repository's own ingestion (`lotto data collect`), and an audited snapshot
exists.

| Dataset | Research database coverage | Source / remaining gap |
|---|---|---|
| Accepted dated draws | 3,909, from 16 April 1988 to 7 October 2026 | lotto.net yearly archives (ruling 23) |
| Staged dated draws | 1 (Wednesday 1 November 2006) | Exact 6/42 to 6/45 switch date unverified (ruling 25) |
| Draws with bonus | 3,566 | Lotto had no bonus before 22 August 1992 |
| Draws with jackpot amount | 2,589 (euro era only) | Pre-2002 converted amounts are not imported (ruling 27) |
| Draws with jackpot outcome (Won/Roll) | 1,703 | Only where the archive marks the outcome |
| Verified rule intervals | 7: 6/36 Saturday-only, 6/36, 6/39, 6/42, 6/45, 6/47 and 6/45-2026 | Wikipedia (CC BY-SA) and the 2015 trade announcement |
| Reviewed schedule exceptions | 23 calendar events | Christmas and moved draws, bound to archive evidence |
| Prize breakdowns | 0 | lotto.net per-draw pages exist, at about 3,900 requests (≈5.5 h at the crawl delay); not needed for training |
| Undated 6/42 combinations | 264 (journal dataset) | Kept staged; no individual draw dates |
| Official period metrics | 112 annual all-games metrics | Regulator and C&AG; not draw-level |

Draws per rule regime in the snapshot: 6/36-saturday 111, 6/36 232, 6/39 218,
6/42 1,263, 6/45 922, 6/47 1,148, 6/45-2026 15.

## Snapshot

`lotto audit report` for 1988-04-16 to 2026-10-09 includes all 3,909 draws,
excludes none, finds no missing or unexpected scheduled dates and is
`snapshot_ready`. The bundle is
`data/snapshots/a3ea572d5deacd3cd80336a8cc682d55f4e8c25c4979b789c9b8572d1744766d`.

## Source policy

- Allowed: lotto.net (disclaimer allows personal use; no harvesting
  prohibition; robots.txt allows the paths). Requests use a 5-second crawl
  delay. Past years are cached and never refetched.
- Restricted (terms prohibit harvesting or require permission):
  irish.national-lottery.com, irishlottery.com, lottery.co.uk, lottery.ie.
  `AccessPolicy` refuses these hosts.
- All fetched evidence, the database and snapshots stay under `data/`, which is
  git-ignored and never pushed.

## Reproduce

```bash
uv run lotto data collect
uv run lotto data enrich data/raw/backfill-import/manifest.json data/reviews/calendar-exceptions.json
uv run lotto audit snapshot --start 1988-04-16 --end 2026-10-09 --evidence-root data --bindings data/reviews/rule-bindings.json
```

Phase 2's formal completion still lists prize breakdowns as outstanding, along
with the backup/restore review.
