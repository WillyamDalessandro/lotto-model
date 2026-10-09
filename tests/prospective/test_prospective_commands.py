from typer.testing import CliRunner

from lotto_model.cli import app

runner = CliRunner()


def test_failures_are_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("LOTTO_DATABASE_URL", "private-credential-marker")
    bad = tmp_path / "protocol.json"
    bad.write_text("{}")
    for args in (
        ["prospective", "protocol", str(bad)],
        ["prospective", "issue", str(tmp_path), "--target-date", "2031-01-06"],
        ["prospective", "evaluate", str(tmp_path)],
        ["prospective", "report", str(tmp_path)],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 1
        assert "private-credential-marker" not in result.output
