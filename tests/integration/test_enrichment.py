from test_ingestion import observation, setup_repository

from lotto_model.ingestion.contracts import PrizeObservation
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.report import query_prizes


def next_artifact(repo, tmp_path):
    artifact = EvidenceStore(tmp_path).write(
        b"second source",
        url="https://example.test/results",
        http_status=200,
        content_type="text/html",
        status="valid",
    )
    return repo.record_artifact(
        artifact, repo.start_run({}), "test_source", "independent"
    )


def prize(**kwargs):
    return PrizeObservation(
        **(
            dict(
                tier="Match 6",
                winners=1,
                amount="10",
                currency="EUR",
                original_text="EUR10",
                prize_type="cash",
            )
            | kwargs
        )
    )


def test_disputed_semantics_excluded_from_totals(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.ingest(observation(prizes=[prize()]), artifact)
    repo.ingest(
        observation(prizes=[prize(prize_type="ticket_or_cash")]),
        next_artifact(repo, tmp_path),
    )
    draw = repo.sql("SELECT id FROM draws").scalar_one()
    assert query_prizes(connection, draw) == []


def test_compatible_complete_observation_replaces_partial_tuple(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.ingest(
        observation(jackpot="100", currency="EUR", prizes=[prize(winners=None)]),
        artifact,
    )
    repo.ingest(
        observation(jackpot="100", currency="EUR", outcome="Won", prizes=[prize()]),
        next_artifact(repo, tmp_path),
    )
    assert repo.sql("SELECT outcome FROM draw_context").scalar_one() == "Won"
    assert repo.sql("SELECT winners FROM prize_tiers").scalar_one() == 1


def test_reaccepted_observation_resolves_staging_issue(connection, tmp_path):
    repo, artifact = setup_repository(connection, tmp_path)
    repo.sql("UPDATE rule_regimes SET starts_on='2026-10-08'")
    assert repo.ingest(observation(), artifact) == "staged"
    repo.sql("UPDATE rule_regimes SET starts_on='2026-01-01'")
    assert repo.ingest(observation(), artifact) == "accepted"
    assert (
        repo.sql(
            "SELECT count(*) FROM quality_issues WHERE resolved_at IS NULL"
        ).scalar_one()
        == 0
    )
