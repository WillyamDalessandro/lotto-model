from fractions import Fraction
from itertools import combinations

import pytest

from lotto_model.research.odds import match_pmf, p_at_least


def test_exact_pmf():
    assert sum(match_pmf(47)) == 1
    assert match_pmf(6)[6] == 1 and sum(match_pmf(6)[:6]) == 0
    with pytest.raises(ValueError):
        match_pmf(5)
    # Independent enumeration on a small pool.
    line = {1, 2, 3, 4, 5, 6}
    counts = [0] * 7
    draws = list(combinations(range(1, 11), 6))
    for draw in draws:
        counts[len(line & set(draw))] += 1
    assert match_pmf(10) == tuple(Fraction(c, len(draws)) for c in counts)
    assert p_at_least(47, 3) == Fraction(
        sum(c for c in [20 * 10660, 15 * 820, 6 * 41, 1]), 10737573
    )
