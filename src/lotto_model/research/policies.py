"""Seeded uniform and smoothed-frequency baseline portfolios."""

from math import comb

import numpy as np

from lotto_model.audit.contracts import canonical_json, sha256
from lotto_model.research.contracts import ROOT_SEED, ResearchDraw

ATTEMPT_CAP = 100_000


def derive_seed(
    protocol_digest: str,
    policy: str,
    target_date,
    budget: int,
    simulation_index: int,
    root_seed: int = ROOT_SEED,
) -> int:
    """First 16 hex characters of SHA-256 over canonical JSON inputs."""
    payload = [
        root_seed,
        protocol_digest,
        policy,
        target_date.isoformat(),
        budget,
        simulation_index,
    ]
    return int(sha256(canonical_json(payload))[:16], 16)


def _check(pool: int, budget: int):
    if pool < 6 or budget < 1 or budget > comb(pool, 6):
        raise ValueError("Impossible portfolio budget for this pool")


def _collect(budget, draw_line, initial=()):
    lines = list(initial)
    seen = set(lines)
    attempts = 0
    while len(lines) < budget:
        attempts += 1
        if attempts > ATTEMPT_CAP:
            raise ValueError("Portfolio attempt cap reached")
        line = draw_line()
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return tuple(lines)


def uniform_portfolio(pool: int, budget: int, seed: int) -> tuple[tuple[int, ...], ...]:
    """Distinct uniformly sampled six-number lines (duplicate lines rejected)."""
    _check(pool, budget)
    rng = np.random.Generator(np.random.PCG64(seed))

    def draw_line():
        # The six smallest of pool i.i.d. uniforms form a uniform 6-subset.
        chosen = np.argpartition(rng.random(pool), 6)[:6]
        return tuple(sorted(int(n) + 1 for n in chosen))

    return _collect(budget, draw_line)


def frequency_marginals(history: list[ResearchDraw], pool: int) -> np.ndarray:
    """p_j = (count_j + 6/pool) / (history_count + 1) over observed history only."""
    counts = np.zeros(pool)
    for draw in history:
        if draw.pool != pool:
            raise ValueError("History mixes rule regimes")
        for number in draw.mains:
            counts[number - 1] += 1
    return (counts + 6 / pool) / (len(history) + 1)


def top_line(scores) -> tuple[int, ...]:
    """Six largest scores; ties resolved toward smaller numbers."""
    order = sorted(range(len(scores)), key=lambda j: (-float(scores[j]), j))
    return tuple(sorted(j + 1 for j in order[:6]))


def frequency_portfolio(
    history: list[ResearchDraw], budget: int, seed: int, pool: int = 47
) -> tuple[tuple[int, ...], ...]:
    """Top-six line first; further lines weighted samples without replacement."""
    _check(pool, budget)
    weights = frequency_marginals(history, pool)
    return weighted_portfolio(weights, budget, seed)


def weighted_portfolio(weights, budget: int, seed: int) -> tuple[tuple[int, ...], ...]:
    weights = np.asarray(weights, dtype=float)
    pool = len(weights)
    _check(pool, budget)
    if np.any(weights < 0) or np.count_nonzero(weights) < 6:
        raise ValueError("Weights need at least six positive numbers")
    probabilities = weights / weights.sum()
    rng = np.random.Generator(np.random.PCG64(seed))

    def draw_line():
        chosen = rng.choice(pool, 6, replace=False, p=probabilities)
        return tuple(sorted(int(n) + 1 for n in chosen))

    return _collect(budget, draw_line, initial=(top_line(weights),))
