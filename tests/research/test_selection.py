from dataclasses import replace

from lotto_model.research.backtest import evaluate, run_development
from lotto_model.research.metrics import check_parity
from lotto_model.research.models import CANDIDATES
from lotto_model.research.protocol import build_protocol
from lotto_model.research.selection import develop


def test_common_development_population(research_draws):
    draws = research_draws(282)
    protocol = build_protocol(draws, "a" * 64)
    result = develop(protocol, draws, candidates=(CANDIDATES[0], CANDIDATES[3]))
    assert {s["targets"] for s in result["scores"]} == {50}
    assert result["selected"] in {"logistic-c0.01", "boosting-leaves3"}
    baseline = run_development(protocol, draws, "uniform", 1)
    records = evaluate(
        [r for r in result["records"]]
        + baseline
        + run_development(protocol, draws, "uniform", 5)
        + run_development(protocol, draws, "uniform", 10),
        draws,
    )
    check_parity(records)
    changed = [
        d if i < 225 else replace(d, mains=(1, 2, 3, 4, 5, 6))
        for i, d in enumerate(draws)
    ]
    again = develop(protocol, changed, candidates=(CANDIDATES[0], CANDIDATES[3]))
    assert (
        again["scores"] == result["scores"] and again["selected"] == result["selected"]
    )
