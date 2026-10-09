"""Shared research contracts carried from Phase 4 baselines into Phase 5."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lotto_model.audit.contracts import canonical_json, sha256

PROTOCOL_VERSION = 1
ROOT_SEED = 20261009
BUDGETS = (1, 5, 10)
SIMULATIONS = 10_000


@dataclass(frozen=True)
class ResearchDraw:
    """One verified draw; gap_before marks a missing scheduled draw before it."""

    draw_date: date
    rule_code: str
    pool: int
    mains: tuple[int, ...]
    gap_before: bool = False


class Fold(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int
    end: int
    first_date: date
    last_date: date


class Protocol(BaseModel):
    """Every frozen choice; any change produces a different digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = PROTOCOL_VERSION
    revision: int = Field(default=0, ge=0)
    revision_reason: str | None = None
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_code: str
    pool: Literal[47]
    population: int
    dates: tuple[date, ...]
    development: tuple[int, int]
    holdout: tuple[int, int]
    holdout_first_date: date
    holdout_last_date: date
    feature_warmup: int = 150
    supervised_warmup: int = 25
    validation_start: int = 175
    block_size: int = 25
    minimum_partial_block: int = 10
    minimum_population: int = 282
    folds: tuple[Fold, ...]
    budgets: tuple[int, ...] = BUDGETS
    primary: str = "one_line_hit_3_plus"
    secondary: tuple[str, ...] = ("hit_5_plus", "portfolio_any_line_budget_5_10")
    root_seed: int = ROOT_SEED
    simulations: int = SIMULATIONS
    frequency_prior: str = "p_j=(count_j+6/47)/(history_count+1)"
    line_policy: str = (
        "budget 1: six largest p_j, ties to smaller numbers; budget>1: that line "
        "plus probability-weighted unique lines, 100000-attempt cap"
    )
    candidate_grid: dict = Field(
        default_factory=lambda: {
            "logistic_c": [0.01, 0.1, 1.0],
            "boosting_max_leaf_nodes": [3, 7, 15],
        }
    )
    selection: str = (
        "highest pooled development one-line 3-plus rate, then lowest Brier, then "
        "lowest log loss, then stable candidate identifier"
    )
    retraining: str = "expanding history, refit for every target"
    uncertainty: str = (
        "95% Clopper-Pearson rate interval minus exact p0; 10000 paired draw "
        "bootstrap replicates; circular block length 5 sensitivity; 10000 null "
        "refits; Holm adjustment over secondary comparisons"
    )

    @model_validator(mode="after")
    def consistent(self):
        n = self.population
        if len(self.dates) != n or list(self.dates) != sorted(set(self.dates)):
            raise ValueError("Protocol dates must be unique, ordered and complete")
        if self.development != (0, self.holdout[0]) or self.holdout[1] != n:
            raise ValueError("Development must precede the locked holdout")
        if any(f.end > self.development[1] for f in self.folds):
            raise ValueError("Validation folds must stay within development")
        return self

    def payload(self) -> dict:
        return self.model_dump(mode="json")

    @property
    def digest(self) -> str:
        return sha256(canonical_json(self.payload()))


def _six(mains) -> tuple[int, ...]:
    values = tuple(sorted(mains))
    if len(values) != 6 or len(set(values)) != 6:
        raise ValueError("A line requires six distinct numbers")
    return values


class PredictionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_digest: str
    snapshot_digest: str
    target_date: date
    policy: str
    budget: int = Field(ge=1)
    line_index: int = Field(ge=0)
    mains: tuple[int, ...]
    seed: int | None
    max_input_date: date

    @model_validator(mode="after")
    def valid(self):
        object.__setattr__(self, "mains", _six(self.mains))
        if self.max_input_date >= self.target_date:
            raise ValueError("Inputs must precede the target draw")
        if self.line_index >= self.budget:
            raise ValueError("Line index exceeds budget")
        return self


class EvaluatedRecord(BaseModel):
    """Outcome attached separately; the issued prediction is never edited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prediction: PredictionRecord
    outcome: tuple[int, ...]
    matched_mains: int = Field(ge=0, le=6)
    hit_3_plus: bool
    hit_5_plus: bool
