import httpx
import pytest

from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.fetch import AccessPolicy, Fetcher


def test_policy_denies_archive():
    with pytest.raises(ValueError):
        AccessPolicy().check(
            "https://irish.national-lottery.com/irish-lotto/results-archive-2026"
        )


def test_retry_cache_and_block(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(500 if len(calls) == 1 else 200, content=b"page")

    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(respond))
    policy = AccessPolicy({"example.test": ("/results",)})
    fetcher = Fetcher(
        EvidenceStore(tmp_path), client=client, policy=policy, sleep=sleeps.append
    )
    a = fetcher.fetch("https://example.test/results")
    assert a.status == "valid" and len(calls) == 2
    assert fetcher.fetch(a.url) == a and len(calls) == 2
    assert sleeps


def test_redirect_denied(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                302, headers={"location": "https://example.test/play"}
            )
        )
    )
    f = Fetcher(
        EvidenceStore(tmp_path),
        client=client,
        policy=AccessPolicy({"example.test": ("/results",)}),
        sleep=lambda _: None,
    )
    with pytest.raises(ValueError):
        f.fetch("https://example.test/results")


def test_long_retry_after_defers_instead_of_sleeping(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"retry-after": "3600"})
        )
    )
    sleeps = []
    fetcher = Fetcher(
        EvidenceStore(tmp_path),
        client=client,
        policy=AccessPolicy({"example.test": ["/results"]}),
        sleep=sleeps.append,
    )
    with pytest.raises(ValueError, match="deferred"):
        fetcher.fetch("https://example.test/results")
    assert all(s <= 60 for s in sleeps)


def test_failed_content_is_not_cached(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"not a PDF")
        )
    )
    store = EvidenceStore(tmp_path)
    fetcher = Fetcher(
        store, client=client, policy=AccessPolicy({"example.test": ["/report"]})
    )
    artifact = fetcher.fetch(
        "https://example.test/report", validator=lambda b: b.startswith(b"%PDF")
    )
    assert artifact.status == "invalid"
    assert store.cached(artifact.url) is None
