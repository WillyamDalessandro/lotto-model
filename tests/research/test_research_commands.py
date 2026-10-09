import json

from typer.testing import CliRunner

from lotto_model.cli import app

runner = CliRunner()


def test_protocol_and_baselines_cli(synthetic_snapshot, tmp_path):
    snapshot = synthetic_snapshot(282)
    created = runner.invoke(
        app,
        ["research", "protocol", str(snapshot.path), "--rule-code", "6/47"]
        + ["--output-root", str(tmp_path / "experiments")],
    )
    assert created.exit_code == 0, created.output
    value = json.loads(created.output)
    assert value["holdout"] == [225, 282]
    args = ["research", "baselines", value["path"], "--snapshot", str(snapshot.path)]
    ran = runner.invoke(app, [*args, "--simulations", "3"])
    assert ran.exit_code == 0, ran.output
    summary = json.loads(ran.output)["summary"]
    assert set(summary) == {
        f"{p}:{b}" for p in ("uniform", "frequency") for b in (1, 5, 10)
    }
    assert runner.invoke(app, [*args, "--simulations", "3"]).exit_code == 0
    (snapshot.path / "draws.csv").write_bytes(b"tampered")
    refused = runner.invoke(app, [*args, "--simulations", "3"])
    assert refused.exit_code == 1


def test_insufficient_data_is_reported(synthetic_snapshot, tmp_path):
    snapshot = synthetic_snapshot(100)
    result = runner.invoke(
        app,
        ["research", "protocol", str(snapshot.path), "--rule-code", "6/47"]
        + ["--output-root", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "insufficient_data" in result.output
