from pathlib import Path

import pytest

from lotto_model.ingestion import evidence


def test_replace_retries_transient_lock(tmp_path, monkeypatch):
    source, target = tmp_path / "a.tmp", tmp_path / "a.json"
    source.write_text("x")
    calls = []
    original = Path.replace

    def flaky(self, other):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("locked")
        return original(self, other)

    monkeypatch.setattr(Path, "replace", flaky)
    monkeypatch.setattr(evidence.time, "sleep", lambda _: None)
    evidence._replace(source, target)
    assert target.read_text() == "x" and len(calls) == 3


def test_replace_gives_up(tmp_path, monkeypatch):
    def locked(self, other):
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(evidence.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        evidence._replace(tmp_path / "a", tmp_path / "b", attempts=2)
