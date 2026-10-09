"""Narrow, reviewed CC BY acquisition and version-pinned curated facts."""

import json

import httpx

from lotto_model.ingestion.complementary import ComplementaryRecord
from lotto_model.ingestion.fetch import AccessPolicy, Fetcher

METADATA_URL = (
    "https://data.gov.ie/api/3/action/package_show"
    "?id=exchequer-receipts-from-national-lottery-ticket-sales"
)
REPORT_URL = (
    "https://www.audit.gov.ie/en/find-report/publications/2022/"
    "19-exchequer-receipts-from-national-lottery-ticket-sales.pdf"
)
REPORT_PATH = (
    "/media/ii1bmrnu/19-exchequer-receipts-from-national-lottery-ticket-sales.pdf"
)
REVIEWED_SHA256 = "75aa108858385408f560ba2837943dbf4385ee3696a8d3355f8e119224e651f6"


def collect_official(store, *, client=None, **fetch_options):
    owned = client is None
    client = client or httpx.Client(
        timeout=20, headers={"User-Agent": "lotto-model-research/0.1"}
    )
    fetcher = Fetcher(
        store,
        client=client,
        policy=AccessPolicy(
            {
                "data.gov.ie": ["/api/3/action/package_show"],
                "www.audit.gov.ie": [REPORT_URL.split(".ie", 1)[1], REPORT_PATH],
            }
        ),
        **fetch_options,
    )
    try:
        metadata = fetcher.fetch(METADATA_URL)
        if metadata.status != "valid":
            raise ValueError("Official metadata unavailable")
        package = json.loads(store.read(metadata))
        if (
            not package.get("success")
            or package["result"].get("license_id") != "CC-BY-4.0"
        ):
            raise ValueError("Unreviewed source license")
        if REPORT_URL not in [r["url"] for r in package["result"]["resources"]]:
            raise ValueError("Official report resource changed; review required")
        report = fetcher.fetch(
            REPORT_URL, validator=lambda body: body.startswith(b"%PDF-")
        )
        if report.status != "valid":
            raise ValueError("Official resource is not an accessible PDF")
        if report.sha256 != REVIEWED_SHA256:
            raise ValueError("Report bytes changed; curated values require review")
        records = []
        for metric, value, paragraph, page in [
            ("online_sales_share", "16.6", "19.10", 3),
            ("prizes_won_share_of_ticket_sales", "55.6", "19.11", 4),
        ]:
            record = ComplementaryRecord(
                dataset="official_period_metrics",
                record_key=f"cag:2021:{metric}",
                payload=dict(
                    period_start="2021-01-01",
                    period_end="2021-12-31",
                    game_scope="all_national_lottery_games",
                    metric=metric,
                    value=value,
                    unit="percent",
                    currency=None,
                    paragraph=paragraph,
                    pdf_page=page,
                    license="CC-BY-4.0",
                    publisher="Office of the Comptroller and Auditor General",
                    source_url=REPORT_URL,
                    extraction="reviewed_curated_v1",
                ),
            )
            records.append((record, report))
        return records
    finally:
        if owned:
            client.close()
