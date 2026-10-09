from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lotto_model.ingestion.parsers import ParseError, parse_lottonet_year

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ingestion" / "lottonet-2015.html"
URL = "https://www.lotto.net/irish-lotto/results/2015"


def test_year_page_parses_dates_numbers_and_outcomes():
    rows = parse_lottonet_year(FIXTURE.read_bytes(), URL)
    assert [r.draw_date for r in rows] == [date(2015, 9, 2), date(2015, 9, 5)]
    assert rows[0].mains == (1, 9, 17, 25, 40, 45) and rows[0].bonus == 3
    assert rows[0].outcome == "Won" and rows[1].outcome == "Roll"
    assert rows[1].jackpot == Decimal("2000000") and rows[1].currency == "EUR"


def test_pre_euro_jackpots_are_not_assigned_a_currency():
    body = FIXTURE.read_bytes().replace(b"2015", b"1995")
    body = body.replace(
        b"Saturday</span> September 5th", b"Tuesday</span> September 5th"
    )
    body = body.replace(
        b"Wednesday</span> September 2nd", b"Saturday</span> September 2nd"
    )
    rows = parse_lottonet_year(body, URL.replace("2015", "1995"))
    assert all(r.jackpot is None and r.currency is None for r in rows)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"Saturday</span> September 5th", b"Monday</span> September 5th"),
        (b"September 5th 2015", b"September 5th 2014"),
        (b'<li class="ball ball"><span>2</span></li>', b""),
        (b"<span>11</span>", b"<span>20</span>"),
    ],
)
def test_inconsistent_pages_are_rejected(old, new):
    with pytest.raises(ParseError):
        parse_lottonet_year(FIXTURE.read_bytes().replace(old, new), URL)


def test_wrong_path_and_empty_page_are_rejected():
    with pytest.raises(ParseError):
        parse_lottonet_year(FIXTURE.read_bytes(), URL + "/extra")
    with pytest.raises(ParseError):
        parse_lottonet_year(b"<html><title>Archive</title></html>", URL)


def test_fixed_jackpot_second_draw_on_same_date_is_skipped():
    body = FIXTURE.read_bytes()
    first = body.index(b'<div class="results-vsmall')
    end = body.index(b'<div class="results-vsmall', first + 1)
    block = body[first:end]
    second = block.replace("€2,000,000".encode(), "€500,000".encode())
    second = second.replace(b"<span>2</span>", b"<span>3</span>")
    rows = parse_lottonet_year(body[:end] + second + body[end:], URL)
    assert [r.mains[0] for r in rows] == [1, 2]
    with pytest.raises(ParseError, match="Duplicate"):
        parse_lottonet_year(body[:end] + block + body[end:], URL)
