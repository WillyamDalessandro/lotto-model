from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lotto_model.ingestion.parsers import (
    ParseError,
    parse_lottonet_detail,
    parse_lottonet_year,
)

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


DRAW = (
    Path(__file__).parents[1]
    / "fixtures"
    / "ingestion"
    / "lottonet-draw-2015-09-05.html"
)
DRAW_URL = "https://www.lotto.net/irish-lotto/results/september-05-2015"


def test_draw_page_parses_main_prize_table_only():
    observation = parse_lottonet_detail(DRAW.read_bytes(), DRAW_URL)
    assert observation.draw_date == date(2015, 9, 5)
    assert observation.mains == (2, 11, 20, 33, 46, 47) and observation.bonus == 5
    tiers = {p.tier: p for p in observation.prizes}
    assert len(tiers) == 8
    assert tiers["Match 6"].winners == 0
    assert tiers["Match 3"].winners == 9000
    assert tiers["Match 2 + Bonus"].prize_type == "ticket_or_cash"
    assert tiers["Match 5"].amount == Decimal("1000")


def test_draw_page_rejects_mismatched_address_and_missing_table():
    with pytest.raises(ParseError):
        parse_lottonet_detail(DRAW.read_bytes(), DRAW_URL.replace("05", "06", 1))
    with pytest.raises(ParseError):
        parse_lottonet_detail(
            DRAW.read_bytes().replace(b"<h2>Prize Breakdown</h2>", b"<h2>Other</h2>"),
            DRAW_URL,
        )


def test_pre_euro_prize_amounts_are_unassigned():
    body = DRAW.read_bytes().replace(b"2015", b"1995").replace(b"Saturday", b"Tuesday")
    observation = parse_lottonet_detail(body, DRAW_URL.replace("2015", "1995"))
    assert all(p.amount is None and p.currency is None for p in observation.prizes)
