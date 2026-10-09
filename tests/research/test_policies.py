from dataclasses import replace
from datetime import date

import pytest

from lotto_model.research import policies
from lotto_model.research.contracts import ResearchDraw
from lotto_model.research.policies import (
    derive_seed,
    frequency_portfolio,
    top_line,
    uniform_portfolio,
)


def test_seed_derivation_is_stable():
    seed = derive_seed("d" * 64, "uniform", date(2026, 10, 7), 1, 0)
    assert seed == derive_seed("d" * 64, "uniform", date(2026, 10, 7), 1, 0)
    assert seed != derive_seed("d" * 64, "uniform", date(2026, 10, 7), 1, 1)
    assert 0 <= seed < 2**64


@pytest.mark.parametrize("budget", [1, 5, 10])
def test_portfolios_are_valid(budget, research_draws):
    for lines in (
        uniform_portfolio(47, budget, 11),
        frequency_portfolio(research_draws(50), budget, 11),
    ):
        assert len(lines) == budget == len(set(lines))
        assert all(len(set(x)) == 6 and all(1 <= n <= 47 for n in x) for x in lines)
    assert uniform_portfolio(47, budget, 11) == uniform_portfolio(47, budget, 11)


def test_frequency_ties_and_history():
    assert frequency_portfolio([], 1, 3) == ((1, 2, 3, 4, 5, 6),)
    history = [ResearchDraw(date(2026, 1, 5), "6/47", 47, (10, 20, 30, 40, 41, 47))]
    assert frequency_portfolio(history, 1, 3) == ((10, 20, 30, 40, 41, 47),)
    assert top_line([0.0] * 47) == (1, 2, 3, 4, 5, 6)
    with pytest.raises(ValueError):
        frequency_portfolio([replace(history[0], pool=45)], 1, 3)


def test_impossible_budget_and_attempt_cap(monkeypatch):
    with pytest.raises(ValueError, match="Impossible"):
        uniform_portfolio(6, 2, 1)
    assert uniform_portfolio(7, 7, 1) and len(set(uniform_portfolio(7, 7, 1))) == 7
    monkeypatch.setattr(policies, "ATTEMPT_CAP", 3)
    with pytest.raises(ValueError, match="cap"):
        uniform_portfolio(7, 7, 1)
