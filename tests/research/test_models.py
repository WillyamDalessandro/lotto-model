import numpy as np
import pytest

from lotto_model.research import models
from lotto_model.research.features import target_features, training_rows
from lotto_model.research.models import (
    CANDIDATES,
    fit_candidate,
    predict_marginals,
)
from lotto_model.research.selection import CandidateScore, select_candidate


def test_fixed_grid_and_fit_scope(research_draws):
    assert [c.identifier for c in CANDIDATES] == [
        "logistic-c0.01",
        "logistic-c0.1",
        "logistic-c1",
        "boosting-leaves3",
        "boosting-leaves7",
        "boosting-leaves15",
    ]
    draws = research_draws(200)
    features, y = training_rows(draws, 175)
    for config in (CANDIDATES[0], CANDIDATES[3]):
        model = fit_candidate(config, features, y, 5)
        p = predict_marginals(model, target_features(draws, 175))
        assert p.shape == (47,) and np.all((p >= 0) & (p <= 1))
    scaler = fit_candidate(CANDIDATES[0], features, y, 5).estimator["scale"]
    assert np.allclose(scaler.mean_, features.values.mean(axis=0))
    with pytest.raises(ValueError, match="single class"):
        fit_candidate(CANDIDATES[0], features, np.zeros_like(y), 5)


def test_nonconvergence_fails(research_draws, monkeypatch):
    from sklearn.exceptions import ConvergenceWarning

    draws = research_draws(180)
    features, y = training_rows(draws, 175)

    class Never:
        def fit(self, *args):
            import warnings

            warnings.warn("no", ConvergenceWarning)

    monkeypatch.setattr(models, "_estimator", lambda config, seed: Never())
    with pytest.raises(ValueError, match="converge"):
        fit_candidate(CANDIDATES[0], features, y, 5)


def test_selection_tie_breaks():
    def score(name, rate, brier, loss):
        return CandidateScore(name, 50, int(rate * 50), rate, brier, loss)

    assert (
        select_candidate([score("b", 0.1, 0.2, 0.3), score("a", 0.12, 0.3, 0.3)]) == "a"
    )
    assert (
        select_candidate([score("b", 0.1, 0.2, 0.3), score("a", 0.1, 0.25, 0.1)]) == "b"
    )
    assert (
        select_candidate([score("b", 0.1, 0.2, 0.3), score("a", 0.1, 0.2, 0.4)]) == "b"
    )
    assert (
        select_candidate([score("b", 0.1, 0.2, 0.3), score("a", 0.1, 0.2, 0.3)]) == "a"
    )
    with pytest.raises(ValueError):
        select_candidate(
            [score("a", 0.1, 0.2, 0.3), CandidateScore("b", 49, 1, 0.1, 0.2, 0.3)]
        )
