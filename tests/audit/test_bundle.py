import json
import random
from datetime import date
from decimal import Decimal

import pytest

from lotto_model.audit.bundle import (
    build_content,
    build_manifest,
    content_digest,
    verify_bundle,
    verify_files,
)
from lotto_model.audit.contracts import AuditRequest
from lotto_model.audit.eligibility import audit_inputs
from lotto_model.audit.registry import publish_bundle

MON, WED = date(2026, 10, 5), date(2026, 10, 7)
REQUEST = AuditRequest(start=MON, end=WED)


def content(factory, draws=None, shuffle=False, enrichment=()):
    draws = draws or [
        factory.draw(MON, mains=(9, 3, 1, 40, 22, 17), bonus=None),
        factory.draw(WED),
    ]
    if shuffle:
        draws = random.Random(4).sample(draws, len(draws))
    inputs = factory.inputs(draws, enrichment=enrichment)
    return build_content(audit_inputs(inputs, REQUEST), REQUEST)


def complete(files):
    return {**files, "manifest.json": build_manifest(files, REQUEST, 2, "rev")}


def test_canonical_serialization(audit_factory):
    prize = dict(
        kind="prize",
        draw_date=WED,
        tier="match_3",
        winners=2,
        amount=Decimal("1.20"),
        currency="EUR",
        disputed=False,
        evidence_ok=True,
    )
    draw = audit_factory.draw(WED)
    prize["observation_key"] = draw["observation_key"]
    first = content(audit_factory, enrichment=[prize])
    assert first == content(audit_factory, shuffle=True, enrichment=[prize])
    lines = first["draws.csv"].decode().split("\n")
    assert lines[0] == (
        "game,draw_date,rule_code,main_1,main_2,main_3,main_4,main_5,main_6,"
        "bonus,observation_key"
    )
    assert lines[1].startswith("lotto,2026-10-05,6/47,1,3,9,17,22,40,,")
    assert lines[-1] == ""
    assert '"amount":"1.20"' in first["enrichment.json"].decode()
    assert all(body.endswith(b"\n") for p, body in first.items() if ".json" in p)
    lineage = first["lineage.json"].decode()
    assert '"retrieved_at":"2026-10-09T12:00:00Z"' in lineage
    manifest = json.loads(build_manifest(first, REQUEST, 2, "rev"))
    assert manifest["extracted_at"].endswith("Z")


def test_portable_identity(audit_factory):
    first = content(audit_factory)
    # Database IDs, host paths and run IDs never enter the inputs or content.
    assert content_digest(first) == content_digest(content(audit_factory))
    changed = content(
        audit_factory,
        draws=[
            audit_factory.draw(MON, mains=(9, 3, 1, 40, 22, 18), bonus=None),
            audit_factory.draw(WED),
        ],
    )
    assert content_digest(changed) != content_digest(first)


def test_blocking_audit_cannot_build(audit_factory):
    inputs = audit_factory.inputs([])
    with pytest.raises(ValueError, match="blocking"):
        build_content(audit_inputs(inputs, REQUEST), REQUEST)


def _mutations():
    def body(files):
        files["draws.csv"] = files["draws.csv"].replace(b"6/47", b"6/48", 1)

    def missing(files):
        files.pop("rules.json")

    def extra(files):
        files["notes.txt"] = b"x"

    def unsafe(files):
        manifest = json.loads(files["manifest.json"])
        manifest["files"]["../escape"] = manifest["files"].pop("rules.json")
        files["manifest.json"] = json.dumps(manifest).encode()

    def count(files):
        manifest = json.loads(files["manifest.json"])
        manifest["included_draws"] = 3
        files["manifest.json"] = json.dumps(manifest).encode()

    def ineligible(files, factory):
        bad = content(
            factory,
            draws=[factory.draw(MON, bonus=None), factory.draw(WED)],
        )
        bad["draws.csv"] = bad["draws.csv"].replace(
            b",1,2,3,4,5,6,7,", b",1,2,3,4,5,48,7,"
        )
        files.clear()
        files.update(complete(bad))

    def lineage(files, factory):
        bad = content(factory)
        data = json.loads(bad["lineage.json"])
        data["observations"] = data["observations"][:1]
        bad["lineage.json"] = (json.dumps(data) + "\n").encode()
        files.clear()
        files.update(complete(bad))

    return [body, missing, extra, unsafe, count, ineligible, lineage]


@pytest.mark.parametrize("mutate", _mutations(), ids=lambda m: m.__name__)
def test_bundle_verification(audit_factory, mutate):
    files = complete(content(audit_factory))
    assert verify_files(dict(files)).included_draws == 2
    if mutate.__code__.co_argcount == 2:
        mutate(files, audit_factory)
    else:
        mutate(files)
    with pytest.raises(ValueError):
        verify_files(files)


def test_atomic_publication_and_reuse(audit_factory, tmp_path, monkeypatch):
    files = content(audit_factory)
    manifest = build_manifest(files, REQUEST, 2, "rev")
    from lotto_model.audit import registry

    original = registry._write

    def failing(root, items):
        original(root, dict(list(items.items())[:1]))
        raise OSError("disk full")

    monkeypatch.setattr(registry, "_write", failing)
    with pytest.raises(OSError):
        publish_bundle(files, manifest, tmp_path, 2)
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(registry, "_write", original)
    result = publish_bundle(files, manifest, tmp_path, 2)
    assert result.path.name == result.content_sha256
    assert verify_bundle(result.path).content_sha256 == result.content_sha256
    again = publish_bundle(files, build_manifest(files, REQUEST, 2, "new"), tmp_path, 2)
    assert again.path == result.path
    assert (
        json.loads((result.path / "manifest.json").read_text())["source_revision"]
        == "rev"
    )
    (result.path / "draws.csv").write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        publish_bundle(files, manifest, tmp_path, 2)
