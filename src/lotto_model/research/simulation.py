"""Seeded random-portfolio null simulations on development targets only."""

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


def simulate_baselines(
    protocol: Protocol,
    draws: list[ResearchDraw],
    simulations: int | None = None,
    budgets: tuple[int, ...] | None = None,
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
    for budget in budgets or protocol.budgets:
        hits3 = np.zeros(simulations, dtype=np.int64)
        hits5 = np.zeros(simulations, dtype=np.int64)
        for s in range(simulations):
            for draw, outcome in zip(targets, outcomes):
                seed = derive_seed(
                    protocol.digest,
                    POLICY,
                    draw.draw_date,
                    budget,
                    s,
                    protocol.root_seed,
                )
                best = max(
                    len(outcome.intersection(line))
                    for line in uniform_portfolio(protocol.pool, budget, seed)
                )
                hits3[s] += best >= 3
                hits5[s] += best >= 5
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
