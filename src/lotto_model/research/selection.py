"""Chronological development scoring and deterministic candidate selection."""

from dataclasses import asdict, dataclass

import numpy as np

from lotto_model.research.backtest import check_population, development_targets
from lotto_model.research.contracts import PredictionRecord, Protocol, ResearchDraw
from lotto_model.research.features import labels, target_features, training_rows
from lotto_model.research.models import (
    CANDIDATES,
    CandidateConfig,
    fit_candidate,
    predict_marginals,
)
from lotto_model.research.policies import derive_seed, top_line, weighted_portfolio

EPSILON = 1e-15


@dataclass(frozen=True)
class CandidateScore:
    candidate: str
    targets: int
    hit_3_plus: int
    hit_3_plus_rate: float
    brier: float
    log_loss: float


def require_candidate_protocol(protocol: Protocol):
    """Candidates need 25 supervised draws before the first common target."""
    if (
        protocol.validation_start
        != protocol.feature_warmup + protocol.supervised_warmup
        or not protocol.folds
        or protocol.folds[0].start != protocol.validation_start
        or protocol.development[1] < 225
    ):
        raise ValueError("Protocol lacks candidate training boundaries; revise it")


def brier_and_log_loss(probabilities: np.ndarray, outcome: np.ndarray):
    clipped = np.clip(probabilities, EPSILON, 1 - EPSILON)
    brier = float(np.mean((probabilities - outcome) ** 2))
    loss = float(
        -np.mean(outcome * np.log(clipped) + (1 - outcome) * np.log(1 - clipped))
    )
    return brier, loss


def model_seed(protocol: Protocol, candidate: CandidateConfig, target_date) -> int:
    return derive_seed(
        protocol.digest, candidate.identifier, target_date, 0, 0, protocol.root_seed
    )


def predict_target(protocol, draws, index, candidate, cache=None):
    """Fit on supervised rows strictly before index, then predict that target."""
    target = draws[index]
    features, y = training_rows(draws, index, protocol.feature_warmup, cache)
    model = fit_candidate(
        candidate, features, y, model_seed(protocol, candidate, target.draw_date)
    )
    batch = (
        cache[index]
        if cache is not None and index in cache
        else target_features(draws, index)
    )
    return predict_marginals(model, batch), batch.max_input_date


def candidate_records(
    protocol, candidate_id, target_date, budget, probabilities, cutoff
):
    seed = derive_seed(
        protocol.digest, candidate_id, target_date, budget, 0, protocol.root_seed
    )
    lines = (
        (top_line(probabilities),)
        if budget == 1
        else weighted_portfolio(probabilities, budget, seed)
    )
    return [
        PredictionRecord(
            protocol_digest=protocol.digest,
            snapshot_digest=protocol.snapshot_digest,
            target_date=target_date,
            policy=candidate_id,
            budget=budget,
            line_index=k,
            mains=line,
            seed=None if budget == 1 else seed,
            max_input_date=cutoff,
        )
        for k, line in enumerate(lines)
    ]


def develop(
    protocol: Protocol,
    draws: list[ResearchDraw],
    candidates=CANDIDATES,
) -> dict:
    """Score every fixed candidate on the common development targets."""
    check_population(protocol, draws)
    require_candidate_protocol(protocol)
    indices = development_targets(protocol)
    cache = {}
    scores, records, probabilities = [], [], {}
    for candidate in candidates:
        hits, briers, losses = 0, [], []
        for index in indices:
            target = draws[index]
            p, cutoff = predict_target(protocol, draws, index, candidate, cache)
            brier, loss = brier_and_log_loss(p, labels(target))
            briers.append(brier)
            losses.append(loss)
            hits += len(set(top_line(p)) & set(target.mains)) >= 3
            probabilities[(candidate.identifier, target.draw_date)] = p
            for budget in protocol.budgets:
                records += candidate_records(
                    protocol, candidate.identifier, target.draw_date, budget, p, cutoff
                )
        scores.append(
            CandidateScore(
                candidate=candidate.identifier,
                targets=len(indices),
                hit_3_plus=hits,
                hit_3_plus_rate=hits / len(indices),
                brier=float(np.mean(briers)),
                log_loss=float(np.mean(losses)),
            )
        )
    return dict(
        scores=[asdict(s) for s in scores],
        selected=select_candidate(scores),
        records=records,
        probabilities=probabilities,
    )


def select_candidate(scores: list[CandidateScore]) -> str:
    """Highest 3-plus rate, then lowest Brier, log loss, then identifier."""
    if not scores:
        raise ValueError("No candidate scores")
    if len({s.targets for s in scores}) != 1:
        raise ValueError("Candidates were scored on different populations")
    best = min(
        scores, key=lambda s: (-s.hit_3_plus_rate, s.brier, s.log_loss, s.candidate)
    )
    return best.candidate
