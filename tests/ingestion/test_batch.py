import json
import socket

import pytest
from pydantic import ValidationError

from lotto_model.ingestion.batch import validate_batch


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Batch validation must not use the network")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def edit(path, **changes):
    data = json.loads(path.read_text())
    data |= changes
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}))
    return path


def test_valid_batch(tmp_path, write_batch):
    prepared = validate_batch(write_batch(tmp_path, enrichment=True))
    assert len(prepared.rules) == 1
    assert sum(len(rows) for *_, rows in prepared.draws) == 2
    assert len(prepared.enrichment) == 1
    assert len(prepared.digest) == 64


def test_digest_excludes_host_paths(tmp_path, write_batch):
    first = validate_batch(write_batch(tmp_path / "a"))
    second = validate_batch(write_batch(tmp_path / "elsewhere" / "b"))
    assert first.digest == second.digest


def test_digest_changes_with_content(tmp_path, write_batch):
    first = validate_batch(write_batch(tmp_path / "a"))
    changed = write_batch(
        tmp_path / "b", draws=b"date,n1,n2,n3,n4,n5,n6\n2026-10-07,1,2,3,4,5,7\n"
    )
    assert validate_batch(changed).digest != first.digest


@pytest.mark.parametrize(
    "changes",
    [
        {"version": 2},
        {"adapter": "auto"},
        {"adapter": "unsupported"},
        {"permitted_use": "publication"},
        {"permission_evidence_sha256": "0" * 64},
        {"permission_evidence_sha256": "not-a-hash"},
        {"rules_records": None},
        {"permission_evidence_path": "../outside.txt"},
        {"draw_manifest": "../outside/manifest.json"},
        {"unexpected": True},
    ],
)
def test_invalid_batches(tmp_path, write_batch, changes):
    (tmp_path / "outside.txt").write_text("x")
    path = edit(write_batch(tmp_path / "batch"), **changes)
    with pytest.raises((ValueError, ValidationError, OSError)):
        validate_batch(path)


def test_absent_permission_fails(tmp_path, write_batch):
    path = write_batch(tmp_path)
    (tmp_path / "permission.txt").unlink()
    with pytest.raises(OSError):
        validate_batch(path)


def test_tampered_evidence_fails(tmp_path, write_batch):
    path = write_batch(tmp_path)
    body = next((tmp_path / "draws").glob("*.body"))
    body.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        validate_batch(path)


def test_invalid_rule_and_enrichment_fail(tmp_path, write_batch):
    path = write_batch(tmp_path / "a")
    rules = json.loads((tmp_path / "a" / "rules.json").read_text())
    rules[0]["schedule"] = [7]
    (tmp_path / "a" / "rules.json").write_text(json.dumps(rules))
    with pytest.raises(ValueError):
        validate_batch(path)
    with pytest.raises(ValueError):
        validate_batch(write_batch(tmp_path / "b", enrichment="invalid"))


def test_out_of_range_artifact_index(tmp_path, write_batch):
    path = write_batch(tmp_path)
    rules = json.loads((tmp_path / "rules.json").read_text())
    rules[0]["artifact_index"] = 3
    (tmp_path / "rules.json").write_text(json.dumps(rules))
    with pytest.raises(ValueError, match="range"):
        validate_batch(path)
