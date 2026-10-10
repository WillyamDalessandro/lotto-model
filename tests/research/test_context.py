from datetime import date

import numpy as np
from test_study import small_config

from lotto_model.research.context import (
    context_columns,
    context_vector,
    days_to_holiday,
    irish_holidays,
)
from lotto_model.research.study import FeatureCache, run_study, split, tune


def _context(draws):
    return {
        d.draw_date: dict(
            jackpot=2_000_000 + 100_000 * i,
            prizes={
                "Match 6": (1 if i % 7 == 0 else 0, None),
                "Match 3": (10_000 + i, 4.0),
                "Match 4": (700, 40.0 + i % 5),
                "Match 5": (15, 1500.0),
            },
        )
        for i, d in enumerate(draws)
    }


def test_irish_holidays_2026():
    days = irish_holidays(2026)
    assert date(2026, 4, 6) in days and date(2026, 10, 26) in days
    assert date(2026, 2, 2) in days and date(2022, 2, 1) not in irish_holidays(2022)
    assert days_to_holiday(date(2026, 12, 23)) == 2


def test_context_uses_only_pre_draw_information(research_draws):
    draws = research_draws(40)
    context = _context(draws)
    groups = ("jackpot", "holiday", "prize")
    before = context_vector(draws, 20, context, groups)
    # The target draw's own results must not change its context.
    context[draws[20].draw_date]["prizes"] = {"Match 6": (5, None)}
    assert np.array_equal(before, context_vector(draws, 20, context, groups))
    assert len(before) == len(context_columns(groups))
    assert before[1] == 20 - 14 - 1 and before[-1] == 0.0


def test_missing_context_is_flagged(research_draws):
    draws = research_draws(10)
    vector = context_vector(draws, 5, {}, ("jackpot",))
    assert vector[-1] == 1.0 and not np.isnan(vector).any()


def test_context_study_never_reads_evaluation_outcomes(research_draws, tmp_path):
    draws = research_draws(90)
    context = _context(draws)
    config = small_config(context_features=("jackpot", "holiday", "prize"))
    bounds = split(config, draws)
    altered = list(draws)
    from dataclasses import replace

    for i in range(bounds["evaluation_start"], len(draws)):
        altered[i] = replace(draws[i], mains=(1, 2, 3, 4, 5, 6))
    first = tune(config, draws, FeatureCache(draws, context=context), bounds)
    second = tune(config, altered, FeatureCache(altered, context=context), bounds)
    assert first == second
    output, _ = run_study(config, draws, tmp_path, context=context)
    assert "context: jackpot, holiday, prize" in (output / "findings.md").read_text()


def test_until_truncates_draws(research_draws, tmp_path):
    draws = research_draws(120)
    until = draws[89].draw_date
    output, _ = run_study(small_config(until=until), draws, tmp_path)
    assert f"draws up to {until}" in (output / "findings.md").read_text()
    assert small_config(until=until).digest != small_config().digest
