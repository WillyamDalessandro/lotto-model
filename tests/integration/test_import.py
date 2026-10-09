import pytest
from sqlalchemy import text

from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.report import coverage
from lotto_model.ingestion.workflows import import_manifest


def test_csv_rebuild_and_evidence_copy(db_engine, tmp_path):
    source = EvidenceStore(tmp_path / "source")
    source.write(
        b"date,n1,n2,n3,n4,n5,n6,bonus\n1990-01-03,1,2,3,4,5,6,7\n",
        url="https://example.test/export.csv",
        http_status=200,
        content_type="text/csv",
        status="valid",
    )
    target = EvidenceStore(tmp_path / "target")
    # Rollback-only Connection acts as engine: nested .begin scopes use savepoints.
    with db_engine.connect() as conn:
        txn = conn.begin()

        class Scope:
            def begin(self):
                from contextlib import contextmanager

                @contextmanager
                def scope():
                    with conn.begin_nested():
                        yield conn

                return scope()

        try:
            assert import_manifest(Scope(), source.manifest, target, "csv") == {
                "staged": 1
            }
            assert import_manifest(Scope(), source.manifest, target, "csv") == {
                "staged": 1
            }
            assert conn.scalar(text("SELECT count(*) FROM source_observations")) == 1
            assert target.load_manifest(target.manifest)
        finally:
            txn.rollback()


def test_invalid_manifest_prevents_database_mutation(db_engine, tmp_path):
    store = EvidenceStore(tmp_path)
    artifact = store.write(
        b"bad",
        url="https://example.test/export.csv",
        http_status=200,
        content_type="text/csv",
        status="valid",
    )
    (tmp_path / artifact.body_path).write_bytes(b"tampered")
    with db_engine.connect() as conn:
        before = conn.scalar(text("SELECT count(*) FROM ingestion_runs"))
    with pytest.raises(ValueError, match="hash"):
        import_manifest(db_engine, store.manifest, store, "csv")
    with db_engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM ingestion_runs")) == before


def test_report_contains_all_datasets(db_engine):
    value = coverage(db_engine)
    assert value["expected_coverage"] is None
    assert "official_period_metrics" in value["datasets"]
    assert "rules_and_prices" in value["datasets"]
    assert "field_missingness" in value
