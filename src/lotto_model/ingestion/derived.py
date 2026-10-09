from datetime import timedelta
from decimal import Decimal


def build_calendar(start, end, rules, exceptions):
    if start > end:
        raise ValueError("Calendar start must precede end")
    output = []
    day = start
    events = {e["day"]: e for e in exceptions}
    while day <= end:
        active = [
            r
            for r in rules
            if r["starts_on"] <= day and (r["ends_on"] is None or day <= r["ends_on"])
        ]
        if len(active) > 1:
            raise ValueError("Overlapping calendar rules")
        rule = active[0] if active else None
        scheduled = day.weekday() in rule["schedule"] if rule else None
        if day in events:
            scheduled = events[day]["scheduled"]
        iso = day.isocalendar()
        output.append(
            dict(
                day=day,
                iso_year=iso.year,
                iso_week=iso.week,
                weekday=day.weekday(),
                scheduled=scheduled,
                rule_id=rule["id"] if rule else None,
            )
        )
        day += timedelta(days=1)
    return output


def derive_context(draws):
    output = []
    previous = None
    streak = None
    last_win = None
    for row in sorted(draws, key=lambda r: r["draw_date"]):
        mains = sorted(row["mains"])
        values = {}
        cash = Decimal(0)
        cash_known_tiers = 0
        for prize in row["prizes"]:
            if (
                prize["winners"] is None
                or prize["original_amount"] is None
                or prize["currency"] is None
            ):
                continue
            value = prize["winners"] * prize["original_amount"]
            currency = prize["currency"]
            values[currency] = values.get(currency, Decimal(0)) + value
            if currency == "EUR" and prize["prize_type"] == "cash":
                cash += value
                cash_known_tiers += 1
        # Absence of a verified contiguous preceding schedule makes streak unknown.
        if not row.get("continuous_from_previous", False):
            streak = None
        output.append(
            dict(
                draw_id=row["id"],
                definition_version="1",
                draw_date=str(row["draw_date"]),
                main_sum=sum(mains),
                odd_count=sum(n % 2 for n in mains),
                adjacent_pairs=sum(b - a == 1 for a, b in zip(mains, mains[1:])),
                previous_overlap=len(set(mains) & set(previous["mains"]))
                if previous
                else None,
                previous_observed_draw_id=previous["id"] if previous else None,
                days_since_previous_observed_draw=(
                    row["draw_date"] - previous["draw_date"]
                ).days
                if previous
                else None,
                days_since_prior_known_win=(row["draw_date"] - last_win).days
                if last_win
                else None,
                prior_rollover_streak=streak,
                prior_known_win_date=str(last_win) if last_win else None,
                face_values={k: str(v) for k, v in values.items()},
                cash_only_eur=str(cash) if cash_known_tiers else None,
                cash_known_tiers=cash_known_tiers,
                prize_totals_complete=row.get("prizes_complete", False),
            )
        )
        if row.get("outcome") == "Won":
            streak = 0
            last_win = row["draw_date"]
        elif row.get("outcome") == "Roll" and streak is not None:
            streak += 1
        else:
            streak = None
        previous = row
    return output
