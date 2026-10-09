from decimal import Decimal
from pathlib import Path

import pytest

from lotto_model.ingestion.parsers import ParseError, parse_archive, parse_detail

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ingestion"


def test_archive():
    rows = parse_archive(
        (FIXTURES / "archive.html").read_bytes(),
        "https://irish.national-lottery.com/irish-lotto/results-archive-2026",
    )
    assert len(rows) == 1
    assert rows[0].mains == (3, 17, 26, 29, 37, 42)
    assert rows[0].bonus == 38
    assert rows[0].jackpot == Decimal("5664896")


def test_old_unknowns():
    row = parse_archive(
        (FIXTURES / "old.html").read_bytes(),
        "https://irish.national-lottery.com/irish-lotto/results-archive-1988",
    )[0]
    assert row.bonus is None
    assert row.currency == "POUND_UNRESOLVED"
    assert row.outcome is None


def test_detail():
    row = parse_detail(
        (FIXTURES / "detail.html").read_bytes(),
        "https://www.irishlottery.com/results/irish-lotto-result-07-10-2026",
    )
    assert row.bonus == 38
    assert len(row.prizes) == 8
    assert row.prizes[1].winners == 0
    assert row.prizes[0].amount == Decimal("5664896")


@pytest.mark.parametrize("body", [b"<html>captcha</html>", b"<html>Not found</html>"])
def test_invalid_page(body):
    with pytest.raises(ParseError):
        parse_archive(
            body, "https://irish.national-lottery.com/irish-lotto/results-archive-2026"
        )


def test_detail_rejects_eight_numbers():
    body = (
        b'<h1>Lotto Results 7 October 2026</h1><ul class="balls">'
        + b"".join(f"<li>{n}</li>".encode() for n in range(1, 9))
        + b"</ul>"
    )
    with pytest.raises(ParseError):
        parse_detail(body, "https://www.irishlottery.com/results-07-10-2026")


def test_plus_detail_contamination_is_rejected():
    body = (
        b"<h1>Lotto Results 7 October 2026</h1>"
        b'<aside><h2>Lotto Plus 1</h2><ul class="balls">'
        + b"".join(f"<li>{n}</li>".encode() for n in range(1, 8))
        + b'</ul></aside><section><h2>Main Lotto</h2><ul class="balls">'
        + b"".join(f"<li>{n}</li>".encode() for n in range(10, 17))
        + b"</ul></section>"
    )
    with pytest.raises(ParseError):
        parse_detail(body, "https://www.irishlottery.com/results-07-10-2026")


def test_operator_plus_game_is_rejected():
    from lotto_model.ingestion.parsers import parse_operator

    body = b"<h1>Lotto Plus 1</h1><section><h2>Lotto Plus 1 07/10/26</h2></section>"
    with pytest.raises(ParseError):
        parse_operator(
            body, "https://www.lottery.ie/draw-games/results/view?game=lottoPlus1"
        )


def test_operator_main_card_isolated_from_plus():
    from lotto_model.ingestion.parsers import parse_operator

    rows = parse_operator(
        (FIXTURES / "operator.html").read_bytes(),
        "https://www.lottery.ie/draw-games/results/view?game=lotto&lang=en",
    )
    assert len(rows) == 1
    assert rows[0].mains == (3, 17, 26, 29, 37, 42)
    assert rows[0].bonus == 38
    assert len(rows[0].prizes) == 8
    assert rows[0].prizes[0].winners == 0
    assert rows[0].prizes[-1].prize_type == "ticket_or_cash"
