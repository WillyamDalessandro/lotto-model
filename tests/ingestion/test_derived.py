from datetime import date
from decimal import Decimal

from lotto_model.ingestion.derived import build_calendar, derive_context


def test_unknown_calendar():
    days = build_calendar(date(2026, 1, 1), date(2026, 1, 3), [], [])
    assert len(days) == 3 and all(d["scheduled"] is None for d in days)


def test_gap_does_not_reset_rollover():
    rows = [
        dict(
            id=1,
            draw_date=date(2026, 1, 3),
            mains=[1, 2, 3, 4, 5, 6],
            outcome="Roll",
            prizes=[],
        ),
        dict(
            id=2,
            draw_date=date(2026, 1, 7),
            mains=[1, 2, 3, 4, 5, 7],
            outcome=None,
            prizes=[],
        ),
    ]
    values = derive_context(rows)
    assert values[0]["prior_rollover_streak"] is None
    assert values[1]["previous_overlap"] == 5
    assert values[1]["main_sum"] == 22


def test_unknown_mixed_payout():
    rows = [
        dict(
            id=1,
            draw_date=date(2026, 1, 3),
            mains=[1, 2, 3, 4, 5, 6],
            outcome="Won",
            prizes=[
                dict(
                    winners=2,
                    original_amount=Decimal("4"),
                    currency="EUR",
                    prize_type="ticket_or_cash",
                )
            ],
        )
    ]
    result = derive_context(rows)[0]
    assert result["face_values"]["EUR"] == "8"
    assert result["cash_only_eur"] is None


def test_unclassified_cash_subtotal_is_unknown():
    values = derive_context(
        [
            dict(
                id=1,
                draw_date=date(2026, 10, 7),
                mains=[1, 2, 3, 4, 5, 6],
                prizes=[
                    dict(
                        winners=1,
                        original_amount=Decimal("10"),
                        currency="EUR",
                        prize_type="unresolved",
                    )
                ],
            )
        ]
    )
    assert values[0]["cash_only_eur"] is None
