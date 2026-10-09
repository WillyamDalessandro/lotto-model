"""Exact single-line match probabilities for a six-from-N draw."""

from fractions import Fraction
from math import comb


def match_pmf(pool: int) -> tuple[Fraction, ...]:
    """P(K=k) = C(6,k) C(N-6,6-k) / C(N,6) for k=0..6; impossible terms are 0."""
    if pool < 6:
        raise ValueError("Pool must contain at least six numbers")
    total = comb(pool, 6)
    return tuple(Fraction(comb(6, k) * comb(pool - 6, 6 - k), total) for k in range(7))


def p_at_least(pool: int, matches: int) -> Fraction:
    return sum(match_pmf(pool)[matches:], Fraction(0))
