from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from lotto_model.ingestion import backfill as module

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ingestion" / "lottonet-2015.html"


class Scope:
    """Engine stand-in whose scopes are savepoints of one rolled-back connection."""

    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn


def bodies(**changes):
    values = {
        module.WIKIPEDIA_URL: " ... ".join(module.WIKIPEDIA_PHRASES).encode(),
        module.ANNOUNCEMENT_URL: " ".join(module.ANNOUNCEMENT_PHRASES).encode(),
        module.LOTTONET.format(year=2015): FIXTURE.read_bytes(),
    }
    return values | changes


def client_for(values, calls):
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=values[str(request.url)])

    return httpx.Client(transport=httpx.MockTransport(respond))


def accepted(conn):
    return conn.execute(
        text(
            """SELECT d.draw_date, r.code FROM draws d
            JOIN rule_regimes r ON r.id=d.rule_id ORDER BY d.draw_date"""
        )
    ).all()


def test_backfill_registers_rules_and_assigns_regimes(connection, tmp_path):
    calls = []
    result = module.backfill(
        Scope(connection),
        tmp_path,
        2015,
        2015,
        client=client_for(bodies(), calls),
        sleep=lambda _: None,
    )
    assert result["years"] == 1 and result["rules"] == len(module.RULES)
    assert [(str(d), c) for d, c in accepted(connection)] == [
        ("2015-09-02", "6/45"),
        ("2015-09-05", "6/47"),
    ]
    # A rerun reuses cached evidence for past years and is idempotent.
    module.backfill(
        Scope(connection),
        tmp_path,
        2015,
        2015,
        client=client_for(bodies(), calls),
        sleep=lambda _: None,
        refresh_from=2100,
    )
    assert len(calls) == 3
    assert len(accepted(connection)) == 2


def test_backfill_refuses_changed_rule_evidence(connection, tmp_path):
    changed = bodies(**{module.WIKIPEDIA_URL: b"rewritten article"})
    with pytest.raises(ValueError, match="Rule evidence"):
        module.backfill(
            Scope(connection),
            tmp_path,
            2015,
            2015,
            client=client_for(changed, []),
            sleep=lambda _: None,
        )
    assert connection.scalar(text("SELECT count(*) FROM rule_regimes")) == 0
