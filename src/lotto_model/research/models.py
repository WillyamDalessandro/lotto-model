"""The six fixed Phase 5 candidates; no further search or calibration."""

import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from lotto_model.research.features import FEATURE_COLUMNS, FeatureBatch


@dataclass(frozen=True)
class CandidateConfig:
    family: Literal["logistic", "boosting"]
    value: float

    @property
    def identifier(self) -> str:
        if self.family == "logistic":
            return f"logistic-c{self.value:g}"
        return f"boosting-leaves{int(self.value)}"

    def as_dict(self) -> dict:
        return dict(family=self.family, value=self.value, id=self.identifier)


CANDIDATES = (
    *(CandidateConfig("logistic", c) for c in (0.01, 0.1, 1.0)),
    *(CandidateConfig("boosting", n) for n in (3, 7, 15)),
)


def config_from_id(identifier: str) -> CandidateConfig:
    for config in CANDIDATES:
        if config.identifier == identifier:
            return config
    raise ValueError("Unknown candidate configuration")


@dataclass
class FittedCandidate:
    config: CandidateConfig
    estimator: object
    training_rows: int
    max_input_date: object


def _estimator(config: CandidateConfig, seed: int):
    if config.family == "logistic":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(C=config.value, solver="lbfgs", max_iter=2000),
                ),
            ]
        )
    return HistGradientBoostingClassifier(
        max_leaf_nodes=int(config.value),
        max_iter=100,
        learning_rate=0.05,
        min_samples_leaf=47,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=seed % (2**32),
    )


def fit_candidate(
    config: CandidateConfig, features: FeatureBatch, labels: np.ndarray, seed: int
) -> FittedCandidate:
    """Fit on training rows only; nonconvergence or one class fails visibly."""
    if features.columns != FEATURE_COLUMNS:
        raise ValueError("Feature schema differs from the frozen definition")
    if len(features.values) != len(labels) or len(labels) == 0:
        raise ValueError("Feature and label counts differ")
    if len(np.unique(labels)) != 2:
        raise ValueError("Training labels contain a single class")
    if not np.all(np.isfinite(features.values)):
        raise ValueError("Non-finite training features")
    estimator = _estimator(config, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            estimator.fit(features.values, labels)
        except ConvergenceWarning as exc:
            raise ValueError(f"{config.identifier} did not converge") from exc
    return FittedCandidate(config, estimator, len(labels), features.max_input_date)


def predict_marginals(model: FittedCandidate, features: FeatureBatch) -> np.ndarray:
    """Per-number inclusion probabilities; not a joint combination model."""
    if features.columns != FEATURE_COLUMNS:
        raise ValueError("Feature schema differs from the frozen definition")
    if features.max_input_date < model.max_input_date:
        raise ValueError("Prediction features precede the training cutoff")
    probabilities = model.estimator.predict_proba(features.values)[:, 1]
    if not np.all((probabilities >= 0) & (probabilities <= 1)):
        raise ValueError("Invalid probability")
    return probabilities
