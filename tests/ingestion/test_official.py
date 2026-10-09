import hashlib

import httpx
import pytest

from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.official import METADATA_URL, REPORT_URL, collect_official


def test_official_evidence_and_curated_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "lotto_model.ingestion.official.REVIEWED_SHA256",
        hashlib.sha256(b"%PDF-1.7 test").hexdigest(),
    )
    urls = []

    def respond(request):
        urls.append(str(request.url))
        if str(request.url) == METADATA_URL:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "license_id": "CC-BY-4.0",
                        "resources": [{"url": REPORT_URL}],
                    },
                },
            )
        return httpx.Response(
            200, content=b"%PDF-1.7 test", headers={"content-type": "application/pdf"}
        )

    store = EvidenceStore(tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    records = collect_official(store, client=client, sleep=lambda _: None)
    assert len(records) == 2
    assert records[0][0].payload["game_scope"] == "all_national_lottery_games"
    assert records[0][0].payload["value"] == "16.6"
    assert records[1][0].payload["value"] == "55.6"
    assert all(a.sha256 for _, a in records)
    assert urls == [METADATA_URL, REPORT_URL]
    collect_official(store, client=client, sleep=lambda _: None)
    assert len(urls) == 2


def test_official_wrong_license_stops_before_pdf(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"success": True, "result": {"license_id": "unknown"}}
            )
        )
    )
    with pytest.raises(ValueError, match="license"):
        collect_official(EvidenceStore(tmp_path), client=client, sleep=lambda _: None)


def test_official_html_is_not_pdf(tmp_path):
    def respond(request):
        if str(request.url) == METADATA_URL:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "license_id": "CC-BY-4.0",
                        "resources": [{"url": REPORT_URL}],
                    },
                },
            )
        return httpx.Response(200, content=b"<html>not found</html>")

    client = httpx.Client(transport=httpx.MockTransport(respond))
    with pytest.raises(ValueError, match="PDF"):
        collect_official(EvidenceStore(tmp_path), client=client, sleep=lambda _: None)
