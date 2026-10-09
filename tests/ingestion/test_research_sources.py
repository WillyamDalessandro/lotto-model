import hashlib
from decimal import Decimal

import httpx
import pytest

from lotto_model.ingestion import research_sources as sources
from lotto_model.ingestion.evidence import EvidenceStore

JOURNAL = b"1 1 2 3 4 5 6\n2 4 17 37 10 21 29\n3 1 2 3 4 5 6\n"


def regulator_html():
    tables = [
        (
            "Sales, Prizes Won, and Good Causes Contribution",
            ["Year", "Sales", "Prizes Won", "Good Causes"],
            ["2022", "€884.1m", "€484.9m (54.8%)", "€259.9m (29.4%)"],
        ),
        (
            "Size of Retail Network since Licence Commenced",
            ["Year", "Number of retail agents at year end"],
            ["2022", "5225"],
        ),
        (
            "Retail and Online Sales as a Proportion of Total Sales",
            ["Year", "Retail as % total sales", "Online as % total sales"],
            ["2022", "84.0%", "16.0%"],
        ),
        (
            "Good Causes Funds Earned",
            ["Year", "Good Causes Funds Earned Annually"],
            ["2022", "€259.5m"],
        ),
        (
            "Prizes Won and Good Causes Contribution as % Sales",
            ["Year", "Prizes Won", "Good Causes"],
            ["2022", "54.8%", "29.4%"],
        ),
    ]
    html = "<h1>Key Commercial Metrics</h1>"
    for heading, headers, values in tables:
        html += f"<h2>{heading}</h2><table><tr>"
        html += "".join(f"<th>{x}</th>" for x in headers) + "</tr><tr>"
        html += "".join(f"<td>{x}</td>" for x in values) + "</tr></table>"
    return html.encode()


def test_journal_excludes_students_and_simulations_without_inventing_dates():
    rows = sources.parse_journal(JOURNAL)
    assert len(rows) == 1
    row = rows[0]
    assert row.mains == (4, 10, 17, 21, 29, 37)
    assert row.source_row == 2
    assert row.draw_date is None and row.bonus is None
    assert str(row.reported_period_start) == "1994-09-24"
    assert str(row.reported_period_end) == "1997-03-08"
    assert row.pool == 42


@pytest.mark.parametrize(
    "body",
    [
        b"2 1 2 3 4 5 43",
        b"2 1 2 3 4 5 5",
        b"2 1 2 3 4 5",
        b"4 1 2 3 4 5 6",
        b"<html>not found</html>",
        b"1 1 2 3 4 5 6",
    ],
)
def test_journal_rejects_unknown_groups_and_invalid_actual_results(body):
    with pytest.raises(ValueError):
        sources.parse_journal(body)


def test_regulator_preserves_rounding_scope_and_conflicting_sections():
    rows = sources.parse_regulator(regulator_html())
    assert len(rows) == 11
    assert all(r.payload["game_scope"] == "all_national_lottery_games" for r in rows)
    good = [r for r in rows if r.payload["metric"] == "good_causes_contribution"]
    assert [r.payload["value"] for r in good] == ["259900000.0", "259500000.0"]
    assert len({r.record_key for r in good}) == 2
    assert good[0].payload["source_unit"] == "million EUR"
    assert Decimal(good[0].payload["rounding_increment"]) == Decimal("100000")
    assert good[0].payload["original_text"] == "€259.9m (29.4%)"
    assert good[0].payload["currency"] == "EUR"
    assert rows[5].payload["value"] == "5225"


@pytest.mark.parametrize("replacement", ["£884.1m", "€884.1", "€NaNm"])
def test_regulator_rejects_ambiguous_or_malformed_money(replacement):
    body = regulator_html().decode().replace("€884.1m", replacement).encode()
    with pytest.raises(ValueError):
        sources.parse_regulator(body)


def test_regulator_rejects_missing_sections_and_schema_drift():
    with pytest.raises(ValueError):
        sources.parse_regulator(b"<html>Key Commercial Metrics unavailable</html>")
    with pytest.raises(ValueError):
        sources.parse_regulator(
            regulator_html().replace(b"Online as % total sales", b"Online")
        )


def test_collector_verifies_policy_and_caches_all_evidence(tmp_path, monkeypatch):
    bodies = {
        sources.JOURNAL_POLICY_URL: b"journal reviewed policy",
        sources.REGULATOR_POLICY_URL: b"regulator reviewed policy",
        sources.JOURNAL_DOC_URL: b"reviewed documentation",
        sources.JOURNAL_URL: JOURNAL,
        sources.REGULATOR_URL: regulator_html(),
    }
    monkeypatch.setattr(
        sources,
        "REVIEWED_HASHES",
        {
            url: hashlib.sha256(body).hexdigest()
            for url, body in bodies.items()
            if url != sources.REGULATOR_URL
        },
    )
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=bodies[str(request.url)])

    client = httpx.Client(transport=httpx.MockTransport(respond))
    store = EvidenceStore(tmp_path)
    batch = sources.collect_research(store, client=client, sleep=lambda _: None)
    assert len(batch.observations) == 1 and len(batch.metrics) == 11
    assert len(batch.artifacts) == 5
    assert all(a.sha256 for a in batch.artifacts)
    sources.collect_research(store, client=client, sleep=lambda _: None)
    assert len(calls) == 5


def test_collector_stops_on_changed_policy_before_acquiring_datasets(tmp_path):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=b"changed policy")

    with pytest.raises(ValueError, match="review"):
        sources.collect_research(
            EvidenceStore(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(respond)),
            sleep=lambda _: None,
        )
    assert len(calls) == 1
