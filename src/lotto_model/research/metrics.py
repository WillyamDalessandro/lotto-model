"""Draw-level match metrics with explicit numerators and denominators."""

from collections import defaultdict
from fractions import Fraction

from lotto_model.research.contracts import EvaluatedRecord


def _rate(numerator: int, denominator: int) -> dict:
    return dict(
        numerator=numerator,
        denominator=denominator,
        rate=numerator / denominator if denominator else None,
    )


def check_parity(records: list[EvaluatedRecord]):
    """Every compared policy must cover identical target dates and budgets."""
    populations = defaultdict(set)
    for record in records:
        p = record.prediction
        populations[p.policy].add((p.target_date, p.budget))
    if len({frozenset(v) for v in populations.values()}) > 1:
        raise ValueError("Compared methods differ in target dates or budgets")
    portfolios = defaultdict(set)
    for record in records:
        p = record.prediction
        key = (p.policy, p.target_date, p.budget)
        if p.line_index in portfolios[key]:
            raise ValueError("Duplicate line index in a portfolio")
        portfolios[key].add(p.line_index)
    for (_, _, budget), indices in portfolios.items():
        if indices != set(range(budget)):
            raise ValueError("Incomplete portfolio")


def summarize(records: list[EvaluatedRecord]) -> dict:
    """Per policy/budget: histogram, per-line and any-line (per-draw) rates."""
    check_parity(records)
    groups = defaultdict(list)
    for record in records:
        groups[(record.prediction.policy, record.prediction.budget)].append(record)
    output = {}
    for (policy, budget), rows in sorted(groups.items()):
        histogram = [0] * 7
        draws = defaultdict(list)
        for row in rows:
            histogram[row.matched_mains] += 1
            draws[row.prediction.target_date].append(row)
        dates = sorted(draws)
        output[f"{policy}:{budget}"] = dict(
            policy=policy,
            budget=budget,
            draws=len(dates),
            lines=len(rows),
            first_date=dates[0].isoformat(),
            last_date=dates[-1].isoformat(),
            histogram=histogram,
            mean_matches=float(
                Fraction(sum(k * c for k, c in enumerate(histogram)), len(rows))
            ),
            line_hit_3_plus=_rate(sum(r.hit_3_plus for r in rows), len(rows)),
            line_hit_5_plus=_rate(sum(r.hit_5_plus for r in rows), len(rows)),
            any_line_hit_3_plus=_rate(
                sum(any(r.hit_3_plus for r in v) for v in draws.values()), len(dates)
            ),
            any_line_hit_5_plus=_rate(
                sum(any(r.hit_5_plus for r in v) for v in draws.values()), len(dates)
            ),
        )
    return output
