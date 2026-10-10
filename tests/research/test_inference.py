from datetime import date

import numpy as np
import pytest

from lotto_model.research.inference import (
    calibration_bins,
    clopper_pearson,
    holm,
    infer_primary,
    monte_carlo_p,
    null_statistic,
    paired_bootstrap,
    run_null_replicates,
)
from lotto_model.research.predictor import predict_next
from lotto_model.research.protocol import build_protocol
from lotto_model.research.reporting import minimum_detectable_rate

FROZEN = dict(
    selected=dict(id="logistic-c0.01"),
    protocol_digest="a" * 64,
    snapshot_digest="a" * 64,
)


def test_sparse_intervals():
    lower, upper = clopper_pearson(0, 57)
    assert lower == 0 and 0 < upper < 0.1
    result = infer_primary([False] * 57, 47)
    assert result["improvement_interval"] == [
        lower - result["p0"],
        upper - result["p0"],
    ]
    assert not result["interval_excludes_zero"]
    assert monte_carlo_p(0.5, np.zeros(10_000)) == 1 / 10_001
    assert monte_carlo_p(0.0, np.zeros(10)) == 1.0
    assert 0.09 < minimum_detectable_rate(result["p0"], 57) < 0.1


def test_holm_family():
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert holm({"a": 0.9, "b": 0.8}) == {"b": 1.0, "a": 1.0}


def test_calibration_last_bin_includes_one():
    bins = calibration_bins([0.0, 0.05, 0.95, 1.0], [0, 0, 1, 1])
    assert len(bins) == 10 and bins[-1]["count"] == 2 and bins[0]["count"] == 2
    assert sum(b["count"] for b in bins) == 4


def test_bootstrap_units():
    model = [True, False, False, True, False]
    base = [False, False, False, True, False]
    first = paired_bootstrap(model, base, 200, 3)
    assert first == paired_bootstrap(model, base, 200, 3)
    assert first["mean_difference"] == 0.2
    assert paired_bootstrap(model, base, 200, 3, block=5)["block_length"] == 5
    with pytest.raises(ValueError):
        paired_bootstrap(model, base[:-1], 10, 1)


def test_null_resume_equals_uninterrupted(research_draws, tmp_path):
    draws = research_draws(282)
    protocol = build_protocol(draws, "a" * 64)
    interrupted = tmp_path / "a"
    run_null_replicates(FROZEN, protocol, draws, 1, interrupted)
    resumed = run_null_replicates(FROZEN, protocol, draws, 2, interrupted)
    clean = run_null_replicates(FROZEN, protocol, draws, 2, tmp_path / "b")
    assert resumed == clean and not clean["final"]
    assert len(list(interrupted.glob("*.json"))) == 2
    assert null_statistic(FROZEN, protocol, draws, 0) == clean["statistics"][0]


def test_parallel_nulls_equal_sequential(research_draws, tmp_path):
    draws = research_draws(282)
    protocol = build_protocol(draws, "a" * 64)
    sequential = run_null_replicates(FROZEN, protocol, draws, 3, tmp_path / "s")
    parallel = run_null_replicates(FROZEN, protocol, draws, 3, tmp_path / "p", 2)
    assert parallel == sequential


def test_predict_next(research_draws):
    draws = research_draws(200)
    frozen = FROZEN | dict(
        feature_columns=list(
            __import__("lotto_model.research.features", fromlist=["x"]).FEATURE_COLUMNS
        )
    )
    value = predict_next(frozen, draws, date(2030, 1, 7), 47)
    assert len(set(value["mains"])) == 6 and all(1 <= n <= 47 for n in value["mains"])
    assert value["cutoff"] == draws[-1].draw_date.isoformat()
    with pytest.raises(ValueError):
        predict_next(frozen, draws, draws[-1].draw_date, 47)
    with pytest.raises(ValueError):
        predict_next(frozen, draws, date(2030, 1, 7), 45)
    with pytest.raises(ValueError):
        predict_next(frozen, draws[:100], date(2030, 1, 7), 47)
