"""Seeded random-portfolio null simulations on development targets only."""

import os
from concurrent.futures import ProcessPoolExecutor
from math import sqrt

import numpy as np

from lotto_model.research.backtest import check_population, development_targets
from lotto_model.research.contracts import Protocol, ResearchDraw
from lotto_model.research.odds import p_at_least
from lotto_model.research.policies import derive_seed, uniform_portfolio

POLICY = "uniform_simulation"


def tolerance(p: float, trials: int) -> float:
    """Predeclared numerical validation band, not a significance test."""
    return 5 * sqrt(p * (1 - p) / trials) + 1 / trials


def _simulation_range(key, outcomes, start: int, stop: int):
    """Hit counts for simulations start..stop-1; each seed is independent."""
    digest, root_seed, pool, budget, dates = key
    hits3 = np.zeros(stop - start, dtype=np.int64)
    hits5 = np.zeros(stop - start, dtype=np.int64)
    for s in range(start, stop):
        for draw_date, outcome in zip(dates, outcomes):
            seed = derive_seed(digest, POLICY, draw_date, budget, s, root_seed)
            best = max(
                len(outcome.intersection(line))
                for line in uniform_portfolio(pool, budget, seed)
            )
            hits3[s - start] += best >= 3
            hits5[s - start] += best >= 5
    return hits3, hits5


def _simulate(key, outcomes, simulations: int, workers: int | None):
    """Split simulations across processes; results equal a sequential run."""
    workers = workers or min(os.cpu_count() or 1, 8)
    if workers <= 1 or simulations < 100:
        return _simulation_range(key, outcomes, 0, simulations)
    edges = np.linspace(0, simulations, workers + 1).astype(int)
    with ProcessPoolExecutor(workers) as pool:
        parts = list(
            pool.map(
                _simulation_range,
                [key] * workers,
                [outcomes] * workers,
                edges[:-1].tolist(),
                edges[1:].tolist(),
            )
        )
    return (
        np.concatenate([a for a, _ in parts]),
        np.concatenate([b for _, b in parts]),
    )


def simulate_baselines(
    protocol: Protocol,
    draws: list[ResearchDraw],
    simulations: int | None = None,
    budgets: tuple[int, ...] | None = None,
    workers: int | None = None,
) -> dict:
    check_population(protocol, draws)
    simulations = protocol.simulations if simulations is None else simulations
    if simulations < 1:
        raise ValueError("At least one simulation is required")
    targets = [draws[i] for i in development_targets(protocol)]
    outcomes = [set(d.mains) for d in targets]
    p3 = float(p_at_least(protocol.pool, 3))
    p5 = float(p_at_least(protocol.pool, 5))
    output = dict(
        simulations=simulations,
        target_draws=len(targets),
        first_date=targets[0].draw_date.isoformat(),
        last_date=targets[-1].draw_date.isoformat(),
        exact_line_p3=p3,
        exact_line_p5=p5,
        budgets={},
    )
    dates = [d.draw_date for d in targets]
    for budget in budgets or protocol.budgets:
        hits3, hits5 = _simulate(
            (protocol.digest, protocol.root_seed, protocol.pool, budget, dates),
            outcomes,
            simulations,
            workers,
        )
        trials = simulations * len(targets)
        rates = hits3 / len(targets)
        result = dict(
            trials=trials,
            any_line_hit_3_plus=dict(
                events=int(hits3.sum()), rate=hits3.sum() / trials
            ),
            any_line_hit_5_plus=dict(
                events=int(hits5.sum()), rate=hits5.sum() / trials
            ),
            per_simulation_rate_3_plus=dict(
                mean=float(rates.mean()),
                q025=float(np.quantile(rates, 0.025)),
                q500=float(np.quantile(rates, 0.5)),
                q975=float(np.quantile(rates, 0.975)),
            ),
        )
        if budget == 1:
            band = tolerance(p3, trials)
            difference = abs(hits3.sum() / trials - p3)
            result["reconciliation"] = dict(
                exact=p3,
                tolerance=band,
                absolute_difference=float(difference),
                passed=bool(difference <= band),
            )
        output["budgets"][str(budget)] = result
    return output
