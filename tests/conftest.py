import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from lotto_model.audit.contracts import AuditInputs, observation_key, sha256
from lotto_model.ingestion.evidence import EvidenceStore


def require_test_url(url):
    parsed = make_url(url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.query
        or not (parsed.database and parsed.database.endswith("_test"))
    ):
        raise ValueError("Integration tests require a PostgreSQL database ending _test")
    return url


@pytest.fixture(scope="session")
def test_url():
    load_dotenv()
    url = os.environ.get("LOTTO_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set LOTTO_TEST_DATABASE_URL; integration tests are mandatory")
    return require_test_url(url)


@pytest.fixture(scope="session")
def migration_config(test_url):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = test_url
    return config


@pytest.fixture(scope="session")
def db_engine(migration_config, test_url):
    command.upgrade(migration_config, "head")
    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(db_engine):
    with db_engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()


DRAWS = (
    b"date,n1,n2,n3,n4,n5,n6,bonus,jackpot,currency,jackpotWinners\n"
    b"2026-10-05,3,17,26,29,37,42,38,5000000,EUR,0\n"
    b"2026-10-07,1,2,3,4,5,6,,,,\n"
)


def _write_batch(root, *, draws=DRAWS, rules=True, enrichment=False, **changes):
    """Create a self-contained reviewed batch directory and return its path."""
    root.mkdir(parents=True, exist_ok=True)
    permission = root / "permission.txt"
    permission.write_text("Reviewed permission for local research.\n")
    batch = {
        "version": 1,
        "source_code": "test-export",
        "permission_evidence_path": "permission.txt",
        "permission_evidence_sha256": hashlib.sha256(
            permission.read_bytes()
        ).hexdigest(),
        "permitted_use": "local_research",
        "evidence_root": ".",
        "adapter": "csv",
    }
    if draws is not None:
        store = EvidenceStore(root / "draws")
        store.write(
            draws,
            url="https://example.test/export.csv",
            http_status=200,
            content_type="text/csv",
            status="valid",
        )
        batch["draw_manifest"] = "draws/manifest.json"
    if rules:
        store = EvidenceStore(root / "rules")
        store.write(
            b"rules evidence",
            url="https://example.test/rules.pdf",
            http_status=200,
            content_type="application/pdf",
            status="valid",
        )
        records = [
            {
                "artifact_index": 0,
                "code": "6/45",
                "starts_on": "2026-09-01",
                "ends_on": None,
                "pool": 45,
                "schedule": [0, 2, 5],
            }
        ]
        (root / "rules.json").write_text(json.dumps(records))
        batch |= {
            "rules_manifest": "rules/manifest.json",
            "rules_records": "rules.json",
        }
    if enrichment:
        store = EvidenceStore(root / "enrichment")
        store.write(
            b"calendar evidence",
            url="https://example.test/calendar",
            http_status=200,
            content_type="text/html",
            status="valid",
        )
        records = [
            {
                "artifact_index": 0,
                "record": {
                    "dataset": "calendar_events",
                    "record_key": "lotto:2026-12-25",
                    "payload": {
                        "day": "2026-12-25",
                        "scheduled": False,
                        "description": "No draw",
                        "game": "lotto",
                    },
                },
            }
        ]
        if enrichment == "invalid":
            records[0]["record"]["payload"].pop("scheduled")
        (root / "enrichment.json").write_text(json.dumps(records))
        batch |= {
            "enrichment_manifest": "enrichment/manifest.json",
            "enrichment_records": "enrichment.json",
        }
    batch |= changes
    path = root / "batch.json"
    path.write_text(json.dumps({k: v for k, v in batch.items() if v is not ...}))
    return path


@pytest.fixture
def write_batch():
    return _write_batch


# Synthetic audit inputs shared by audit unit tests.
RULE_BODY = b"reviewed rule evidence"
OBS_BODY = b"observation evidence"
RULE_SHA = sha256(RULE_BODY)
OBS_SHA = sha256(OBS_BODY)
RULE_URL = "https://example.test/rules"


def make_rule(**changes):
    return (
        dict(
            code="6/47",
            starts_on=date(2026, 1, 1),
            ends_on=None,
            pool=47,
            schedule=[0, 2],
            evidence_url=RULE_URL,
            binding=dict(
                rule_code="6/47", artifact_sha256=RULE_SHA, source_url=RULE_URL
            ),
            verified=True,
            binding_matches=True,
        )
        | changes
    )


def make_draw(day, mains=(1, 2, 3, 4, 5, 6), bonus=7, **changes):
    key = observation_key("test", "https://example.test/r", OBS_SHA, "1", str(day))
    payload = dict(
        game="lotto", draw_date=day.isoformat(), mains=list(mains), bonus=bonus
    )
    return (
        dict(
            game="lotto",
            draw_date=day,
            status="accepted",
            rule_code="6/47",
            mains=sorted(mains),
            bonus=bonus,
            observation_key=key,
            observation=payload,
            evidence_ok=True,
            number_conflict=False,
        )
        | changes
    )


def lineage_for(draw):
    return dict(
        observation_key=draw["observation_key"],
        source="test",
        url="https://example.test/r",
        artifact_sha256=OBS_SHA,
        retrieved_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc),
        parser_version="1",
        record_key=draw["draw_date"].isoformat(),
        payload=draw["observation"],
        status="accepted",
    )


def build_inputs(draws, rules=None, events=(), enrichment=()):
    return AuditInputs(
        draws=list(draws),
        rules=list(rules or [make_rule()]),
        observations=[lineage_for(d) for d in draws if d["observation"]],
        issues=[],
        enrichment=list(enrichment),
        events=list(events),
        evidence={RULE_SHA: RULE_BODY, OBS_SHA: OBS_BODY},
        staged=dict(undated=0, malformed_date=0, staged_in_range=0),
    )


@pytest.fixture
def audit_factory():
    class Factory:
        rule = staticmethod(make_rule)
        draw = staticmethod(make_draw)
        inputs = staticmethod(build_inputs)

    return Factory
