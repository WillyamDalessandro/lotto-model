import pytest

from lotto_model.ingestion.workflows import parse_csv


def test_csv_preserves_unknowns():
    rows = parse_csv(
        b"date,n1,n2,n3,n4,n5,n6,bonus,jackpot,currency,jackpotWinners\n2026-10-07,3,17,26,29,37,42,38,5664896,EUR,1\n",
        "https://example.test/export.csv",
    )
    assert rows[0].outcome == "Won" and rows[0].bonus == 38


def test_wrong_csv_not_silently_empty():
    with pytest.raises(ValueError):
        parse_csv(b"hello,world\n1,2", "https://example.test/export.csv")


def test_negative_jackpot_winners_rejected():
    with pytest.raises(ValueError):
        parse_csv(
            b"date,n1,n2,n3,n4,n5,n6,jackpotWinners\n2026-10-07,1,2,3,4,5,6,-1\n",
            "https://example.test/export",
        )


def test_truncated_csv_rejected():
    with pytest.raises(ValueError):
        parse_csv(
            b"date,n1,n2,n3,n4,n5,n6,jackpotWinners\n2026-10-07,1,2,3,4,5,6\n",
            "https://example.test/export",
        )
