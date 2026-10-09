from typer.testing import CliRunner

from lotto_model.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "db" in result.output


def test_failed_connection_is_sanitised(monkeypatch):
    monkeypatch.setenv(
        "LOTTO_DATABASE_URL",
        "postgresql+psycopg://user:private-secret@127.0.0.1:1/lotto",
    )
    result = runner.invoke(app, ["db", "health"])
    assert result.exit_code == 1
    assert "Database unavailable" in result.output
    assert "private-secret" not in result.output


def test_failed_migration_is_sanitised(monkeypatch):
    monkeypatch.setenv(
        "LOTTO_DATABASE_URL",
        "postgresql+psycopg://user:private-secret@127.0.0.1:1/lotto",
    )
    result = runner.invoke(app, ["db", "migrate"])
    assert result.exit_code == 1
    assert "Migration failed" in result.output
    assert "private-secret" not in result.output
