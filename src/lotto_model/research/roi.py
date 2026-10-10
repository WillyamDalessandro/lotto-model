"""Lines-per-draw and draws-played versus big-prize probability and return.

Probabilities are exact for one line under a fair draw. An optional lift
multiplies every winning tier's probability; it is a what-if, because no
model has shown an edge (Phase 5 and Phase 7). Prize values come from the
snapshot: the median paid per tier in the regime, and the jackpot the next
draw will offer.
"""

import json
import math
from datetime import date
from math import comb
from pathlib import Path
from statistics import median

TIERS = (
    ("Match 6", 6, None),
    ("Match 5 + Bonus", 5, True),
    ("Match 5", 5, False),
    ("Match 4 + Bonus", 4, True),
    ("Match 4", 4, False),
    ("Match 3 + Bonus", 3, True),
    ("Match 3", 3, False),
    ("Match 2 + Bonus", 2, True),
)
BIG_PRIZES = ("Match 6", "Match 5 + Bonus")


def tier_probabilities(pool: int, picks: int = 6) -> dict[str, float]:
    """Exact one-line probability of each prize tier (one bonus ball)."""
    total = comb(pool, picks)
    others = pool - picks  # numbers not among the drawn mains
    result = {}
    for name, matched, bonus in TIERS:
        p_matched = comb(picks, matched) * comb(others, picks - matched) / total
        if bonus is None:
            result[name] = p_matched
            continue
        # The bonus is one of the `others` numbers; it is ours if it hits one
        # of our picks - matched unmatched numbers.
        p_bonus = (picks - matched) / others
        result[name] = p_matched * (p_bonus if bonus else 1 - p_bonus)
    return result


def market(snapshot: Path, rule_code: str) -> dict:
    """Median prize per tier, next jackpot and lines sold for one regime."""
    body = json.loads((Path(snapshot) / "enrichment.json").read_text(encoding="utf8"))
    rules = json.loads((Path(snapshot) / "rules.json").read_text(encoding="utf8"))
    rule = next(r for r in rules if r["code"] == rule_code)
    starts = date.fromisoformat(rule["starts_on"])
    ends = date.fromisoformat(rule["ends_on"]) if rule.get("ends_on") else date.max
    prizes: dict[str, list[float]] = {}
    match3_winners: list[int] = []
    jackpots: dict[date, float] = {}
    jackpot_won: dict[date, bool] = {}
    for record in body["records"]:
        day = date.fromisoformat(record["draw_date"])
        if not starts <= day <= ends:
            continue
        if record["kind"] == "context" and record.get("amount") is not None:
            jackpots[day] = float(record["amount"])
        if record["kind"] != "prize":
            continue
        if record["tier"] == "Match 6" and record.get("winners") is not None:
            jackpot_won[day] = record["winners"] > 0
        elif record.get("amount") is not None:
            prizes.setdefault(record["tier"], []).append(float(record["amount"]))
        if record["tier"] == "Match 3" and record.get("winners") is not None:
            match3_winners.append(int(record["winners"]))
    last = max(jackpots)
    starting = jackpots[min(jackpots)]
    pool = int(rule["pool"])
    p3 = tier_probabilities(pool)["Match 3"]
    return dict(
        rule_code=rule_code,
        pool=pool,
        draws=len(jackpots),
        last_draw=last.isoformat(),
        next_jackpot=starting if jackpot_won.get(last) else jackpots[last],
        starting_jackpot=starting,
        prizes={tier: median(values) for tier, values in prizes.items()},
        # Match 3 winners / P(Match 3) estimates the lines sold per draw.
        lines_sold=median(match3_winners) / p3 if match3_winners else None,
    )


def shared_fraction(lines_sold: float | None, p6: float) -> float:
    """Expected share of a jackpot: E[1/(1+X)], X ~ Poisson(other winners)."""
    if not lines_sold:
        return 1.0
    expected = lines_sold * p6
    return (1 - math.exp(-expected)) / expected


def line_value(market_: dict, jackpot: float, lift: float = 1.0) -> dict:
    probabilities = tier_probabilities(market_["pool"])
    share = shared_fraction(market_["lines_sold"], probabilities["Match 6"])
    values = dict(market_["prizes"])
    values["Match 6"] = jackpot * share
    expected = sum(
        lift * p * values.get(tier, 0.0) for tier, p in probabilities.items()
    )
    big = lift * sum(probabilities[t] for t in BIG_PRIZES)
    rest = expected - lift * probabilities["Match 6"] * values["Match 6"]
    return dict(
        expected_return=expected,
        big_prize_probability=big,
        jackpot_share=share,
        values=values,
        rest_of_tiers=rest,
        probabilities=probabilities,
    )


def plan_table(
    market_: dict,
    price: float,
    lift: float = 1.0,
    lines: tuple[int, ...] = (1, 2, 5, 10, 20, 50, 100),
    draws: tuple[int, ...] = (1, 12, 52, 156),
    jackpot: float | None = None,
) -> list[dict]:
    """Every (lines per draw, draws played) plan: chance of a big prize, cost
    and expected return. Distinct lines per draw; draws are independent."""
    value = line_value(market_, jackpot or market_["next_jackpot"], lift)
    p_big = value["big_prize_probability"]
    rows = []
    for n in lines:
        per_draw = 1 - (1 - p_big) ** n
        for d in draws:
            cost = n * d * price
            rows.append(
                dict(
                    lines_per_draw=n,
                    draws=d,
                    cost=cost,
                    p_big_prize=1 - (1 - per_draw) ** d,
                    p_jackpot=1
                    - (1 - lift * n * value["probabilities"]["Match 6"]) ** d,
                    expected_return=value["expected_return"] * n * d,
                    expected_net=(value["expected_return"] - price) * n * d,
                    return_per_euro=value["expected_return"] / price,
                )
            )
    return rows


def break_even_jackpot(market_: dict, price: float, lift: float = 1.0) -> float:
    """Advertised jackpot at which one line's expected return equals its price.

    Solved numerically because a bigger jackpot sells more lines and is
    shared more; lines sold are held at the regime median here."""
    low, high = 0.0, 1e10
    for _ in range(200):
        middle = (low + high) / 2
        if line_value(market_, middle, lift)["expected_return"] < price:
            low = middle
        else:
            high = middle
    return high


def lines_for_probability(p_line: float, target: float) -> int:
    """Smallest number of distinct lines with P(at least one hit) >= target."""
    return math.ceil(math.log(1 - target) / math.log(1 - p_line))


def _percent(p: float) -> str:
    if p >= 0.001:
        return f"{p:.2%}"
    return f"1 in {1 / p:,.0f}" if p > 0 else "0"


def roi_report(
    market_: dict,
    price: float,
    lift: float = 1.0,
    lift_note: str = "",
    jackpots: tuple[float, ...] = (),
) -> str:
    jackpot = market_["next_jackpot"]
    value = line_value(market_, jackpot, lift)
    breakeven = break_even_jackpot(market_, price, lift)
    p_big = value["big_prize_probability"]
    lines = [
        f"# Lines, draws and return: {market_['rule_code']}",
        "",
        f"- Data: {market_['draws']} draws of {market_['rule_code']}, last "
        f"{market_['last_draw']}. Price per line: EUR {price:.2f}.",
        f"- Next advertised jackpot: EUR {jackpot:,.0f}. Estimated lines sold per "
        f"draw: {market_['lines_sold']:,.0f}, so a jackpot win keeps "
        f"{value['jackpot_share']:.1%} on average after sharing.",
        f"- Probability lift applied: {lift:g}"
        + (f" ({lift_note})" if lift_note else " (fair draw, no model edge)"),
        "- Big prize means Match 6 (jackpot) or Match 5 + Bonus.",
        "",
        "## One line",
        "",
        "| Tier | Probability | Prize used (EUR) | Expected (EUR) |",
        "|---|---|---:|---:|",
    ]
    for tier, p in value["probabilities"].items():
        prize = value["values"].get(tier, 0.0)
        lines.append(
            f"| {tier} | {_percent(lift * p)} | {prize:,.0f} | {lift * p * prize:.3f} |"
        )
    lines += [
        "",
        f"Expected return per line: **EUR {value['expected_return']:.2f}** for "
        f"EUR {price:.2f}, so **{value['expected_return'] / price:.0%} back per "
        "euro**. The rest is the expected loss.",
        f"Break-even advertised jackpot: **EUR {breakeven:,.0f}**. Below it every "
        "line loses money on average, whatever the number of lines.",
        "",
        "## If you play X lines per draw for D draws",
        "",
        "| Lines per draw | Draws | Cost (EUR) | P(big prize) | P(jackpot) | "
        "Expected back (EUR) | Expected net (EUR) |",
        "|---:|---:|---:|---|---|---:|---:|",
    ]
    for row in plan_table(market_, price, lift):
        lines.append(
            f"| {row['lines_per_draw']} | {row['draws']} | {row['cost']:,.0f} | "
            f"{_percent(row['p_big_prize'])} | {_percent(row['p_jackpot'])} | "
            f"{row['expected_return']:,.0f} | {row['expected_net']:,.0f} |"
        )
    lines += [
        "",
        "## Lines needed for a chance of a big prize in one draw",
        "",
        "| Target probability | Lines | Cost (EUR) | Expected net (EUR) |",
        "|---|---:|---:|---:|",
    ]
    for target in (0.01, 0.1, 0.5, 0.9):
        n = lines_for_probability(p_big, target)
        lines.append(
            f"| {target:.0%} | {n:,} | {n * price:,.0f} | "
            f"{(value['expected_return'] - price) * n:,.0f} |"
        )
    if jackpots:
        lines += [
            "",
            "## Return per euro at other advertised jackpots",
            "",
            "| Jackpot (EUR) | Expected back per EUR 1 |",
            "|---:|---:|",
        ]
        for amount in jackpots:
            back = line_value(market_, amount, lift)["expected_return"] / price
            lines.append(f"| {amount:,.0f} | {back:.2f} |")
    lines += [
        "",
        "## The ideal number of lines",
        "",
        "Return per euro does not depend on how many lines are played. Distinct "
        "lines add their chances and their costs in the same proportion. So:",
        "",
        f"- While the advertised jackpot is below EUR {breakeven:,.0f}, the plan "
        "with the best expected return is to play nothing. Each extra line adds "
        f"EUR {price - value['expected_return']:.2f} of expected loss.",
        "- Above it, each line has a positive expectation, but the variance is "
        "extreme: almost all of the value is the jackpot, which a line wins once "
        f"in {1 / (lift * value['probabilities']['Match 6']):,.0f} draws.",
        "- If you play for entertainment, choose the budget you accept losing. The "
        "tables show the chance of a big prize that budget buys.",
        "- Choosing numbers above 31 does not change any probability here. It "
        "raises the prize per win, because fewer players share it (Phase 7 "
        "prize analysis).",
        "",
    ]
    return "\n".join(lines)
