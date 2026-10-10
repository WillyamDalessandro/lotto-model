from math import comb

import pytest

from lotto_model.research.roi import (
    break_even_jackpot,
    line_value,
    lines_for_probability,
    plan_table,
    roi_report,
    shared_fraction,
    tier_probabilities,
)

MARKET = dict(
    rule_code="6/45-2026",
    pool=45,
    draws=15,
    last_draw="2026-10-07",
    next_jackpot=2_000_000.0,
    starting_jackpot=2_000_000.0,
    prizes={"Match 5 + Bonus": 42_031.0, "Match 4": 43.0, "Match 3": 4.0},
    lines_sold=534_411.0,
)


def test_official_odds_for_6_45():
    p = tier_probabilities(45)
    assert 1 / p["Match 6"] == pytest.approx(8_145_060)
    assert 1 / p["Match 5 + Bonus"] == pytest.approx(1_357_510)
    # Every tier plus "no prize" partitions the outcomes of one line.
    no_prize = sum(comb(6, k) * comb(39, 6 - k) for k in (0, 1, 2)) / comb(45, 6)
    no_prize -= p["Match 2 + Bonus"]
    assert sum(p.values()) + no_prize == pytest.approx(1)


def test_sharing_and_break_even():
    assert shared_fraction(None, 1e-7) == 1.0
    assert 0.9 < shared_fraction(534_411, 1 / 8_145_060) < 1.0
    price = 2.0
    breakeven = break_even_jackpot(MARKET, price)
    assert line_value(MARKET, breakeven * 0.99)["expected_return"] < price
    assert line_value(MARKET, breakeven * 1.01)["expected_return"] > price
    assert break_even_jackpot(MARKET, price, lift=2.0) < breakeven


def test_plan_table_scales_cost_and_probability():
    rows = {(r["lines_per_draw"], r["draws"]): r for r in plan_table(MARKET, 2.0)}
    assert rows[(10, 12)]["cost"] == 240
    assert rows[(10, 12)]["p_big_prize"] > rows[(1, 12)]["p_big_prize"]
    assert rows[(10, 1)]["return_per_euro"] == rows[(1, 1)]["return_per_euro"]
    assert lines_for_probability(0.5, 0.75) == 2


def test_report_names_break_even_and_plans():
    text = roi_report(MARKET, 2.0, jackpots=(16e6,))
    assert "Break-even advertised jackpot" in text
    assert "| 100 | 156 |" in text and "16,000,000" in text
