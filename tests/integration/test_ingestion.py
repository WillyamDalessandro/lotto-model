from datetime import date

import pytest
from sqlalchemy import text

from lotto_model.ingestion.contracts import Observation
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.repository import Repository


def setup_repository(connection, tmp_path):
    repository = Repository(connection)
    run = repository.start_run({"test": True})
    artifact = EvidenceStore(tmp_path).write(
        b"evidence",
        url="https://example.test/results",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    artifact_id = repository.record_artifact(
        artifact, run, "test_source", "independent"
    )
    repository.add_rule(
        "test_regime", date(2026, 1, 1), None, 45, [0, 2, 5], artifact_id
    )
    return repository, artifact_id


def observation(**changes):
    return Observation(
        **(
            {
                "draw_date": "2026-10-07",
                "mains": [1, 2, 3, 4, 5, 6],
                "bonus": 7,
                "source_url": "https://example.test/results",
            }
            | changes
        )
    )


def test_idempotence_and_conflict(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    assert repo.ingest(observation(), artifact) == "accepted"
    assert repo.ingest(observation(), artifact) == "corroborated"
    assert connection.scalar(text("SELECT count(*) FROM draws")) == 1
    other = EvidenceStore(tmp_path).write(
        b"new evidence",
        url="https://example.test/results",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    run = repo.start_run({"test": True})
    other_id = repo.record_artifact(other, run, "test_source", "independent")
    assert repo.ingest(observation(mains=[1, 2, 3, 4, 5, 8]), other_id) == "quarantined"
    assert connection.scalar(text("SELECT status FROM draws")) == "quarantined"


def test_unknown_rule_staged(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    assert (
        repo.ingest(observation(draw_date="1988-04-16", bonus=None), artifact)
        == "staged"
    )
    assert connection.scalar(text("SELECT count(*) FROM draws")) == 0


def test_unknown_bonus_stays_null_and_later_fills(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    assert repo.ingest(observation(bonus=None), artifact) == "accepted"
    assert (
        connection.scalar(text("SELECT count(*) FROM draw_numbers WHERE role='bonus'"))
        == 0
    )
    other = EvidenceStore(tmp_path).write(
        b"bonus evidence",
        url="https://example.test/results",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    run = repo.start_run({"test": True})
    other_id = repo.record_artifact(other, run, "test_source", "independent")
    assert repo.ingest(observation(), other_id) == "corroborated"
    assert (
        connection.scalar(text("SELECT number FROM draw_numbers WHERE role='bonus'"))
        == 7
    )


def test_ineligible_numbers_staged(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    assert repo.ingest(observation(bonus=46), artifact) == "staged"
    assert connection.scalar(text("SELECT count(*) FROM draws")) == 0


def test_rule_overlap_rejected(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    with pytest.raises(ValueError):
        repo.add_rule("overlap", date(2026, 1, 2), None, 47, [2, 5], artifact)


def test_same_evidence_cannot_change_payload(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.ingest(observation(), artifact)
    with pytest.raises(ValueError, match="parser version"):
        repo.ingest(observation(mains=[1, 2, 3, 4, 5, 8]), artifact)


def test_blocked_artifact_cannot_be_ingested(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.sql("UPDATE raw_artifacts SET status='blocked' WHERE id=:a", a=artifact)
    with pytest.raises(ValueError, match="valid evidence"):
        repo.ingest(observation(), artifact)


def test_operator_resolution_preserves_conflicting_observations(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.ingest(observation(), artifact)
    body = EvidenceStore(tmp_path).write(
        b"operator evidence",
        url="https://example.test/operator",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    run = repo.start_run({"test": True})
    other_id = repo.record_artifact(body, run, "operator_test", "operator")
    new = observation(mains=[1, 2, 3, 4, 5, 8])
    assert repo.ingest(new, other_id) == "quarantined"
    obs_id = repo.sql(
        "SELECT id FROM source_observations WHERE artifact_id=:a", a=other_id
    ).scalar_one()
    repo.resolve_numbers(obs_id)
    assert repo.sql("SELECT status FROM draws").scalar_one() == "accepted"
    assert repo.sql("SELECT count(*) FROM source_observations").scalar_one() == 2
    assert (
        repo.sql(
            "SELECT count(*) FROM quality_issues WHERE resolved_at IS NOT NULL"
        ).scalar_one()
        == 1
    )
    assert repo.sql("SELECT number FROM draw_numbers WHERE number=8").scalar_one() == 8
    assert repo.ingest(observation(), artifact) == "superseded"
    assert repo.sql("SELECT status FROM draws").scalar_one() == "accepted"
    assert repo.ingest(new, other_id) == "corroborated"


def test_independent_resolution_is_rejected(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.ingest(observation(), artifact)
    obs_id = repo.sql("SELECT id FROM source_observations").scalar_one()
    with pytest.raises(ValueError, match="operator"):
        repo.resolve_numbers(obs_id)
