import json
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lotto_model.research import experiment as experiment_module
from lotto_model.research.contracts import PredictionRecord
from lotto_model.research.experiment import (
    freeze_selection,
    run_development_outputs,
    run_holdout,
)
from lotto_model.research.ledger import (
    acquire_run_lock,
    claim_experiment,
    issue_predictions,
    release_run_lock,
)
from lotto_model.research.models import CANDIDATES
from lotto_model.research.protocol import (
    build_protocol,
    freeze_protocol,
    load_population,
)

LEDGER = "experiment_evaluations,experiment_predictions,experiments"
LINES_PER_TARGET = 1 + 5 + 10


def truncate(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {LEDGER} RESTART IDENTITY CASCADE"))


@pytest.fixture
def frozen_run(db_engine, synthetic_snapshot, tmp_path):
    snapshot = synthetic_snapshot(282)
    draws = load_population(snapshot.path, "6/47")
    protocol_dir = freeze_protocol(
        build_protocol(draws, snapshot.content_sha256), tmp_path / "experiments"
    )
    development = run_development_outputs(
        protocol_dir, snapshot.path, candidates=(CANDIDATES[0],)
    )
    frozen = freeze_selection(development)
    truncate(db_engine)
    yield db_engine, frozen, snapshot.path
    truncate(db_engine)


def count(engine, sql):
    with engine.connect() as conn:
        return conn.scalar(text(sql))


def test_resume_reuses_predictions(frozen_run, monkeypatch):
    engine, frozen, snapshot = frozen_run
    original = experiment_module.record_evaluations
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("interrupted")
        return original(*args, **kwargs)

    monkeypatch.setattr(experiment_module, "record_evaluations", flaky)
    with pytest.raises(RuntimeError):
        run_holdout(engine, frozen, snapshot)
    assert count(engine, "SELECT status FROM experiments") == "failed"
    issued_before = count(engine, "SELECT count(*) FROM experiment_predictions")
    assert issued_before == 2 * LINES_PER_TARGET
    with engine.connect() as conn:
        first = conn.execute(
            text("SELECT id,mains,issued_at FROM experiment_predictions ORDER BY id")
        ).all()
    monkeypatch.setattr(experiment_module, "record_evaluations", original)
    out = run_holdout(engine, frozen, snapshot)
    assert count(engine, "SELECT status FROM experiments") == "evaluated"
    assert count(engine, "SELECT attempts FROM experiments") == 2
    assert (
        count(engine, "SELECT count(*) FROM experiment_predictions")
        == 57 * LINES_PER_TARGET
    )
    assert (
        count(engine, "SELECT count(*) FROM experiment_evaluations")
        == 57 * LINES_PER_TARGET
    )
    with engine.connect() as conn:
        again = conn.execute(
            text(
                "SELECT id,mains,issued_at FROM experiment_predictions "
                "ORDER BY id LIMIT :n"
            ),
            dict(n=len(first)),
        ).all()
    assert again == first
    manifest = json.loads((out / "manifest.json").read_text())
    assert {"prediction_log.csv", "metrics.json", "model.json"} <= set(manifest)

    def refuse(*args, **kwargs):
        raise AssertionError("completed experiments must not refit")

    monkeypatch.setattr(experiment_module, "predict_target", refuse)
    assert run_holdout(engine, frozen, snapshot) == out


def test_ledger_immutability_and_claims(frozen_run):
    engine, frozen, snapshot = frozen_run
    run_holdout(engine, frozen, snapshot)
    for statement in (
        "UPDATE experiment_predictions SET mains='[1,2,3,4,5,6]'",
        "DELETE FROM experiment_predictions",
        "UPDATE experiment_evaluations SET matched_mains=6",
        "DELETE FROM experiment_evaluations",
    ):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(text(statement))
    with engine.connect() as conn:
        row = conn.execute(text("SELECT identity,frozen FROM experiments")).one()
    with engine.begin() as conn, pytest.raises(ValueError, match="different"):
        claim_experiment(conn, row.identity, row.frozen | {"budgets": [1]})
    record = PredictionRecord(
        protocol_digest="a" * 64,
        snapshot_digest="a" * 64,
        target_date=date(2030, 1, 2),
        policy="x",
        budget=5,
        line_index=0,
        mains=(1, 2, 3, 4, 5, 6),
        seed=1,
        max_input_date=date(2030, 1, 1),
    )
    with engine.begin() as conn, pytest.raises(ValueError, match="Incomplete"):
        issue_predictions(conn, 1, [record])
    one = record.model_copy(update={"budget": 1})
    with engine.begin() as conn:
        issue_predictions(conn, 1, [one])
    with pytest.raises(IntegrityError), engine.begin() as conn:
        issue_predictions(conn, 1, [one])


def test_concurrent_run_is_refused(frozen_run):
    engine, frozen, snapshot = frozen_run
    identity = frozen.name
    with engine.connect() as other:
        acquire_run_lock(other, identity)
        try:
            with pytest.raises(ValueError, match="already running"):
                run_holdout(engine, frozen, snapshot)
        finally:
            release_run_lock(other, identity)
            other.commit()
    assert count(engine, "SELECT count(*) FROM experiments") == 0


def test_reconcile_report_and_cli(frozen_run, monkeypatch, test_url):
    from typer.testing import CliRunner

    from lotto_model.cli import app
    from lotto_model.research.reconcile import reconcile_outputs

    engine, frozen, snapshot = frozen_run
    monkeypatch.setenv("LOTTO_DATABASE_URL", test_url)
    runner = CliRunner()
    held = runner.invoke(
        app, ["research", "holdout", str(frozen), "--snapshot", str(snapshot)]
    )
    assert held.exit_code == 0, held.output
    output = frozen / "holdout"
    result = reconcile_outputs(output, snapshot)
    assert result["reconciled"] and result["selected"] == "logistic-c0.01"
    assert result["recomputed"]["logistic-c0.01:10"]["lines"] == 570
    nulls = runner.invoke(
        app,
        ["research", "nulls", str(frozen), "--snapshot", str(snapshot), "--count", "2"],
    )
    assert nulls.exit_code == 0, nulls.output
    reported = runner.invoke(
        app, ["research", "report", str(frozen), "--snapshot", str(snapshot)]
    )
    assert reported.exit_code == 0, reported.output
    assert "Not final" in json.loads(reported.output)["verdict"]  # 2 < 100 refits
    text_report = (output / "report.md").read_text()
    assert "Retrospective simulation" in text_report
    assert (output / "model-card.md").exists()
    predicted = runner.invoke(
        app,
        ["research", "predict", str(frozen), "--snapshot", str(snapshot)]
        + ["--target-date", "2031-01-06"],
    )
    assert predicted.exit_code == 0, predicted.output
    assert len(json.loads(predicted.output)["mains"]) == 6

    log = output / "evaluation_results.csv"
    original = log.read_bytes()
    lines = original.decode().split("\n")
    fields = lines[1].split(",")
    fields[5] = str((int(fields[5]) + 1) % 7)
    lines[1] = ",".join(fields)
    log.write_bytes("\n".join(lines).encode())
    with pytest.raises(ValueError, match="hash"):
        reconcile_outputs(output, snapshot)
    import hashlib

    manifest = json.loads((output / "manifest.json").read_text())
    manifest["evaluation_results.csv"] = hashlib.sha256(log.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="differs"):
        reconcile_outputs(output, snapshot)
