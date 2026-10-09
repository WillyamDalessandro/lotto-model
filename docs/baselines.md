# Frozen protocol and baselines

Status: software implemented and tested on synthetic snapshots. No real protocol
has been frozen because no audited historical snapshot exists. No holdout result
exists or is produced by these commands.

## Commands

```bash
uv run lotto research protocol data/snapshots/<content_sha256> --rule-code 6/47
uv run lotto research baselines data/experiments/<protocol_digest> --snapshot data/snapshots/<content_sha256>
```

`protocol` verifies the snapshot, reads one regime and writes
`data/experiments/<protocol_digest>/protocol.json` (canonical JSON; the
directory name is its SHA-256). Fewer than 282 eligible draws, mixed regimes or
fewer than two full validation blocks fail with `insufficient_data`. Freezing
the same inputs again reuses the directory; changed bytes are rejected.

`baselines` reloads and re-verifies the protocol and snapshot (both must match),
runs the uniform and smoothed-frequency baselines at budgets 1/5/10 on
development folds only, and runs seeded uniform null simulations (10,000 by
default; `--simulations N` writes a separate non-official result directory).
Outputs are write-once under `<protocol>/baselines/simulations-<N>/`.

Runtime note: simulations create one seeded generator per simulation, target
and budget. Expect roughly 0.4 ms per simulation-target across the three
budgets (about 3.5 minutes per 100 development targets at 10,000 simulations).

## Frozen choices (version 1)

- Population: one verified regime, pool 47, chronological; `gap_before` marks a
  missing scheduled draw (from the audit) before a draw.
- Holdout: final `ceil(0.20 n)` draws, computed with integer arithmetic.
- Feature warmup 150, supervised warmup 25, validation from index 175 in
  25-target blocks; a final partial block is kept if it has at least 10 targets.
- Seeds: first 16 hex characters of SHA-256 over canonical JSON
  `[root_seed, protocol_digest, policy, target_date, budget, simulation_index]`,
  `root_seed = 20261009`, NumPy `PCG64`.
- Uniform portfolios: distinct uniformly random six-number lines (the six
  smallest of `pool` i.i.d. uniforms), duplicates rejected, 100,000-attempt cap.
- Frequency baseline: `p_j = (count_j + 6/47) / (history_count + 1)` over
  earlier observed draws; the one-line policy takes the six largest `p_j`
  (ties to smaller numbers). Larger budgets keep that line and add
  probability-weighted unique lines.
- Exact odds: `P(K=k) = C(6,k) C(N-6,6-k) / C(N,6)` as exact fractions. For
  N=47, `P(K>=3) = 75249/3579191 ≈ 0.021024`.
- Simulation reconciliation (budget 1): `|simulated - exact| <= 5
  sqrt(p(1-p)/trials) + 1/trials`, trials counting simulated target draws.

## Guarantees tested

Every prediction's `max_input_date` precedes its target; development commands
refuse holdout targets; changing future or holdout outcomes cannot change
earlier predictions; portfolios contain the exact number of unique valid lines;
seeds reproduce; metrics compare identical dates and budgets and count
any-line portfolio hits once per draw.

Statistical power is not established by these software checks. Phase 4A
(`docs/ai-model-research.md`) assesses whether the eligible sample can detect a
useful improvement before any protocol is frozen for real data.
