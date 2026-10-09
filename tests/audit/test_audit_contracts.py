import os
from datetime import date

import pytest
from pydantic import ValidationError

from lotto_model.audit.contracts import AuditRequest, RuleBindings, canonical_json
from lotto_model.audit.reader import read_evidence

HASH = "a" * 64


def test_request_and_bindings_validation():
    assert AuditRequest(start=date(2026, 1, 1), end=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        AuditRequest(start=date(2026, 1, 2), end=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        AuditRequest(game="lotto_plus", start=date(2026, 1, 1), end=date(2026, 1, 1))
    rule = dict(rule_code="6/47", artifact_sha256=HASH, source_url="https://x.test")
    assert RuleBindings(version=1, rules=[rule], calendar_events=[])
    for bad in (
        dict(version=2, rules=[rule]),
        dict(version=1, rules=[rule, rule]),
        dict(version=1, rules=[rule | {"artifact_sha256": "XYZ"}]),
        dict(version=1, rules=[rule], calendar_events=["a", "a"]),
    ):
        with pytest.raises(ValidationError):
            RuleBindings(**bad)


def test_canonical_json_rules():
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    value = {
        "b": Decimal("1.20"),
        "a": datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
    }
    assert canonical_json(value) == b'{"a":"2026-01-01T00:00:00Z","b":"1.20"}\n'
    with pytest.raises(ValueError):
        canonical_json({"a": datetime(2026, 1, 1)})


def test_evidence_resolution(tmp_path):
    import hashlib

    root = tmp_path / "root"
    root.mkdir()
    body = b"evidence"
    digest = hashlib.sha256(body).hexdigest()
    (root / "e.body").write_bytes(body)
    assert read_evidence("e.body", digest, root) == body
    assert read_evidence(str(root / "e.body"), digest, root) == body
    (tmp_path / "outside.body").write_bytes(body)
    for path, expected in (
        (str(tmp_path / "outside.body"), digest),
        ("../outside.body", digest),
        ("missing.body", digest),
        ("e.body", "0" * 64),
    ):
        with pytest.raises(ValueError):
            read_evidence(path, expected, root)
    try:
        os.symlink(tmp_path / "outside.body", root / "link.body")
    except (OSError, NotImplementedError):
        return
    with pytest.raises(ValueError):
        read_evidence("link.body", digest, root)
