import json

import pytest

from lotto_model.ingestion.evidence import EvidenceStore


def test_roundtrip(tmp_path):
    store = EvidenceStore(tmp_path)
    artifact = store.write(
        b"hello",
        url="https://example.test/result",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    assert store.read(artifact) == b"hello"
    assert store.load_manifest(store.manifest) == [artifact]
    (tmp_path / artifact.body_path).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        store.load_manifest(store.manifest)


def test_escape(tmp_path):
    store = EvidenceStore(tmp_path)
    store.write(
        b"x",
        url="https://example.test/result",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    payload = json.loads(store.manifest.read_text())
    payload["artifacts"][0]["body_path"] = "../outside"
    store.manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        store.load_manifest(store.manifest)
