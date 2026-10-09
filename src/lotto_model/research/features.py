"""Leakage-safe per-number features computed only from earlier draws."""

from dataclasses import dataclass
from datetime import date

import numpy as np

from lotto_model.research.contracts import ResearchDraw

WINDOWS = (10, 25, 50, 100)
RECENCY_CAP = 100
FEATURE_COLUMNS = (
    *(f"freq_{w}" for w in WINDOWS),
    "recency",
    "never_seen",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_1_valid",
    "lag_2_valid",
    "lag_3_valid",
    "freq_10_minus_100",
    "smoothed_frequency",
    *(f"weekday_{d}" for d in range(7)),
    "days_since_prior",
)
FEATURE_VERSION = 1


@dataclass(frozen=True)
class FeatureBatch:
    """Rows ordered by number 1..pool (one target) or stacked targets."""

    columns: tuple[str, ...]
    values: np.ndarray
    max_input_date: date
    target_dates: tuple[date, ...]


def feature_rows(
    history: list[ResearchDraw],
    target_date: date,
    pool: int,
    target_gap: bool = False,
) -> FeatureBatch:
    """Features for every number before target_date; history must precede it."""
    if not history:
        raise ValueError("Features require at least one earlier draw")
    if history[-1].draw_date >= target_date or any(
        a.draw_date >= b.draw_date for a, b in zip(history, history[1:])
    ):
        raise ValueError("History must be chronological and precede the target")
    if any(d.pool != pool for d in history):
        raise ValueError("History mixes rule regimes")
    present = np.zeros((len(history), pool), dtype=bool)
    for i, draw in enumerate(history):
        present[i, np.asarray(draw.mains) - 1] = True
    columns = []
    for window in WINDOWS:
        columns.append(present[-window:].mean(axis=0))
    seen = present.any(axis=0)
    reversed_index = np.argmax(present[::-1], axis=0)  # 0 = previous draw
    recency = np.where(seen, np.minimum(reversed_index + 1, RECENCY_CAP), RECENCY_CAP)
    columns += [recency.astype(float), (~seen).astype(float)]
    # Lag k crosses a missing scheduled draw if any link in the chain has a gap.
    links = [target_gap, *(d.gap_before for d in reversed(history))]
    lags, validity = [], []
    for k in (1, 2, 3):
        valid = len(history) >= k and not any(links[:k])
        lags.append(present[-k].astype(float) if valid else np.zeros(pool))
        validity.append(np.full(pool, float(valid)))
    columns += lags + validity
    columns.append(columns[0] - columns[3])
    counts = present.sum(axis=0)
    columns.append((counts + 6 / pool) / (len(history) + 1))
    weekday = np.zeros((7, pool))
    weekday[target_date.weekday()] = 1.0
    columns += list(weekday)
    columns.append(np.full(pool, float((target_date - history[-1].draw_date).days)))
    return FeatureBatch(
        columns=FEATURE_COLUMNS,
        values=np.column_stack(columns),
        max_input_date=history[-1].draw_date,
        target_dates=(target_date,),
    )


def target_features(draws: list[ResearchDraw], index: int) -> FeatureBatch:
    target = draws[index]
    return feature_rows(
        list(draws[:index]), target.draw_date, target.pool, target.gap_before
    )


def labels(draw: ResearchDraw) -> np.ndarray:
    y = np.zeros(draw.pool, dtype=int)
    y[np.asarray(draw.mains) - 1] = 1
    return y


def training_rows(
    draws: list[ResearchDraw], end_index: int, warmup: int = 150, cache=None
) -> tuple[FeatureBatch, np.ndarray]:
    """Supervised rows for targets warmup..end_index-1 (labels never in X)."""
    if end_index <= warmup:
        raise ValueError("No supervised training targets before this index")
    batches = [
        cache[i] if cache is not None and i in cache else target_features(draws, i)
        for i in range(warmup, end_index)
    ]
    if cache is not None:
        cache.update({i: b for i, b in zip(range(warmup, end_index), batches)})
    return (
        FeatureBatch(
            columns=FEATURE_COLUMNS,
            values=np.vstack([b.values for b in batches]),
            max_input_date=draws[end_index - 1].draw_date,
            target_dates=tuple(draws[i].draw_date for i in range(warmup, end_index)),
        ),
        np.concatenate([labels(draws[i]) for i in range(warmup, end_index)]),
    )
