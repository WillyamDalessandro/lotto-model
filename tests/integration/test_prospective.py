import threading
import time as clock
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lotto_model.audit.contracts import sha256
from lotto_model.ingestion.contracts import Observation
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.repository import Repository
from lotto_model.prospective.evaluation import evaluate_available, prospective_report
from lotto_model.prospective.issuance import issue
from lotto_model.prospective.protocol import ProspectiveProtocol

RULE_BODY = b"reviewed 6/45 rules"
URL = "https://example.test/results"
MON, WED, SAT = date(2031, 1, 6), date(2031, 1, 8), date(2031, 1, 11)
PAST_MON = date(2026, 9, 7)


def protocol(**changes):
    return ProspectiveProtocol(
        **dict(
            start_date=PAST_MON,
            rule_code="6/45",
            pool=45,
            schedule=(0, 2, 5),
            rule_evidence_sha256=sha256(RULE_BODY),
            schedule_evidence_sha256=sha256(RULE_BODY),
            deadline_local_time=time(19, 45),
            deadline_timezone="Europe/Dublin",
            deadline_evidence="test",
            arms=[dict(id="uniform", policy="uniform", budgets=[1, 5])],
            result_source_policy="test imports",
        )
        | changes
    )


def setup(conn, root):
    repo = Repository(conn)
    store = EvidenceStore(root)
    run = repo.start_run({"test": "prospective"})
    rule = repo.record_artifact(
        store.write(
            RULE_BODY,
            url="https://example.test/rules",
            http_status=200,
            content_type="application/pdf",
            status="valid",
        ),
        run,
        "rules",
        "manual",
    )
    repo.add_rule("6/45", date(2026, 9, 5), None, 45, [0, 2, 5], rule)
    return repo, store, run


def result(repo, store, run, day, mains, authority="independent", body=None):
    artifact = repo.record_artifact(
        store.write(
            body or f"{day}{mains}".encode(),
            url=URL,
            http_status=200,
            content_type="text/html",
            status="valid",
        ),
        run,
        authority,
        authority,
    )
    repo.ingest(Observation(draw_date=day, mains=mains, source_url=URL), artifact)
    return artifact


def test_issuance_timing_and_idempotence(connection, tmp_path):
    setup(connection, tmp_path)
    assert MON.weekday() == 0 and SAT.weekday() == 5
    value = protocol()
    first = issue(connection, value, MON, "uniform")
    assert first.status == "issued" and len(first.lines[5]) == 5
    assert all(n <= 45 for lines in first.lines.values() for x in lines for n in x)
    again = issue(connection, value, MON, "uniform")
    assert again.status == "existing" and again.lines == {
        k: [tuple(x) for x in v] for k, v in first.lines.items()
    }
    missed = issue(connection, value, PAST_MON, "uniform")
    assert missed.status == "missed" and missed.reason == "deadline_passed"
    now = connection.scalar(text("SELECT clock_timestamp()"))
    exact = protocol(deadline_overrides={WED: now})
    assert issue(connection, exact, WED, "uniform").status == "missed"
    with pytest.raises(ValueError, match="scheduled"):
        issue(connection, value, MON + timedelta(days=1), "uniform")
    with pytest.raises(ValueError, match="retroactive"):
        issue(connection, value, date(2026, 9, 5), "uniform")
    with pytest.raises(DBAPIError):
        with connection.begin_nested():
            connection.execute(text("UPDATE prospective_lines SET mains='[1]'"))
    assert connection.scalar(text("SELECT count(*) FROM prospective_lines")) == 6


def test_existing_result_refuses_issue(connection, tmp_path):
    repo, store, run = setup(connection, tmp_path)
    result(repo, store, run, SAT, (1, 2, 3, 4, 5, 6))
    late = issue(connection, protocol(), SAT, "uniform")
    assert late.status == "missed" and late.reason == "result_available"
    assert connection.scalar(text("SELECT count(*) FROM prospective_lines")) == 0


def test_rule_change_and_model_contract_fail_closed(connection, tmp_path):
    setup(connection, tmp_path)
    with pytest.raises(ValueError):
        issue(connection, protocol(rule_code="6/47", pool=47), MON, "uniform")
    contract = dict(
        frozen=dict(feature_columns=[], selected=dict(id="logistic-c0.01")),
        rule_code="6/45",
        pool=45,
        reviewed=True,
    )
    model = protocol(
        arms=[
            dict(id="model", policy="model", experimental=True, model_contract=contract)
        ]
    )
    failed = issue(connection, model, MON, "model")
    assert failed.status == "failed"


def test_result_revisions(connection, tmp_path):
    repo, store, run = setup(connection, tmp_path)
    value = protocol()
    issued = issue(connection, value, MON, "uniform")
    line = issued.lines[1][0]
    result(repo, store, run, MON, tuple(sorted(line)))
    assert evaluate_available(connection, value.digest) == {"scored": 6}
    assert evaluate_available(connection, value.digest) == {"unchanged": 6}
    other = tuple(n for n in range(1, 46) if n not in line)[:6]
    result(repo, store, run, MON, other, body=b"conflict")
    assert evaluate_available(connection, value.digest) == {"disputed": 6}
    operator = result(repo, store, run, MON, other, "operator", body=b"operator")
    observation = connection.scalar(
        text("SELECT id FROM source_observations WHERE artifact_id=:a"),
        dict(a=operator),
    )
    repo.resolve_numbers(observation)
    assert evaluate_available(connection, value.digest) == {"revised": 6}
    rows = connection.execute(
        text(
            "SELECT revision,matched_mains FROM prospective_evaluations e JOIN "
            "prospective_lines l ON l.id=e.line_id WHERE l.budget=1 ORDER BY revision"
        )
    ).all()
    assert [tuple(r) for r in rows] == [(1, 6), (2, 0)]
    assert connection.scalar(
        text("SELECT mains FROM prospective_lines WHERE budget=1")
    ) == list(line)


def test_coverage_denominators(connection, tmp_path):
    repo, store, run = setup(connection, tmp_path)
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    value = protocol(start_date=MON, deadline_overrides={WED: past})
    issue(connection, value, MON, "uniform")
    issue(connection, value, WED, "uniform")
    issue(connection, value, SAT, "uniform")
    result(repo, store, run, MON, (1, 2, 3, 4, 5, 6))
    result(repo, store, run, SAT, (1, 2, 3, 4, 5, 6))
    result(repo, store, run, SAT, (1, 2, 3, 4, 5, 7), body=b"conflict")
    evaluate_available(connection, value.digest)
    report = prospective_report(connection, value, as_of=SAT)
    arm = report["arms"]["uniform"]
    assert arm["scheduled_denominator"] == 3
    assert arm["coverage"] == {"completed": 1, "disputed": 1, "missed": 1}
    assert arm["completed_issue_performance"]["1"]["completed_draws"] == 1
    assert "no confirmed advantage" in report["label"]


DATA = (
    "prospective_evaluations,prospective_lines,prospective_issues,"
    "prospective_protocols,draw_numbers,prize_tiers,draw_context,quality_issues,"
    "draws,rule_regimes,games,fetch_checkpoints,retrieval_events,"
    "source_observations,raw_artifacts,ingestion_runs,sources"
)


def test_issue_ingestion_race(db_engine, tmp_path):
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {DATA} RESTART IDENTITY CASCADE"))
        repo, store, run = setup(conn, tmp_path)
    value = protocol()
    outcome = {}
    try:
        with db_engine.connect() as ingest_conn:
            transaction = ingest_conn.begin()
            repo = Repository(ingest_conn)
            result(repo, store, run, MON, (1, 2, 3, 4, 5, 6))  # holds draw lock

            def issuer():
                with db_engine.begin() as conn:
                    outcome["value"] = issue(conn, value, MON, "uniform")

            thread = threading.Thread(target=issuer)
            thread.start()
            clock.sleep(1.0)
            assert thread.is_alive(), "issuance must wait for the draw lock"
            transaction.commit()
            thread.join(timeout=30)
        assert outcome["value"].status == "missed"
        assert outcome["value"].reason == "result_available"
    finally:
        with db_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {DATA} RESTART IDENTITY CASCADE"))
