from datetime import date

from lotto_model.ingestion.calendar import materialize_calendar


def test_calendar_keeps_unverified_days_unknown(connection):
    count = materialize_calendar(connection, date(2026, 1, 1), date(2026, 1, 3))
    assert count == 3
    assert (
        connection.exec_driver_sql(
            "SELECT count(*) FROM calendar_dates WHERE scheduled IS NULL"
        ).scalar_one()
        == 3
    )
    assert materialize_calendar(connection, date(2026, 1, 1), date(2026, 1, 3)) == 3
    assert (
        connection.exec_driver_sql("SELECT count(*) FROM calendar_dates").scalar_one()
        == 3
    )
