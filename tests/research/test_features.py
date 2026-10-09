from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from lotto_model.research.contracts import ResearchDraw
from lotto_model.research.features import (
    FEATURE_COLUMNS,
    feature_rows,
    target_features,
    training_rows,
)
from lotto_model.research.protocol import build_protocol
from lotto_model.research.selection import require_candidate_protocol


def col(batch, name):
    return batch.values[:, FEATURE_COLUMNS.index(name)]


def test_training_start(research_draws):
    draws = research_draws(282)
    features, y = training_rows(draws, 175)
    assert features.values.shape == (25 * 47, len(FEATURE_COLUMNS))
    assert y.sum() == 25 * 6
    with pytest.raises(ValueError):
        training_rows(draws, 150)
    protocol = build_protocol(draws, "a" * 64)
    require_candidate_protocol(protocol)
    with pytest.raises(ValueError, match="revise"):
        require_candidate_protocol(
            protocol.model_copy(update={"validation_start": 150})
        )


def test_feature_cutoffs_and_gaps(research_draws):
    draws = research_draws(200)
    before = target_features(draws, 160)
    future = [
        d if i < 160 else replace(d, mains=(1, 2, 3, 4, 5, 6))
        for i, d in enumerate(draws)
    ]
    assert np.array_equal(before.values, target_features(future, 160).values)
    assert before.max_input_date == draws[159].draw_date
    first = ResearchDraw(date(2026, 1, 5), "6/47", 47, (1, 2, 3, 4, 5, 6))
    second = ResearchDraw(
        date(2026, 1, 7), "6/47", 47, (1, 7, 8, 9, 10, 11), gap_before=True
    )
    batch = feature_rows([first, second], date(2026, 1, 12), 47)
    assert col(batch, "lag_1_valid")[0] == 1 and col(batch, "lag_2_valid")[0] == 0
    assert col(batch, "lag_2")[1] == 0  # invalid lag is zeroed
    assert col(batch, "lag_3_valid")[0] == 0
    gap_target = feature_rows([first, second], date(2026, 1, 12), 47, target_gap=True)
    assert col(gap_target, "lag_1_valid")[0] == 0
    assert col(batch, "never_seen")[46] == 1 and col(batch, "recency")[46] == 100
    assert col(batch, "recency")[0] == 1 and col(batch, "recency")[1] == 2
    assert col(batch, "weekday_0")[0] == 1 and col(batch, "days_since_prior")[0] == 5
    with pytest.raises(ValueError):
        feature_rows([second], date(2026, 1, 7), 47)
    assert not np.any(np.isnan(batch.values))
