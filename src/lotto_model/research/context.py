"""Draw-level context known before each draw: jackpot, prizes and holidays.

Every value for a target draw comes from the advertised jackpot for that draw
or from results of earlier draws, never from the target draw's own outcome.
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from dateutil.easter import easter

from lotto_model.research.contracts import ResearchDraw

CONTEXT_GROUPS = {
    "jackpot": ("jackpot_log10", "rollovers", "days_since_jackpot_won"),
    "holiday": ("days_to_holiday", "holiday_window"),
    "prize": (
        "prev_match3_winners_log10",
        "prev_match4_prize_log10",
        "prev_match5_prize_log10",
    ),
}
MISSING = "context_missing"


def _first_monday(year: int, month: int) -> date:
    day = date(year, month, 1)
    return day + timedelta(days=(7 - day.weekday()) % 7)


def irish_holidays(year: int) -> list[date]:
    """Irish public holidays (St Brigid's Day from 2023) plus Good Friday."""
    easter_sunday = easter(year)
    days = [
        date(year, 1, 1),
        date(year, 3, 17),
        easter_sunday - timedelta(days=2),
        easter_sunday + timedelta(days=1),
        _first_monday(year, 5),
        _first_monday(year, 6),
        _first_monday(year, 8),
        date(year, 12, 25),
        date(year, 12, 26),
    ]
    last_october = date(year, 10, 31)
    days.append(last_october - timedelta(days=last_october.weekday()))
    if year >= 2023:
        brigid = date(year, 2, 1)
        days.append(brigid if brigid.weekday() == 4 else _first_monday(year, 2))
    return sorted(days)


def days_to_holiday(day: date) -> int:
    """Days to the nearest holiday, before or after."""
    years = (day.year - 1, day.year, day.year + 1)
    return min(abs((h - day).days) for y in years for h in irish_holidays(y))


def load_context(snapshot: Path) -> dict[date, dict]:
    """Jackpot, outcome and prize tiers per draw date from a verified bundle."""
    body = json.loads((Path(snapshot) / "enrichment.json").read_text(encoding="utf8"))
    context: dict[date, dict] = {}
    for record in body["records"]:
        day = date.fromisoformat(record["draw_date"])
        entry = context.setdefault(day, dict(prizes={}))
        if record["kind"] == "context" and record.get("tier") == "jackpot":
            if record.get("amount") is not None:
                entry["jackpot"] = float(record["amount"])
        elif record["kind"] == "prize":
            entry["prizes"][record["tier"]] = (
                None if record.get("winners") is None else int(record["winners"]),
                None if record.get("amount") is None else float(record["amount"]),
            )
    return context


def _log10(value) -> float:
    return math.nan if value is None or value <= 0 else math.log10(value)


def context_vector(
    draws: list[ResearchDraw], index: int, context: dict, groups: tuple[str, ...]
) -> np.ndarray:
    """Columns of the requested groups for draws[index], plus a missing flag."""
    target = draws[index]
    values: list[float] = []
    if "jackpot" in groups:
        values.append(_log10(context.get(target.draw_date, {}).get("jackpot")))
        rollovers, since = 0, math.nan
        for earlier in reversed(draws[:index]):
            winners = (
                context.get(earlier.draw_date, {}).get("prizes", {}).get("Match 6")
            )
            if winners is None or winners[0] is None:
                rollovers = math.nan
                break
            if winners[0] > 0:
                since = float((target.draw_date - earlier.draw_date).days)
                break
            rollovers += 1
        values += [float(rollovers), since]
    if "holiday" in groups:
        distance = days_to_holiday(target.draw_date)
        values += [float(distance), float(distance <= 3)]
    if "prize" in groups:
        prizes = (
            context.get(draws[index - 1].draw_date, {}).get("prizes", {})
            if index > 0
            else {}
        )
        match3 = prizes.get("Match 3", (None, None))
        values += [
            _log10(match3[0]),
            _log10(prizes.get("Match 4", (None, None))[1]),
            _log10(prizes.get("Match 5", (None, None))[1]),
        ]
    array = np.asarray(values, dtype=float)
    missing = np.isnan(array)
    return np.append(np.where(missing, 0.0, array), float(missing.any()))


def context_columns(groups: tuple[str, ...]) -> tuple[str, ...]:
    return (*(c for g in groups for c in CONTEXT_GROUPS[g]), MISSING)
