"""Reviewed public datasets for private, unpublished research."""

import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from lotto_model.ingestion.complementary import ComplementaryRecord
from lotto_model.ingestion.contracts import UndatedObservation
from lotto_model.ingestion.fetch import AccessPolicy, Fetcher

JOURNAL_URL = "https://jse.amstat.org/datasets/lotto.dat.txt"
JOURNAL_DOC_URL = "https://jse.amstat.org/datasets/lotto.txt"
JOURNAL_POLICY_URL = "https://jse.amstat.org/jse_users.htm"
REGULATOR_URL = "https://www.rnl.ie/data-publications/key-commercial-metrics/"
REGULATOR_POLICY_URL = "https://www.rnl.ie/privacy/"
REVIEWED_HASHES = {
    JOURNAL_DOC_URL: "1391da62d19f1bce2eafb22d0ad8b5816561a915ba63705992ee19d9084ffdf4",
    JOURNAL_URL: "2c6b0fe860960a3d9e80050df32e32f1c00b123eda65786e027110bf07239582",
    JOURNAL_POLICY_URL: (
        "27e543d88c24772a1e1d6e867e25c9edc51cc5ac8cf8b2647e7264e13ed3aaf1"
    ),
    REGULATOR_POLICY_URL: (
        "822f73a312b4d0e77b24ae75f8d0eaa1b4b664c8b07dcf3bb6f8eae1e37e2b99"
    ),
}


def parse_journal(body: bytes):
    observations = []
    for row_number, line in enumerate(body.decode("utf8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 7 or fields[0] not in ("1", "2", "3"):
            raise ValueError("Unrecognized journal row")
        # Groups 1 and 3 are human selections and simulations, not winning draws.
        if fields[0] != "2":
            continue
        numbers = tuple(int(n) for n in fields[1:])
        observations.append(
            UndatedObservation(
                mains=tuple(sorted(numbers)),
                source_numbers=numbers,
                pool=42,
                source_row=row_number,
                source_url=JOURNAL_URL,
                reported_period_start="1994-09-24",
                reported_period_end="1997-03-08",
                attribution=(
                    "Lotto 6/42 Selections from Individuals, Irish National "
                    "Lottery, and S-Plus Simulation; Philip J. Boland and "
                    "Yudi Pawitan; Journal of Statistics Education (1999)"
                ),
            )
        )
    if not observations:
        raise ValueError("No actual winning combinations")
    return observations


# Each specification lists the exact reviewed heading, headers and cell metrics.
TABLES = {
    "Sales, Prizes Won, and Good Causes Contribution": (
        "sales_prizes_good_causes",
        ["Year", "Sales", "Prizes Won", "Good Causes"],
        [
            (1, "ticket_sales", "money"),
            (2, "prizes_won", "money"),
            (2, "prizes_won_share_of_ticket_sales", "embedded_percent"),
            (3, "good_causes_contribution", "money"),
            (3, "good_causes_share_of_ticket_sales", "embedded_percent"),
        ],
    ),
    "Size of Retail Network since Licence Commenced": (
        "retail_network",
        ["Year", "Number of retail agents at year end"],
        [(1, "retail_agents_at_year_end", "count")],
    ),
    "Retail and Online Sales as a Proportion of Total Sales": (
        "sales_channels",
        ["Year", "Retail as % total sales", "Online as % total sales"],
        [(1, "retail_sales_share", "percent"), (2, "online_sales_share", "percent")],
    ),
    "Good Causes Funds Earned": (
        "good_causes_funds",
        ["Year", "Good Causes Funds Earned Annually"],
        [(1, "good_causes_contribution", "money")],
    ),
    "Prizes Won and Good Causes Contribution as % Sales": (
        "prizes_good_causes_percent",
        ["Year", "Prizes Won", "Good Causes"],
        [
            (1, "prizes_won_share_of_ticket_sales", "percent"),
            (2, "good_causes_share_of_ticket_sales", "percent"),
        ],
    ),
}


def _cell_value(cell, kind):
    if kind == "money":
        match = re.fullmatch(r"€(\d+(?:\.\d+)?)m(?: \(\d+(?:\.\d+)?%\))?", cell)
        if not match:
            raise ValueError("Unreviewed money units")
        value = Decimal(match[1]) * 1_000_000
        precision = Decimal(10) ** Decimal(-len(match[1].partition(".")[2]))
        return str(value), "EUR", "EUR", "million EUR", str(precision * 1_000_000)
    if kind == "count":
        if not re.fullmatch(r"\d+", cell):
            raise ValueError("Invalid retailer count")
        return cell, "count", None, "count", "1"
    pattern = (
        r".* \((\d+(?:\.\d+)?)%\)"
        if kind == "embedded_percent"
        else r"(\d+(?:\.\d+)?)%"
    )
    match = re.fullmatch(pattern, cell)
    if not match or not 0 <= Decimal(match[1]) <= 100:
        raise ValueError("Invalid sales percentage")
    precision = Decimal(10) ** Decimal(-len(match[1].partition(".")[2]))
    return match[1], "percent", None, "percent", str(precision)


def parse_regulator(body: bytes):
    soup = BeautifulSoup(body.decode("utf8"), "html.parser")
    title = soup.find("h1")
    if not title or title.get_text(" ", strip=True) != "Key Commercial Metrics":
        raise ValueError("Unrecognized regulator document")
    records, seen = [], set()
    for table in soup.find_all("table"):
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        heading = heading.get_text(" ", strip=True) if heading else ""
        if heading not in TABLES or heading in seen:
            raise ValueError("Unreviewed regulator section")
        seen.add(heading)
        section, headers, metrics = TABLES[heading]
        rows = table.find_all("tr")

        def cells(row):
            return [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]

        if not rows or cells(rows[0]) != headers or len(rows) < 2:
            raise ValueError("Regulator table schema changed")
        years = set()
        for row in rows[1:]:
            values = cells(row)
            if len(values) != len(headers) or not re.fullmatch(r"20\d{2}", values[0]):
                raise ValueError("Invalid regulator row")
            year = values[0]
            if year in years:
                raise ValueError("Duplicate reporting year")
            years.add(year)
            for column, metric, kind in metrics:
                value, unit, currency, source_unit, rounding = _cell_value(
                    values[column], kind
                )
                records.append(
                    ComplementaryRecord(
                        dataset="official_period_metrics",
                        record_key=f"rnl:{section}:{year}:{metric}",
                        payload=dict(
                            period_start=f"{year}-01-01",
                            period_end=f"{year}-12-31",
                            game_scope="all_national_lottery_games",
                            metric=metric,
                            value=value,
                            unit=unit,
                            currency=currency,
                            source_unit=source_unit,
                            rounding_increment=rounding,
                            original_text=values[column],
                            section=heading,
                            source_url=REGULATOR_URL,
                            publisher="Regulator of the National Lottery",
                            copyright=(
                                "© Regulator of the National Lottery; "
                                "third-party rights reserved"
                            ),
                            usage="personal_use_only_no_publication_or_commercial_use",
                            license=None,
                            extraction="rnl_tables_v1",
                        ),
                    )
                )
    if seen != set(TABLES):
        raise ValueError("Missing regulator tables")
    return records


@dataclass
class ResearchBatch:
    observations: list
    metrics: list
    artifacts: list


def collect_research(store, *, client=None, **fetch_options):
    urls = [
        JOURNAL_POLICY_URL,
        REGULATOR_POLICY_URL,
        JOURNAL_DOC_URL,
        JOURNAL_URL,
        REGULATOR_URL,
    ]
    allowed = {}
    for url in urls:
        parsed = urlparse(url)
        allowed.setdefault(parsed.hostname, []).append(parsed.path)
    owned = client is None
    client = client or httpx.Client(
        timeout=20, headers={"User-Agent": "lotto-model-research/0.1"}
    )
    fetcher = Fetcher(
        store, client=client, policy=AccessPolicy(allowed), **fetch_options
    )
    artifacts = []
    try:
        for url in urls:
            validator = None
            if url == REGULATOR_URL:

                def validator(body):
                    parse_regulator(body)
                    return True

            artifact = fetcher.fetch(url, validator=validator)
            if artifact.status != "valid":
                raise ValueError("Research source unavailable; review saved evidence")
            if url in REVIEWED_HASHES and artifact.sha256 != REVIEWED_HASHES[url]:
                raise ValueError("Research policy or dataset changed; review required")
            artifacts.append(artifact)
        journal, regulator = artifacts[-2:]
        return ResearchBatch(
            [(row, journal) for row in parse_journal(store.read(journal))],
            [(record, regulator) for record in parse_regulator(store.read(regulator))],
            artifacts,
        )
    finally:
        if owned:
            client.close()
