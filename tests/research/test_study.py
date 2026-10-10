import json
from dataclasses import replace
from math import comb

import numpy as np
import pytest
from scipy.stats import binom
from typer.testing import CliRunner

from lotto_model.research.odds import p_at_least
from lotto_model.research.study import (
    FeatureCache,
    NullModel,
    StudyConfig,
    coverage_lines,
    heuristic_lines,
    poisson_binomial_tail,
    pooled_rows,
    run_study,
    split,
    tune,
)

SMALL_SPACE = {
    "logistic": {"C": [0.01, 1.0]},
    "boosting": {"max_leaf_nodes": [3], "learning_rate": [0.1]},
}


def small_config(**overrides):
    values = dict(
        snapshot_digest="a" * 64,
        rule_code="6/47",
        pool=47,
        evaluation_days=60,
        feature_warmup=30,
        block_size=10,
        tuning_blocks=2,
        families=("logistic", "boosting"),
        search_space=SMALL_SPACE,
        null_samples=2000,
    )
    return StudyConfig(**(values | overrides))


def test_split_orders_warmup_tuning_evaluation(research_draws):
    draws = research_draws(90)
    bounds = split(small_config(), draws)
    first = draws[bounds["evaluation_start"]].draw_date
    assert (draws[-1].draw_date - first).days <= 60
    assert bounds["tuning_start"] == bounds["evaluation_start"] - 20
    assert bounds["tuning_start"] - 30 >= 10


def test_split_refuses_insufficient_history(research_draws):
    with pytest.raises(ValueError, match="insufficient_data"):
        split(small_config(), research_draws(50))


def test_config_requires_search_space_for_each_family():
    with pytest.raises(ValueError, match="search space"):
        small_config(families=("forest",))


def test_tuning_never_reads_evaluation_outcomes(research_draws):
    draws = research_draws(90)
    config = small_config()
    bounds = split(config, draws)
    altered = list(draws)
    for i in range(bounds["evaluation_start"], len(draws)):
        altered[i] = replace(draws[i], mains=(1, 2, 3, 4, 5, 6))
    first = tune(config, draws, FeatureCache(draws), bounds)
    second = tune(config, altered, FeatureCache(altered), bounds)
    assert first == second


def test_coverage_lines_spread_numbers():
    scores = np.linspace(1, 0, 47)
    five = coverage_lines(scores, 5)
    assert len({n for line in five for n in line}) == 30
    ten = coverage_lines(scores, 10)
    assert len(set(ten)) == 10
    assert five[0] == (1, 2, 3, 4, 5, 6)


def test_heuristics_pick_hot_cold_and_overdue(research_draws):
    draws = research_draws(60)
    features = FeatureCache(draws).features(59)
    for method in ("hot", "cold", "overdue"):
        (line,) = heuristic_lines(method, features)
        assert len(set(line)) == 6


def test_poisson_binomial_matches_binomial():
    p = float(p_at_least(47, 3))
    expected = binom.sf(4, 200, p)
    assert poisson_binomial_tail([p] * 200, 5) == pytest.approx(expected)
    assert poisson_binomial_tail([p] * 10, 0) == pytest.approx(1.0)


def test_null_model_portfolio_probability():
    null = NullModel(47, 20_000, 1)
    p0 = float(p_at_least(47, 3))
    assert null.probability(((1, 2, 3, 4, 5, 6),)) == p0
    portfolio = coverage_lines(np.linspace(1, 0, 47), 5)
    # Disjoint lines: 5 p0 minus pairs where two lines both hit exactly three.
    exact = 5 * p0 - 10 * 20 * 20 / comb(47, 6)
    assert null.probability(portfolio) == pytest.approx(exact, abs=4 * 0.0022)
    shifted = tuple(tuple(n + 10 for n in line) for line in portfolio)
    assert null.probability(shifted) == null.probability(portfolio)


def test_run_study_is_complete_and_reproducible(tmp_path, research_draws):
    draws = research_draws(90)
    config = small_config()
    output, reported = run_study(config, draws, tmp_path)
    names = {p.name for p in output.iterdir()}
    assert {
        "config.json",
        "tuning.csv",
        "selected.json",
        "predictions.csv",
        "evaluation.csv",
        "summary.csv",
        "yearly.csv",
        "calibration.csv",
        "findings.md",
        "manifest.json",
    } <= names
    pairs = {(r["source"], r["method"]) for r in reported["summary"]}
    assert ("logistic", "top6") in pairs and ("uniform", "random10") in pairs
    assert ("heuristic", "overdue") in pairs and ("frequency", "coverage5") in pairs
    assert all(0 <= r["holm_p_value"] <= 1 for r in reported["summary"])
    manifest = json.loads((output / "manifest.json").read_text())
    rerun, _ = run_study(config, draws, tmp_path)
    assert json.loads((rerun / "manifest.json").read_text()) == manifest
    assert "Verdict" in (output / "findings.md").read_text()


def test_study_command_reports_insufficient_history(tmp_path, synthetic_snapshot):
    from lotto_model.cli import app

    snapshot = synthetic_snapshot(60)
    result = CliRunner().invoke(
        app,
        [
            "research",
            "study",
            str(snapshot.path),
            "--rule-code",
            "6/47",
            "--output-root",
            str(tmp_path / "studies"),
        ],
    )
    assert result.exit_code == 1
    assert "insufficient_data" in result.output


def test_match_moments_are_exact_for_one_line_and_estimated_for_portfolios():
    null = NullModel(47, 20_000, 3)
    mean, variance = null.match_moments(((1, 2, 3, 4, 5, 6),))
    assert mean == pytest.approx(36 / 47)
    sampled = null.outcomes[:, :6].sum(axis=1)
    assert sampled.mean() == pytest.approx(mean, abs=0.02)
    assert sampled.var() == pytest.approx(variance, abs=0.02)
    portfolio = coverage_lines(np.linspace(1, 0, 47), 5)
    assert null.match_moments(portfolio)[0] > mean


@pytest.mark.parametrize("pool", [36, 39, 42, 45, 47])
def test_coverage_lines_stay_distinct_for_every_regime_pool(pool):
    lines = coverage_lines(np.linspace(1, 0, pool), 10)
    assert len(set(lines)) == 10
    assert all(len(set(line)) == 6 for line in lines)


def _earlier_regime(draws, pool=45, rule_code="6/45"):
    """Same synthetic shape, shifted to end before the studied regime."""
    from datetime import timedelta

    span = draws[-1].draw_date - draws[0].draw_date + timedelta(days=7)
    return [
        replace(
            d,
            draw_date=d.draw_date - span,
            rule_code=rule_code,
            pool=pool,
            mains=tuple(min(n, pool) for n in d.mains)
            if max(d.mains) <= pool
            else tuple(sorted({n % pool + 1 for n in d.mains} | set(range(1, 7))))[:6],
        )
        for d in draws
    ]


def test_default_training_keeps_earlier_digests():
    base = small_config()
    assert "training_window" not in base.model_dump(exclude_defaults=True)
    assert small_config(training_window=None).digest == base.digest
    assert small_config(training_window=25).digest != base.digest
    assert small_config(pooled_regimes=("6/45",)).digest != base.digest


def test_dataset_variants_never_read_evaluation_outcomes(research_draws):
    draws = research_draws(90)
    earlier = _earlier_regime(research_draws(60, seed=3))
    for overrides in (dict(training_window=25), dict(pooled_regimes=("6/45",))):
        config = small_config(**overrides)
        bounds = split(config, draws)
        altered = list(draws)
        for i in range(bounds["evaluation_start"], len(draws)):
            altered[i] = replace(draws[i], mains=(1, 2, 3, 4, 5, 6))
        pooled = (
            pooled_rows(config, {"6/45": earlier}, draws[0].draw_date)
            if config.pooled_regimes
            else None
        )
        first = tune(config, draws, FeatureCache(draws, pooled), bounds)
        second = tune(config, altered, FeatureCache(altered, pooled), bounds)
        assert first == second


def test_pooled_study_runs_and_refuses_overlapping_regimes(tmp_path, research_draws):
    draws = research_draws(90)
    earlier = _earlier_regime(research_draws(60, seed=3))
    config = small_config(pooled_regimes=("6/45",))
    output, reported = run_study(config, draws, tmp_path, {"6/45": earlier})
    assert "plus all draws of 6/45" in (output / "findings.md").read_text()
    assert any(r["source"] == "boosting" for r in reported["summary"])
    with pytest.raises(ValueError, match="must end before"):
        run_study(config, draws, tmp_path / "x", {"6/45": draws})
    with pytest.raises(ValueError, match="match the configured"):
        run_study(config, draws, tmp_path / "y", {})


def test_training_window_limits_rows(tmp_path, research_draws):
    draws = research_draws(90)
    output, _ = run_study(small_config(training_window=25), draws, tmp_path)
    assert "latest 25 earlier draws" in (output / "findings.md").read_text()


def test_compare_studies_tables_variants(tmp_path, research_draws):
    from lotto_model.research.study import compare_studies

    draws = research_draws(90)
    base, _ = run_study(small_config(), draws, tmp_path)
    window, _ = run_study(small_config(training_window=25), draws, tmp_path)
    table = compare_studies([base, window])
    assert "all earlier draws" in table and "latest 25" in table
    assert len(table.strip().splitlines()) == 4


def test_select_line_candidate_prefers_highest_one_line_rate(tmp_path, research_draws):
    from lotto_model.research.study import select_line_candidate

    draws = research_draws(90)
    base, _ = run_study(small_config(), draws, tmp_path)
    window, _ = run_study(small_config(training_window=25), draws, tmp_path)
    result = select_line_candidate([base, window])
    rates = [c["rate"] for c in result["ranking"]]
    assert rates == sorted(rates, reverse=True)
    assert result["selected"]["method"] in ("top6", "weighted")
    assert result["candidates"] == 2 * 2 * 2
