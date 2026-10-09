import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_audit import BINDINGS, REQUEST, RESULT_URL, WED, seed  # noqa: I001

from lotto_model.audit import registry
from lotto_model.audit.bundle import verify_bundle
from lotto_model.audit.registry import audit_connection, create_snapshot
from lotto_model.ingestion.contracts import Observation
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.repository import Repository

DATA_TABLES = (
    "dataset_snapshots,draw_numbers,prize_tiers,draw_context,quality_issues,"
    "calendar_dates,draws,calendar_events,rule_attributes,winning_ticket_reports,"
    "official_period_metrics,rule_regimes,games,fetch_checkpoints,"
    "retrieval_events,source_observations,raw_artifacts,ingestion_runs,sources"
)


def truncate(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {DATA_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def committed(db_engine, tmp_path):
    """Committed rows in the isolated test database, removed afterwards."""
    with db_engine.connect() as conn:
        if conn.scalar(text("SELECT count(*) FROM draws")):
            pytest.fail("Isolated test database unexpectedly contains draws")
    truncate(db_engine)
    with db_engine.begin() as conn:
        seed(conn, tmp_path / "evidence" / "raw")
    yield db_engine
    truncate(db_engine)


def snapshot(engine, root, output):
    return create_snapshot(engine, REQUEST, root, BINDINGS, output, "test-revision")


def count_snapshots(engine):
    with engine.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM dataset_snapshots"))


def test_registry_constraints_and_replay(committed, tmp_path):
    first = snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    assert first.included_draws == 2
    assert verify_bundle(first.path).content_sha256 == first.content_sha256
    with committed.connect() as conn:
        created = conn.execute(
            text("SELECT id,created_at FROM dataset_snapshots")
        ).one()
    again = snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    assert again == first and count_snapshots(committed) == 1
    with committed.connect() as conn:
        assert (
            conn.execute(text("SELECT id,created_at FROM dataset_snapshots")).one()
            == created
        )
    for statement in (
        "UPDATE dataset_snapshots SET included_draws=5",
        "DELETE FROM dataset_snapshots",
        "INSERT INTO dataset_snapshots(content_sha256,schema_version,game,starts_on,"
        "ends_on,included_draws,manifest_path) VALUES('XYZ',1,'lotto',"
        "'2026-01-01','2026-01-02',1,'p')",
        "INSERT INTO dataset_snapshots(content_sha256,schema_version,game,starts_on,"
        "ends_on,included_draws,manifest_path) VALUES(repeat('b',64),1,'lotto',"
        "'2026-01-02','2026-01-01',1,'p')",
        "INSERT INTO dataset_snapshots(content_sha256,schema_version,game,starts_on,"
        "ends_on,included_draws,manifest_path) VALUES(repeat('b',64),1,'lotto',"
        "'2026-01-01','2026-01-02',0,'p')",
    ):
        with pytest.raises(DBAPIError), committed.begin() as conn:
            conn.execute(text(statement))


def test_registry_failure_leaves_retryable_bundle(committed, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("registry unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(registry, "register_snapshot", fail)
        with pytest.raises(RuntimeError):
            snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    assert count_snapshots(committed) == 0
    (left,) = (tmp_path / "out").iterdir()
    assert verify_bundle(left).included_draws == 2
    result = snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    assert result.path == left and count_snapshots(committed) == 1


def test_unexpected_dates_block_snapshot(committed, tmp_path):
    store = EvidenceStore(tmp_path / "evidence" / "raw")
    with committed.begin() as conn:
        repo = Repository(conn)
        artifact = repo.record_artifact(
            store.write(
                b"tuesday",
                url=RESULT_URL,
                http_status=200,
                content_type="text/html",
                status="valid",
            ),
            repo.start_run({}),
            "results",
            "independent",
            evidence_root=store.root,
        )
        repo.ingest(
            Observation(
                draw_date="2026-10-06",
                mains=(20, 21, 22, 23, 24, 25),
                source_url=RESULT_URL,
            ),
            artifact,
        )
    with pytest.raises(ValueError, match="unexpected_dates"):
        snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    assert count_snapshots(committed) == 0
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_reconstruction_identity_and_correction(committed, tmp_path):
    original = snapshot(committed, tmp_path / "evidence", tmp_path / "out")
    truncate(committed)
    with committed.begin() as conn:
        seed(conn, tmp_path / "moved" / "store", shift=7)
    rebuilt = snapshot(committed, tmp_path / "moved", tmp_path / "out2")
    assert rebuilt.content_sha256 == original.content_sha256
    assert (original.path / "draws.csv").read_bytes() == (
        rebuilt.path / "draws.csv"
    ).read_bytes()
    truncate(committed)
    with committed.begin() as conn:
        seed(conn, tmp_path / "corrected", mains=(1, 2, 3, 4, 5, 7))
    corrected = snapshot(committed, tmp_path / "corrected", tmp_path / "out")
    assert corrected.content_sha256 != original.content_sha256
    assert verify_bundle(original.path).content_sha256 == original.content_sha256


def test_repeatable_read_view(committed):
    with audit_connection(committed) as reader, reader.begin():
        before = reader.scalar(text("SELECT count(*) FROM quality_issues"))
        with committed.begin() as writer:
            writer.execute(
                text(
                    "INSERT INTO quality_issues(observation_id,draw_id,kind,detail) "
                    "SELECT accepted_observation_id,id,'number_conflict','{}' "
                    "FROM draws WHERE draw_date=:d AND accepted_observation_id "
                    "IS NOT NULL"
                ),
                dict(d=WED),
            )
        assert reader.scalar(text("SELECT count(*) FROM quality_issues")) == before
    with committed.connect() as fresh:
        assert fresh.scalar(text("SELECT count(*) FROM quality_issues")) == before + 1


def test_cli_report_snapshot_verify(committed, tmp_path, monkeypatch, test_url):
    import json

    from typer.testing import CliRunner

    from lotto_model.cli import app

    monkeypatch.setenv("LOTTO_DATABASE_URL", test_url)
    bindings = tmp_path / "bindings.json"
    bindings.write_text(BINDINGS.model_dump_json())
    runner = CliRunner()
    common = ["--start", "2026-10-05", "--end", "2026-10-07"]
    common += ["--evidence-root", str(tmp_path / "evidence")]
    report = runner.invoke(app, ["audit", "report", *common])
    assert report.exit_code == 0, report.output
    assert json.loads(report.output)["snapshot_ready"] is False  # rules unbound
    report = runner.invoke(
        app, ["audit", "report", *common, "--bindings", str(bindings)]
    )
    assert json.loads(report.output)["counts"]["included"] == 2
    assert count_snapshots(committed) == 0
    created = runner.invoke(
        app,
        ["audit", "snapshot", *common, "--bindings", str(bindings)]
        + ["--output-root", str(tmp_path / "out")],
    )
    assert created.exit_code == 0, created.output
    value = json.loads(created.output)
    verified = runner.invoke(app, ["audit", "verify", value["path"]])
    assert json.loads(verified.output)["content_sha256"] == value["content_sha256"]
    truncate(committed)
    empty = runner.invoke(
        app,
        ["audit", "snapshot", *common, "--bindings", str(bindings)]
        + ["--output-root", str(tmp_path / "out")],
    )
    assert empty.exit_code == 1
    report = runner.invoke(app, ["audit", "report", *common])
    assert report.exit_code == 0
    assert json.loads(report.output)["counts"]["canonical_candidates"] == 0
