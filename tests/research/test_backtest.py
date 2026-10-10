from dataclasses import replace

import pytest

from lotto_model.research.backtest import (
    development_targets,
    evaluate,
    predict,
    run_development,
)
from lotto_model.research.metrics import summarize
from lotto_model.research.protocol import build_protocol
from lotto_model.research.simulation import simulate_baselines

DIGEST = "a" * 64


@pytest.fixture
def setup(research_draws):
    draws = research_draws(282)
    return build_protocol(draws, DIGEST), draws


@pytest.mark.parametrize("policy", ["uniform", "frequency"])
def test_cutoffs_and_holdout_guard(setup, policy):
    protocol, draws = setup
    records = run_development(protocol, draws, policy, 5)
    targets = set(development_targets(protocol))
    assert {r.target_date for r in records} == {draws[i].draw_date for i in targets}
    assert all(r.max_input_date < r.target_date for r in records)
    assert all(175 <= protocol.dates.index(r.target_date) < 225 for r in records)
    with pytest.raises(ValueError, match="Holdout"):
        predict(protocol, draws, policy, 1, [230])
    future = [
        d if i < 175 else replace(d, mains=(1, 2, 3, 4, 5, 6))
        for i, d in enumerate(draws)
    ]
    changed = run_development(protocol, future, policy, 5)
    early = [r for r in records if r.target_date == draws[175].draw_date]
    assert early == [r for r in changed if r.target_date == draws[175].draw_date]
    holdout_changed = [
        d if i < 225 else replace(d, mains=(1, 2, 3, 4, 5, 6))
        for i, d in enumerate(draws)
    ]
    assert run_development(protocol, holdout_changed, policy, 5) == records


def test_population_must_match_protocol(setup):
    protocol, draws = setup
    with pytest.raises(ValueError):
        run_development(protocol, draws[:-1], "uniform", 1)
    with pytest.raises(ValueError):
        run_development(protocol, draws, "uniform", 3)


def test_metric_reconciliation(setup):
    protocol, draws = setup
    target = replace(draws[175], mains=(1, 2, 3, 7, 8, 9))
    record = predict(protocol, draws, "frequency", 1, [175])[0]
    record = record.model_copy(update={"mains": (1, 2, 3, 4, 5, 6)})
    (evaluated,) = evaluate([record], [target])
    assert evaluated.matched_mains == 3 and evaluated.hit_3_plus
    assert not evaluated.hit_5_plus
    assert record.mains == (1, 2, 3, 4, 5, 6)
    records = []
    for policy in ("uniform", "frequency"):
        for budget in (1, 5):
            records += evaluate(run_development(protocol, draws, policy, budget), draws)
    summary = summarize(records)
    for value in summary.values():
        assert sum(value["histogram"]) == value["lines"]
        assert value["any_line_hit_3_plus"]["denominator"] == 50 == value["draws"]
    assert summary["uniform:5"]["lines"] == 250
    incomplete = [
        r
        for r in records
        if not (
            r.prediction.policy == "uniform"
            and r.prediction.target_date == draws[175].draw_date
        )
    ]
    with pytest.raises(ValueError, match="differ"):
        summarize(incomplete)


def test_simulation_reconciles_with_exact_odds(setup):
    protocol, draws = setup
    result = simulate_baselines(protocol, draws, simulations=200, budgets=(1, 5))
    assert result["budgets"]["1"]["trials"] == 200 * 50
    assert result["budgets"]["1"]["reconciliation"]["passed"]
    assert (
        result["budgets"]["5"]["any_line_hit_3_plus"]["rate"] > result["exact_line_p3"]
    )
    again = simulate_baselines(protocol, draws, simulations=200, budgets=(1, 5))
    assert again == result


def test_parallel_simulation_equals_sequential(research_draws):
    from lotto_model.research.protocol import build_protocol
    from lotto_model.research.simulation import simulate_baselines

    draws = research_draws(300)
    protocol = build_protocol(draws, "a" * 64)
    sequential = simulate_baselines(protocol, draws, 120, (1, 5), workers=1)
    parallel = simulate_baselines(protocol, draws, 120, (1, 5), workers=3)
    assert parallel == sequential
