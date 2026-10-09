"""Chronological development predictions and outcome evaluation."""

from lotto_model.research.contracts import (
    EvaluatedRecord,
    PredictionRecord,
    Protocol,
    ResearchDraw,
)
from lotto_model.research.policies import (
    derive_seed,
    frequency_portfolio,
    uniform_portfolio,
)

BASELINES = ("uniform", "frequency")


def development_targets(protocol: Protocol) -> list[int]:
    return [i for fold in protocol.folds for i in range(fold.start, fold.end)]


def check_population(protocol: Protocol, draws: list[ResearchDraw]):
    if tuple(d.draw_date for d in draws) != protocol.dates:
        raise ValueError("Draws differ from the frozen protocol population")
    if any(d.rule_code != protocol.rule_code or d.pool != protocol.pool for d in draws):
        raise ValueError("Draws differ from the protocol regime")


def baseline_lines(protocol, history, policy, target_date, budget, simulation=0):
    seed = derive_seed(
        protocol.digest, policy, target_date, budget, simulation, protocol.root_seed
    )
    if policy == "uniform":
        return seed, uniform_portfolio(protocol.pool, budget, seed)
    if policy == "frequency":
        return seed, frequency_portfolio(history, budget, seed, protocol.pool)
    raise ValueError("Unknown baseline policy")


def predict(
    protocol: Protocol,
    draws: list[ResearchDraw],
    policy: str,
    budget: int,
    indices: list[int],
    *,
    allow_holdout: bool = False,
) -> list[PredictionRecord]:
    """Issue lines for target indices using only strictly earlier draws."""
    check_population(protocol, draws)
    if budget not in protocol.budgets:
        raise ValueError("Budget not in frozen protocol")
    holdout_start = protocol.development[1]
    if any(i >= holdout_start for i in indices) and not allow_holdout:
        raise ValueError("Holdout evaluation is refused during development")
    if any(i < 1 or i >= protocol.population for i in indices):
        raise ValueError("Target index outside population")
    records = []
    for index in indices:
        target = draws[index]
        history = list(draws[:index])
        seed, lines = baseline_lines(
            protocol, history, policy, target.draw_date, budget
        )
        records.extend(
            PredictionRecord(
                protocol_digest=protocol.digest,
                snapshot_digest=protocol.snapshot_digest,
                target_date=target.draw_date,
                policy=policy,
                budget=budget,
                line_index=k,
                mains=line,
                seed=seed,
                max_input_date=history[-1].draw_date,
            )
            for k, line in enumerate(lines)
        )
    return records


def run_development(
    protocol: Protocol, draws: list[ResearchDraw], policy: str, budget: int
) -> list[PredictionRecord]:
    return predict(protocol, draws, policy, budget, development_targets(protocol))


def evaluate(
    predictions: list[PredictionRecord], targets: list[ResearchDraw]
) -> list[EvaluatedRecord]:
    """Attach outcomes in new records; predictions stay unchanged."""
    outcomes = {d.draw_date: d.mains for d in targets}
    evaluated = []
    for prediction in predictions:
        if prediction.target_date not in outcomes:
            raise ValueError("Missing outcome for a prediction")
        outcome = outcomes[prediction.target_date]
        matched = len(set(prediction.mains) & set(outcome))
        evaluated.append(
            EvaluatedRecord(
                prediction=prediction,
                outcome=tuple(sorted(outcome)),
                matched_mains=matched,
                hit_3_plus=matched >= 3,
                hit_5_plus=matched >= 5,
            )
        )
    return evaluated
