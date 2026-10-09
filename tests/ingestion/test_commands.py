from typer.testing import CliRunner

from lotto_model.cli import app

runner = CliRunner()


def test_collect_rejects_invalid_year_range_without_network():
    result = runner.invoke(app, ["data", "collect", "--start-year", "1980"])
    assert result.exit_code == 2


def test_prepare_invalid_csv_has_sanitized_error(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("wrong,data\n1,2\n")
    result = runner.invoke(
        app, ["data", "prepare", str(path), "--root", str(tmp_path / "raw")]
    )
    assert result.exit_code == 1
    assert "failed" in result.output.lower()
    assert not (tmp_path / "raw" / "manifest.json").exists()


def test_bad_settings_report_is_sanitized(monkeypatch):
    monkeypatch.setenv("LOTTO_DATABASE_URL", "private-credential-marker")
    result = runner.invoke(app, ["data", "report"])
    assert result.exit_code == 1
    assert "failed" in result.output.lower()
    assert "private-credential-marker" not in result.output


def test_batch_and_status_failures_are_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("LOTTO_DATABASE_URL", "private-credential-marker")
    for args in (
        ["data", "batch", str(tmp_path / "missing.json")],
        ["data", "acquisition-status"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 1
        assert "failed" in result.output.lower()
        assert "private-credential-marker" not in result.output
