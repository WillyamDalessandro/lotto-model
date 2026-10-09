"""Inference interface: verified pre-draw history in, six eligible mains out."""

from datetime import date

from lotto_model.research.contracts import ResearchDraw
from lotto_model.research.features import (
    FEATURE_COLUMNS,
    feature_rows,
    training_rows,
)
from lotto_model.research.models import config_from_id, fit_candidate, predict_marginals
from lotto_model.research.policies import derive_seed, top_line


def predict_next(
    frozen: dict,
    history: list[ResearchDraw],
    target_date: date,
    pool: int,
    target_gap: bool = False,
    warmup: int = 150,
    root_seed: int = 20261009,
) -> dict:
    """Refit the frozen configuration on verified history; never loads pickles."""
    if frozen["feature_columns"] != list(FEATURE_COLUMNS):
        raise ValueError("Frozen feature schema differs from this version")
    if not history or history[-1].draw_date >= target_date:
        raise ValueError("History must precede the target draw")
    if any(d.pool != pool for d in history):
        raise ValueError("History does not match the effective rule pool")
    if len(history) < warmup + 25:
        raise ValueError("Insufficient verified history for this configuration")
    candidate = config_from_id(frozen["selected"]["id"])
    features, y = training_rows(history, len(history), warmup)
    seed = derive_seed(
        frozen["protocol_digest"], candidate.identifier, target_date, 0, 0, root_seed
    )
    model = fit_candidate(candidate, features, y, seed)
    probabilities = predict_marginals(
        model, feature_rows(history, target_date, pool, target_gap)
    )
    mains = top_line(probabilities)
    if any(not 1 <= n <= pool for n in mains):
        raise ValueError("Ineligible prediction")
    return dict(
        target_date=target_date.isoformat(),
        mains=list(mains),
        probabilities=[float(p) for p in probabilities],
        cutoff=history[-1].draw_date.isoformat(),
        model=candidate.identifier,
        protocol_digest=frozen["protocol_digest"],
        snapshot_digest=frozen["snapshot_digest"],
        pool=pool,
        note="Research output; marginal probabilities, not betting advice.",
    )
