import json
from contextlib import contextmanager

import pytest
from sqlalchemy import text

from lotto_model.ingestion import batch as batch_module
from lotto_model.ingestion.batch import run_batch
from lotto_model.ingestion.report import acquisition_status


class Scope:
    """Engine stand-in whose scopes are savepoints of one rolled-back connection."""

    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn

    @contextmanager
    def connect(self):
        yield self.conn


def count(conn, table):
    return conn.scalar(text(f"SELECT count(*) FROM {table}"))


def test_batch_rollback_and_replay(connection, tmp_path, write_batch, monkeypatch):
    engine = Scope(connection)
    store = tmp_path / "store"
    path = write_batch(tmp_path / "batch", enrichment=True)
    before = {t: count(connection, t) for t in ("rule_regimes", "draws")}

    def fail(*args, **kwargs):
        raise ValueError("injected enrichment failure")

    with monkeypatch.context() as patch:
        patch.setattr(batch_module, "ingest_complementary", fail)
        with pytest.raises(ValueError, match="injected"):
            run_batch(engine, path, None, store)
    assert {t: count(connection, t) for t in before} == before

    receipt = tmp_path / "receipts" / "first.json"
    first = run_batch(engine, path, receipt, store)
    assert first["counts"] == {"accepted": 2, "enrichment": 1, "rules": 1}
    saved = json.loads(receipt.read_text())
    assert saved["digest"] == first["digest"]
    assert saved["coverage_after"]["dated_main_lotto"]["accepted"] == 2
    assert saved["coverage_after"]["complete"] is False
    second = run_batch(engine, path, None, store)
    assert second["digest"] == first["digest"]
    assert second["counts"] == {"corroborated": 2, "enrichment": 1, "rules": 1}
    assert count(connection, "draws") == 2
    assert count(connection, "rule_regimes") == 1
    # Unknown bonus and enrichment remain null rather than invented.
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM draw_numbers n JOIN draws d ON d.id=n.draw_id "
                "WHERE d.draw_date='2026-10-07' AND n.role='bonus'"
            )
        )
        == 0
    )
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM draw_context c JOIN draws d "
                "ON d.id=c.draw_id WHERE d.draw_date='2026-10-07'"
            )
        )
        == 0
    )


def test_correction_is_quarantined_with_provenance(connection, tmp_path, write_batch):
    engine = Scope(connection)
    store = tmp_path / "store"
    run_batch(engine, write_batch(tmp_path / "a"), None, store)
    corrected = write_batch(
        tmp_path / "b",
        draws=b"date,n1,n2,n3,n4,n5,n6\n2026-10-07,1,2,3,4,5,8\n",
    )
    result = run_batch(engine, corrected, None, store)
    assert result["counts"]["quarantined"] == 1
    status = connection.scalar(
        text("SELECT status FROM draws WHERE draw_date='2026-10-07'")
    )
    assert status == "quarantined"
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM source_observations "
                "WHERE payload->>'draw_date'='2026-10-07'"
            )
        )
        == 2
    )


def test_unknown_rules_stay_staged(connection, tmp_path, write_batch):
    engine = Scope(connection)
    draws = b"date,n1,n2,n3,n4,n5,n6\n1990-01-03,1,2,3,4,5,6\n"
    result = run_batch(
        engine, write_batch(tmp_path, draws=draws), None, tmp_path / "store"
    )
    assert result["counts"] == {"rules": 1, "staged": 1}
    assert (
        connection.scalar(
            text("SELECT count(*) FROM draws WHERE draw_date<'2000-01-01'")
        )
        == 0
    )


def test_status_requires_mandatory_inputs(connection):
    connection.execute(
        text(
            "INSERT INTO sources(code,base_url,authority) "
            "VALUES('t','https://example.test','manual')"
        )
    )
    status = acquisition_status(connection)
    assert status["complete"] is False
    assert "dated_draws" in status["outstanding"]
    assert status["annual_metrics_scope"].startswith("All games")
