"""Full-history backfill from reviewed permitted sources (Phase 7.1).

Draws: lotto.net yearly archives. Its published disclaimer allows personal use,
it has no harvesting prohibition and robots.txt allows these paths. Requests
are rate limited and cached; data stays local and is never redistributed.
Rules: the Wikipedia article (CC BY-SA) checked for every reviewed phrase, plus
the 2015 trade announcement for the 6/47 start date.
"""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.fetch import AccessPolicy, Fetcher
from lotto_model.ingestion.repository import Repository
from lotto_model.ingestion.workflows import import_manifest

LOTTONET = "https://www.lotto.net/irish-lotto/results/{year}"
WIKIPEDIA_URL = (
    "https://en.wikipedia.org/w/index.php?title=National_Lottery_(Ireland)&action=raw"
)
ANNOUNCEMENT_URL = (
    "https://www.shelflife.ie/national-lottery-debuts-bigger-better-lotto/"
)
FIRST_YEAR = 1988
CRAWL_DELAY = 3
POLICY = AccessPolicy(
    {
        "www.lotto.net": ["/irish-lotto/results"],
        "en.wikipedia.org": ["/w/index.php"],
        "www.shelflife.ie": ["/national-lottery-debuts-bigger-better-lotto"],
    },
    {"www.lotto.net": CRAWL_DELAY, "en.wikipedia.org": CRAWL_DELAY},
)
# Each phrase must appear verbatim in the evidence that supports the interval.
WIKIPEDIA_PHRASES = (
    "The inaugural Lotto draw was held on Saturday, 16 April 1988",
    "until 30 May 1990, when the first midweek Lotto draw was held",
    "6/39 game for drawings beginning on 22 August 1992",
    "changed Lotto to a 6/42 game on 24 September 1994",
    "In November 2006",
    "6/45 game",
    "The change took effect for drawings beginning 3 September 2015",
    "For draws beginning 5 September 2026",
    "A third Lotto draw was added on Monday nights, starting on 7 September",
)
ANNOUNCEMENT_PHRASES = (
    "Lotto 6/47 (currently Lotto 6/45) will take effect",
    "from <em>Thursday 3<sup>rd</sup> September.</em>",
)


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    starts_on: date
    ends_on: date | None
    pool: int
    schedule: tuple[int, ...]
    evidence: str


# Wikipedia gives only "November 2006" for 6/45, so 6/42 ends with October and
# 6/45 starts with the first Saturday draw of the changed game; the Wednesday
# 1 November 2006 draw stays staged instead of being assigned a guessed pool.
RULES = (
    RuleDefinition(
        "6/36-saturday", date(1988, 4, 16), date(1990, 5, 29), 36, (5,), WIKIPEDIA_URL
    ),
    RuleDefinition(
        "6/36", date(1990, 5, 30), date(1992, 8, 21), 36, (2, 5), WIKIPEDIA_URL
    ),
    RuleDefinition(
        "6/39", date(1992, 8, 22), date(1994, 9, 23), 39, (2, 5), WIKIPEDIA_URL
    ),
    RuleDefinition(
        "6/42", date(1994, 9, 24), date(2006, 10, 31), 42, (2, 5), WIKIPEDIA_URL
    ),
    RuleDefinition(
        "6/45", date(2006, 11, 4), date(2015, 9, 2), 45, (2, 5), WIKIPEDIA_URL
    ),
    RuleDefinition(
        "6/47", date(2015, 9, 3), date(2026, 9, 4), 47, (2, 5), ANNOUNCEMENT_URL
    ),
    RuleDefinition("6/45-2026", date(2026, 9, 5), None, 45, (0, 2, 5), WIKIPEDIA_URL),
)


def contains_all(phrases):
    return lambda body: all(p.encode() in body for p in phrases)


def archive_page(body: bytes) -> bool:
    return b'class="results-vsmall archive-list"' in body


def fetch_sources(store, start_year, end_year, *, client, refresh_from, **options):
    """Fetch rule evidence and yearly archives; cached years are not refetched."""
    fetcher = Fetcher(store, client=client, policy=POLICY, **options)
    evidence = {}
    for url, phrases in (
        (WIKIPEDIA_URL, WIKIPEDIA_PHRASES),
        (ANNOUNCEMENT_URL, ANNOUNCEMENT_PHRASES),
    ):
        artifact = fetcher.fetch(url, validator=contains_all(phrases))
        if artifact.status != "valid":
            raise ValueError(f"Rule evidence unavailable or changed: {url}")
        evidence[url] = artifact
    years = []
    for year in range(start_year, end_year + 1):
        artifact = fetcher.fetch(
            LOTTONET.format(year=year),
            refresh=year >= refresh_from,
            validator=archive_page,
        )
        if artifact.status != "valid":
            raise ValueError(f"Archive {year} unavailable ({artifact.status})")
        years.append(artifact)
    return evidence, years


def register_rules(engine, store, evidence):
    with engine.begin() as conn:
        repo = Repository(conn)
        run = repo.start_run({"rules": "backfill-reviewed-v1"})
        for rule in RULES:
            identifier = repo.record_artifact(
                evidence[rule.evidence],
                run,
                "rules:" + rule.evidence,
                "independent",
                evidence_root=store.root,
            )
            repo.add_rule(
                rule.code,
                rule.starts_on,
                rule.ends_on,
                rule.pool,
                list(rule.schedule),
                identifier,
            )
        repo.finish_run(run, "completed")


def backfill(
    engine,
    root: Path,
    start_year: int = FIRST_YEAR,
    end_year: int | None = None,
    *,
    client=None,
    refresh_from: int | None = None,
    **options,
) -> dict:
    """Fetch, register reviewed rules, then import every saved yearly archive."""
    end_year = end_year or date.today().year
    if not FIRST_YEAR <= start_year <= end_year <= date.today().year:
        raise ValueError("Invalid backfill year range")
    owned = client is None
    client = client or httpx.Client(
        timeout=30,
        headers={"User-Agent": "lotto-model-research/0.1 (personal research)"},
    )
    fetched = EvidenceStore(Path(root) / "backfill")
    try:
        evidence, years = fetch_sources(
            fetched,
            start_year,
            end_year,
            client=client,
            refresh_from=refresh_from or date.today().year,
            **options,
        )
    finally:
        if owned:
            client.close()
    register_rules(engine, fetched, evidence)
    selected = Path(root) / "backfill-import"
    selected.mkdir(parents=True, exist_ok=True)
    manifest = write_selection(fetched, years, selected)
    counts = import_manifest(engine, manifest, EvidenceStore(Path(root)), "auto")
    return dict(years=len(years), rules=len(RULES), observations=counts)


def write_selection(store, artifacts, directory: Path) -> Path:
    """A manifest naming exactly the selected archive bodies (latest per year)."""
    for artifact in artifacts:
        (directory / artifact.body_path).write_bytes(store.read(artifact))
    manifest = directory / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "artifacts": [a.model_dump(mode="json") for a in artifacts],
            },
            indent=2,
        ),
        encoding="utf8",
    )
    return manifest


DETAIL_LINK = re.compile(rb'href="(/irish-lotto/results/[a-z]+-\d{2}-\d{4})"')


def detail_urls(store, years) -> list[str]:
    """Per-draw prize pages linked from the saved yearly archives, in order."""
    found = []
    for artifact in years:
        for path in DETAIL_LINK.findall(store.read(artifact)):
            url = "https://www.lotto.net" + path.decode()
            if url not in found:
                found.append(url)
    return found


def draw_page(body: bytes) -> bool:
    return b"Prize Breakdown" in body and b"<table" in body


def backfill_prizes(
    engine,
    root: Path,
    start_year: int = FIRST_YEAR,
    end_year: int | None = None,
    *,
    client=None,
    **options,
) -> dict:
    """Fetch every draw's prize page (cached), then import numbers and prizes.

    The yearly archives must have been collected first. Draw numbers on each
    page are reconciled with the accepted draw; a disagreement quarantines it.
    """
    end_year = end_year or date.today().year
    fetched = EvidenceStore(Path(root) / "backfill")
    years = [
        fetched.cached(LOTTONET.format(year=year))
        for year in range(start_year, end_year + 1)
    ]
    if any(a is None for a in years):
        raise ValueError("Collect the yearly archives before prize pages")
    owned = client is None
    client = client or httpx.Client(
        timeout=30,
        headers={"User-Agent": "lotto-model-research/0.1 (personal research)"},
    )
    pages, failed = [], []
    try:
        fetcher = Fetcher(fetched, client=client, policy=POLICY, **options)
        for url in detail_urls(fetched, years):
            artifact = fetcher.fetch(url, validator=draw_page)
            (pages if artifact.status == "valid" else failed).append(artifact)
    finally:
        if owned:
            client.close()
    selected = Path(root) / "prize-import"
    selected.mkdir(parents=True, exist_ok=True)
    manifest = write_selection(fetched, pages, selected)
    counts = import_manifest(engine, manifest, EvidenceStore(Path(root)), "auto")
    return dict(pages=len(pages), unavailable=len(failed), observations=counts)
