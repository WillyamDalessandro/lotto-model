import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import ValidationError

from lotto_model.ingestion.contracts import Observation, PrizeObservation

PARSER_VERSION = "1"


class ParseError(ValueError):
    pass


def soup_for(body):
    soup = BeautifulSoup(body.decode("utf-8"), "html.parser")
    if soup.title and re.search(
        r"captcha|access denied|just a moment|not found", soup.title.get_text(), re.I
    ):
        raise ParseError("Blocked or error page")
    return soup


def money(value):
    currency = "EUR" if "€" in value else ("POUND_UNRESOLVED" if "£" in value else None)
    match = re.search(r"[€£]\s*([\d,]+(?:\.\d+)?)", value)
    return (Decimal(match[1].replace(",", "")) if match else None, currency)


def tier(label):
    return re.sub(r"\s+", " ", label.replace("plus", "+")).replace("Jackpot", "Match 6")


def prizes(table, operator=False):
    output = []
    if table is None:
        return output
    for row in table.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.select("td")]
        if len(cells) < 3 or not (
            cells[0].startswith("Match") or cells[0] == "Jackpot"
        ):
            continue
        published = cells[2] if operator else cells[1]
        winners = cells[1] if operator else cells[2]
        amount, currency = money(published)
        kind = (
            "ticket_or_cash"
            if re.search(r"Quick Pick|ticket", published, re.I)
            else "unresolved"
        )
        output.append(
            PrizeObservation(
                tier=tier(cells[0]),
                winners=int(winners.replace(",", ""))
                if re.fullmatch(r"[\d,]+", winners)
                else None,
                amount=amount,
                currency=currency,
                original_text=published,
                prize_type=kind,
            )
        )
    return output


def parse_archive(body: bytes, url: str) -> list[Observation]:
    soup = soup_for(body)
    output = {}
    try:
        for row in soup.select("tr"):
            link = row.find(
                "a", href=re.compile(r"/irish-lotto/results-\d{2}-\d{2}-\d{4}$")
            )
            balls = row.select("ul.balls li")
            if link is None or not balls:
                continue
            draw_date = datetime.strptime(link["href"][-10:], "%d-%m-%Y").date()
            mains = [
                int(b.get_text(strip=True))
                for b in balls
                if "bonus-ball" not in b.get("class", [])
            ]
            bonus = [
                int(b.get_text(strip=True))
                for b in balls
                if "bonus-ball" in b.get("class", [])
            ]
            cell = row.find("td", attrs={"data-title": "Jackpot"})
            amount, currency = money(cell.get_text() if cell else "")
            outcome_cell = row.find("td", attrs={"data-title": "Outcome"})
            outcome = outcome_cell.get_text(strip=True) if outcome_cell else None
            observation = Observation(
                draw_date=draw_date,
                mains=mains,
                bonus=bonus[0] if len(bonus) == 1 else None,
                source_url=urljoin(url, link["href"]),
                jackpot=amount,
                currency=currency,
                outcome=outcome if outcome in ("Won", "Roll") else None,
            )
            if draw_date in output and output[draw_date] != observation:
                raise ParseError("Conflicting rows in archive")
            output[draw_date] = observation
    except (ValueError, ValidationError) as exc:
        raise ParseError("Invalid archive record") from exc
    if not output:
        raise ParseError("No main Lotto archive rows")
    return sorted(output.values(), key=lambda r: r.draw_date)


def parse_detail(body: bytes, url: str) -> Observation:
    soup = soup_for(body)
    match = re.search(r"(?:result|results)-(\d{2}-\d{2}-\d{4})$", url)
    header = soup.find("h1")
    if (
        not match
        or header is None
        or "Lotto" not in header.get_text()
        or "Plus" in header.get_text()
    ):
        raise ParseError("Unrecognised detail page")
    day = datetime.strptime(match[1], "%d-%m-%Y").date()
    title = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", header.get_text())
    date_match = re.search(r"(\d{1,2} \w+ \d{4})", title)
    if not date_match or datetime.strptime(date_match[1], "%d %B %Y").date() != day:
        raise ParseError("URL and published draw date disagree")
    lists = soup.select("ul.ballRow, ul.balls")
    if len(lists) != 1 or lists[0].find_parent(["aside", "nav"]):
        raise ParseError("Missing or ambiguous main numbers")
    ball_list = lists[0]
    numbers = [int(x.get_text(strip=True)) for x in ball_list.select("li")]
    if len(numbers) not in (6, 7):
        raise ParseError("Unexpected number cardinality")
    tables = soup.select("table.breakdownTable, table.prizeTable")
    if not tables:
        tables = ball_list.parent.find_all("table", recursive=False)
    if len(tables) > 1:
        raise ParseError("Ambiguous prize table")
    table = tables[0] if tables else None
    return Observation(
        draw_date=day,
        mains=numbers[:6],
        bonus=numbers[6] if len(numbers) == 7 else None,
        source_url=url,
        prizes=prizes(table),
    )


def parse_operator(body: bytes, url: str) -> list[Observation]:
    soup = soup_for(body)
    title = soup.find("h1")
    if (
        parse_qs(urlparse(url).query).get("game") != ["lotto"]
        or title is None
        or not re.fullmatch(
            r"(?:Latest |Irish )?Lotto Results", title.get_text(strip=True)
        )
    ):
        raise ParseError("Unverified main Lotto page identity")
    output = []
    for header in soup.find_all("h2"):
        match = re.search(r"\b(\d{2}/\d{2}/\d{2})\b", header.get_text())
        if not match:
            continue
        if "Plus" in header.get_text():
            raise ParseError("Wrong game section")
        # The reviewed operator layout places main Lotto in the first result card.
        cards = header.parent.find_all("div", recursive=False)
        if not cards:
            raise ParseError("Missing main Lotto result card")
        section = cards[0]
        table = section.find("table")
        label = section.find(string="Winning numbers")
        if label is None or table is None:
            continue
        main_container = label.parent.parent
        mains = [
            int(x.get_text(strip=True))
            for x in main_container.select("div.rounded-full")
        ]
        bonus_label = section.find(string="Bonus")
        bonus_container = bonus_label.parent.parent if bonus_label else None
        bonus_ball = (
            bonus_container.select_one("div.rounded-full") if bonus_container else None
        )
        breakdown = prizes(table, operator=True)
        prize = next((p for p in breakdown if p.tier == "Match 6"), None)
        jackpot_label = section.find(string="Jackpot")
        jackpot_text = (
            jackpot_label.parent.parent.parent.get_text(" ") if jackpot_label else ""
        )
        amount, currency = money(jackpot_text)
        output.append(
            Observation(
                draw_date=datetime.strptime(match[1], "%d/%m/%y").date(),
                mains=mains,
                bonus=int(bonus_ball.get_text()) if bonus_ball else None,
                source_url=url,
                jackpot=amount,
                currency=currency,
                prizes=breakdown,
                outcome=("Won" if prize.winners else "Roll")
                if prize and prize.winners is not None
                else None,
            )
        )
    if not output:
        raise ParseError("No operator main Lotto results")
    return output


LOTTONET_DATE = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) "
    r"([A-Z][a-z]+) (\d{1,2})(?:st|nd|rd|th) (\d{4})"
)
LOTTONET_OUTCOME = {"Rollover!": "Roll", "Jackpot Won!": "Won"}
EURO_START = datetime(2002, 1, 1).date()
SECOND_DRAW_JACKPOT = "€500,000"


def parse_lottonet_year(body: bytes, url: str) -> list[Observation]:
    """One lotto.net yearly archive: date, six mains, bonus, jackpot, outcome."""
    match = re.fullmatch(r"/irish-lotto/results/(\d{4})", urlparse(url).path)
    if not match:
        raise ParseError("Unsupported lotto.net path")
    year = int(match[1])
    soup = soup_for(body)
    output = {}
    try:
        for block in soup.select("div.archive-list"):
            label = block.select_one("div.date").get_text(" ", strip=True)
            found = LOTTONET_DATE.fullmatch(label)
            if not found:
                raise ParseError("Unrecognized draw date")
            weekday, month, day, published_year = found.groups()
            draw_date = datetime.strptime(
                f"{day} {month} {published_year}", "%d %B %Y"
            ).date()
            if draw_date.year != year or draw_date.strftime("%A") != weekday:
                raise ParseError("Draw date disagrees with archive year or weekday")
            balls = block.select("ul.balls li")
            mains = [
                int(b.get_text(strip=True))
                for b in balls
                if "bonus-ball" not in b.get("class", [])
            ]
            bonus = [
                int(b.select_one("span").get_text(strip=True))
                for b in balls
                if "bonus-ball" in b.get("class", [])
            ]
            if len(bonus) > 1:
                raise ParseError("Several bonus numbers")
            jackpot, currency = None, None
            pot = block.select_one("div.jackpot > span")
            if draw_date in output:
                # 1994-1998 pages list a fixed-jackpot second draw after the main
                # Lotto draw on some dates; keep the main draw, reject anything else.
                if pot is None or pot.get_text(strip=True) != SECOND_DRAW_JACKPOT:
                    raise ParseError("Duplicate draw date")
                continue
            # Pre-euro jackpots are shown converted; the source currency is unknown.
            if pot is not None and draw_date >= EURO_START:
                jackpot, currency = money(pot.get_text(strip=True))
            flag = block.select_one(".rollover")
            outcome = LOTTONET_OUTCOME.get(flag.get_text(strip=True)) if flag else None
            output[draw_date] = Observation(
                draw_date=draw_date,
                mains=mains,
                bonus=bonus[0] if bonus else None,
                source_url=url,
                jackpot=jackpot,
                currency=currency,
                outcome=outcome,
            )
    except ParseError:
        raise
    except (AttributeError, ValueError, ValidationError) as exc:
        raise ParseError("Unexpected lotto.net archive structure") from exc
    if not output:
        raise ParseError("No draws in archive page")
    return [output[d] for d in sorted(output)]


LOTTONET_DETAIL = re.compile(r"/irish-lotto/results/([a-z]+)-(\d{2})-(\d{4})")
LOTTONET_TITLE = re.compile(
    r"Irish Lotto Results for [A-Z][a-z]+ "
    r"(\d{1,2})(?:st|nd|rd|th) ([A-Z][a-z]+) (\d{4})"
)


def _lottonet_prizes(table, draw_date):
    rows = table.select("tr")
    header = [c.get_text(" ", strip=True) for c in rows[0].select("th,td")]
    if not header or header[0] != "Prize Level":
        raise ParseError("Unexpected prize table header")
    output = []
    for row in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in row.select("td")]
        if not cells or cells[0] == "Totals":
            continue
        if len(cells) < 3 or not cells[0].startswith("Match"):
            raise ParseError("Unexpected prize row")
        # The jackpot row prefixes its winner count with a "Rollover!" flag.
        published = cells[1]
        winners = cells[2].removeprefix("Rollover!").strip().replace(",", "")
        amount, currency = money(published)
        if draw_date < EURO_START:
            amount, currency = None, None
        output.append(
            PrizeObservation(
                tier=tier(cells[0]),
                winners=int(winners) if winners.isdigit() else None,
                amount=amount if published != "-" else None,
                currency=currency if published != "-" else None,
                original_text=published,
                prize_type="ticket_or_cash"
                if re.search(r"Quick Pick|ticket|Scratch Card", published, re.I)
                else "unresolved",
            )
        )
    if not output:
        raise ParseError("Empty prize table")
    return output


def parse_lottonet_detail(body: bytes, url: str) -> Observation:
    """One lotto.net draw page: main Lotto numbers and its prize table only."""
    path = LOTTONET_DETAIL.fullmatch(urlparse(url).path)
    if not path:
        raise ParseError("Unsupported lotto.net draw path")
    soup = soup_for(body)
    try:
        titled = LOTTONET_TITLE.fullmatch(soup.title.get_text(strip=True))
        draw_date = datetime.strptime(" ".join(titled.groups()), "%d %B %Y").date()
        if draw_date != datetime.strptime(" ".join(path.groups()), "%B %d %Y").date():
            raise ParseError("Draw page title disagrees with its address")
        balls = soup.select_one("ul.balls").select("li")
        mains = [
            int(b.get_text(strip=True))
            for b in balls
            if "bonus-ball" not in b.get("class", [])
        ]
        bonus = [
            int(b.select_one("span").get_text(strip=True))
            for b in balls
            if "bonus-ball" in b.get("class", [])
        ]
        table = soup.select_one("table")
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        if heading.get_text(strip=True) != "Prize Breakdown":
            raise ParseError("First prize table is not the main Lotto draw")
        return Observation(
            draw_date=draw_date,
            mains=mains,
            bonus=bonus[0] if len(bonus) == 1 else None,
            source_url=url,
            prizes=_lottonet_prizes(table, draw_date),
        )
    except ParseError:
        raise
    except (AttributeError, ValueError, ValidationError) as exc:
        raise ParseError("Unexpected lotto.net draw page structure") from exc
