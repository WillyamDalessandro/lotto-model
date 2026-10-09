import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from lotto_model.cli import app


def test_upgrade_is_idempotent(db_engine, migration_config):
    command.upgrade(migration_config, "head")
    with db_engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
        tables = (
            conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public'"
                )
            )
            .scalars()
            .all()
        )
        assert set(tables) >= {
            "sources",
            "ingestion_runs",
            "raw_artifacts",
            "source_observations",
            "games",
            "rule_regimes",
            "draws",
            "draw_numbers",
            "prize_tiers",
        }


def test_cli_health_and_migrate(test_url, monkeypatch):
    monkeypatch.setenv("LOTTO_DATABASE_URL", test_url)
    runner = CliRunner()
    result = runner.invoke(app, ["db", "migrate"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["db", "health"])
    assert result.exit_code == 0, result.output
    assert "Database healthy" in result.output


def seed_draw(conn):
    game = conn.scalar(
        text("INSERT INTO games(code) VALUES ('synthetic') RETURNING id")
    )
    rule = conn.scalar(
        text(
            "INSERT INTO rule_regimes(game_id, code, starts_on, pool) "
            "VALUES (:game, 'test', '2000-01-01', 45) RETURNING id"
        ),
        {"game": game},
    )
    draw = conn.scalar(
        text(
            "INSERT INTO draws(game_id, rule_id, draw_date) "
            "VALUES (:game, :rule, '2000-01-01') RETURNING id"
        ),
        {"game": game, "rule": rule},
    )
    return game, rule, draw


@pytest.mark.parametrize("number,role", [(0, "main"), (1, "invalid")])
def test_number_constraints(connection, number, role):
    _, _, draw = seed_draw(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("INSERT INTO draw_numbers(draw_id, number, role) VALUES (:d, :n, :r)"),
            {"d": draw, "n": number, "r": role},
        )


def test_duplicate_draw_and_number(connection):
    game, rule, draw = seed_draw(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text(
                "INSERT INTO draws(game_id, rule_id, draw_date) "
                "VALUES (:g, :r, '2000-01-01')"
            ),
            {"g": game, "r": rule},
        )
    connection.execute(
        text("INSERT INTO draw_numbers(draw_id, number, role) VALUES (:d, 1, 'main')"),
        {"d": draw},
    )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text(
                "INSERT INTO draw_numbers(draw_id, number, role) "
                "VALUES (:d, 1, 'bonus')"
            ),
            {"d": draw},
        )


@pytest.mark.parametrize("winners,prize", [(-1, 2), (1, -2)])
def test_negative_prizes_rejected(connection, winners, prize):
    _, _, draw = seed_draw(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text(
                "INSERT INTO prize_tiers(draw_id,tier,winners,prize_eur) "
                "VALUES (:d,'match3',:w,:p)"
            ),
            {"d": draw, "w": winners, "p": prize},
        )


def test_null_prizes_and_duplicate_tier(connection):
    _, _, draw = seed_draw(connection)
    connection.execute(
        text("INSERT INTO prize_tiers(draw_id,tier) VALUES (:d,'match3')"), {"d": draw}
    )
    assert (
        connection.scalar(
            text("SELECT prize_eur FROM prize_tiers WHERE draw_id=:d"), {"d": draw}
        )
        is None
    )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("INSERT INTO prize_tiers(draw_id,tier) VALUES (:d,'match3')"),
            {"d": draw},
        )


def test_rollback_removes_insert(db_engine):
    with db_engine.connect() as conn:
        tx = conn.begin()
        seed_draw(conn)
        tx.rollback()
        assert (
            conn.scalar(text("SELECT count(*) FROM games WHERE code='synthetic'")) == 0
        )


def test_game_rule_mismatch_rejected(connection):
    _, rule, _ = seed_draw(connection)
    other = connection.scalar(
        text("INSERT INTO games(code) VALUES ('other_synthetic') RETURNING id")
    )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text(
                "INSERT INTO draws(game_id,rule_id,draw_date) "
                "VALUES (:g,:r,'2000-01-02')"
            ),
            {"g": other, "r": rule},
        )


def test_accepted_draw_requires_evidence(connection):
    _, _, draw = seed_draw(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("UPDATE draws SET status='accepted' WHERE id=:d"), {"d": draw}
        )
