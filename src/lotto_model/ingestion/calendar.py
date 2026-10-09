from datetime import date

from sqlalchemy import text

from lotto_model.ingestion.derived import build_calendar


def materialize_calendar(connection, start, end):
    rules = [
        dict(r)
        for r in connection.execute(
            text(
                "SELECT * FROM rule_regimes WHERE game_id="
                "(SELECT id FROM games WHERE code='lotto')"
            )
        ).mappings()
    ]
    events = {}
    for row in connection.execute(
        text("SELECT payload FROM calendar_events")
    ).scalars():
        day = date.fromisoformat(row["day"])
        if day in events and events[day]["scheduled"] != row["scheduled"]:
            raise ValueError("Conflicting calendar events require review")
        events[day] = dict(day=day, scheduled=row["scheduled"])
    days = build_calendar(start, end, rules, list(events.values()))
    for row in days:
        connection.execute(
            text(
                "INSERT INTO calendar_dates(day,iso_year,iso_week,weekday,"
                "scheduled,rule_id,observed) "
                "VALUES(:day,:iso_year,:iso_week,:weekday,:scheduled,:rule_id, "
                "EXISTS(SELECT 1 FROM draws WHERE draw_date=:day "
                "AND status='accepted')) "
                "ON CONFLICT(day) DO UPDATE SET scheduled=EXCLUDED.scheduled, "
                "rule_id=EXCLUDED.rule_id,observed=EXCLUDED.observed"
            ),
            row,
        )
    return len(days)
