import json
from datetime import date

from typer.testing import CliRunner

from lotto_model.audit.bundle import build_content, build_manifest
from lotto_model.audit.contracts import AuditRequest
from lotto_model.audit.eligibility import audit_inputs
from lotto_model.audit.registry import publish_bundle
from lotto_model.cli import app

runner = CliRunner()
REQUEST = AuditRequest(start=date(2026, 10, 5), end=date(2026, 10, 7))


def test_invalid_dates_and_credentials_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("LOTTO_DATABASE_URL", "private-credential-marker")
    for args in (
        ["audit", "report", "--start", "2026-10-07", "--end", "2026-10-05"],
        ["audit", "report", "--start", "bad", "--end", "2026-10-05"],
        ["audit", "report", "--start", "2026-10-05", "--end", "2026-10-07"],
    ):
        result = runner.invoke(app, [*args, "--evidence-root", str(tmp_path)])
        assert result.exit_code == 1
        assert "private-credential-marker" not in result.output


def test_verify_without_database(monkeypatch, tmp_path, audit_factory):
    monkeypatch.delenv("LOTTO_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    inputs = audit_factory.inputs([audit_factory.draw(date(2026, 10, 7))])
    files = build_content(audit_inputs(inputs, REQUEST), REQUEST)
    result = publish_bundle(
        files, build_manifest(files, REQUEST, 1, "rev"), tmp_path / "out", 1
    )
    ok = runner.invoke(app, ["audit", "verify", str(result.path)])
    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.output)["content_sha256"] == result.content_sha256
    body = next((result.path / "evidence").iterdir())
    body.write_bytes(b"secret body text")
    bad = runner.invoke(app, ["audit", "verify", str(result.path)])
    assert bad.exit_code == 1
    assert "secret body text" not in bad.output
