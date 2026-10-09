"""Frozen Phase 4 inference: exact-null intervals, bootstrap, nulls, Holm."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.stats import beta

from lotto_model.audit.contracts import canonical_json
from lotto_model.research.contracts import Protocol, ResearchDraw
from lotto_model.research.models import config_from_id
from lotto_model.research.odds import p_at_least
from lotto_model.research.policies import derive_seed, top_line
from lotto_model.research.selection import predict_target

FINAL_REPLICATES = 10_000


def clopper_pearson(events: int, trials: int, confidence: float = 0.95):
    if trials < 1 or not 0 <= events <= trials:
        raise ValueError("Invalid binomial counts")
    alpha = 1 - confidence
    lower = (
        0.0 if events == 0 else float(beta.ppf(alpha / 2, events, trials - events + 1))
    )
    upper = (
        1.0
        if events == trials
        else float(beta.ppf(1 - alpha / 2, events + 1, trials - events))
    )
    return lower, upper


def infer_primary(hits: list[bool], pool: int) -> dict:
    """Holdout one-line 3-plus rate against exact p0; interval minus p0."""
    p0 = float(p_at_least(pool, 3))
    events, trials = int(sum(hits)), len(hits)
    lower, upper = clopper_pearson(events, trials)
    return dict(
        events=events,
        trials=trials,
        rate=events / trials,
        p0=p0,
        rate_interval=[lower, upper],
        improvement=events / trials - p0,
        improvement_interval=[lower - p0, upper - p0],
        interval_excludes_zero=lower - p0 > 0,
    )


def paired_bootstrap(
    model_hits, baseline_hits, replicates: int, seed: int, block: int = 1
) -> dict:
    """Draw-level (optionally circular-block) bootstrap of paired differences."""
    model = np.asarray(model_hits, dtype=float)
    base = np.asarray(baseline_hits, dtype=float)
    if model.shape != base.shape or model.size == 0:
        raise ValueError("Paired series must share the same draws")
    n = model.size
    difference = model - base
    rng = np.random.Generator(np.random.PCG64(seed))
    blocks = -(-n // block)
    starts = rng.integers(0, n, size=(replicates, blocks))
    index = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    index = index.reshape(replicates, -1)[:, :n]
    means = difference[index].mean(axis=1)
    return dict(
        replicates=replicates,
        block_length=block,
        mean_difference=float(difference.mean()),
        interval=[float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
    )


def monte_carlo_p(observed: float, null_statistics) -> float:
    null = np.asarray(null_statistics, dtype=float)
    return float((1 + np.sum(null >= observed)) / (null.size + 1))


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjustment across one complete family."""
    ordered = sorted(pvalues.items(), key=lambda item: (item[1], item[0]))
    m, running, adjusted = len(ordered), 0.0, {}
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[name] = running
    return adjusted


def calibration_bins(probabilities, outcomes, bins: int = 10) -> list[dict]:
    """Equal-width [0,1] bins; the final bin includes probability 1."""
    p = np.asarray(probabilities, dtype=float).ravel()
    y = np.asarray(outcomes, dtype=float).ravel()
    edges = np.linspace(0, 1, bins + 1)
    which = np.minimum(np.floor(p * bins).astype(int), bins - 1)
    output = []
    for b in range(bins):
        mask = which == b
        output.append(
            dict(
                lower=float(edges[b]),
                upper=float(edges[b + 1]),
                count=int(mask.sum()),
                mean_probability=float(p[mask].mean()) if mask.any() else None,
                observed_rate=float(y[mask].mean()) if mask.any() else None,
            )
        )
    return output


def null_statistic(
    frozen: dict, protocol: Protocol, draws: list[ResearchDraw], replicate: int
) -> float:
    """Refit the frozen pipeline on one simulated uniform history."""
    rng = np.random.Generator(
        np.random.PCG64(
            derive_seed(
                protocol.digest,
                "null:" + frozen["selected"]["id"],
                protocol.holdout_first_date,
                1,
                replicate,
                protocol.root_seed,
            )
        )
    )
    simulated = [
        replace(
            d,
            mains=tuple(
                sorted(int(n) + 1 for n in np.argpartition(rng.random(d.pool), 6)[:6])
            ),
        )
        for d in draws
    ]
    candidate = config_from_id(frozen["selected"]["id"])
    cache, hits = {}, 0
    start, end = protocol.holdout
    for index in range(start, end):
        probabilities, _ = predict_target(protocol, simulated, index, candidate, cache)
        hits += len(set(top_line(probabilities)) & set(simulated[index].mains)) >= 3
    return hits / (end - start)


def run_null_replicates(
    frozen: dict,
    protocol: Protocol,
    draws: list[ResearchDraw],
    count: int,
    checkpoint_root: Path,
) -> dict:
    """Seed-indexed checkpoints: resumed runs equal uninterrupted ones."""
    checkpoint_root = Path(checkpoint_root)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    statistics = []
    for replicate in range(count):
        path = checkpoint_root / f"{replicate:05d}.json"
        if path.exists():
            value = json.loads(path.read_text())
            if value["replicate"] != replicate:
                raise ValueError("Corrupt null checkpoint")
        else:
            value = dict(
                replicate=replicate,
                statistic=null_statistic(frozen, protocol, draws, replicate),
            )
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(canonical_json(value))
            temporary.replace(path)
        statistics.append(value["statistic"])
    return dict(count=count, statistics=statistics, final=count >= FINAL_REPLICATES)
