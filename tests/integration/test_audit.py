from datetime import date, datetime, timezone

from sqlalchemy import text

from lotto_model.audit.contracts import AuditRequest, RuleBinding, RuleBindings, sha256
from lotto_model.audit.eligibility import audit_inputs
from lotto_model.audit.reader import read_inputs
from lotto_model.ingestion.contracts import Observation, PrizeObservation
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.repository import Repository

RULE_BODY = b"reviewed 6/47 rules"
RULE_URL = "https://example.test/rules"
RESULT_URL = "https://example.test/results"
MON, TUE, WED = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
REQUEST = AuditRequest(start=MON, end=WED)
RETRIEVED = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
BINDINGS = RuleBindings(
    version=1,
    rules=[
        RuleBinding(
            rule_code="6/47", artifact_sha256=sha256(RULE_BODY), source_url=RULE_URL
        )
    ],
)


def seed(conn, root, mains=(1, 2, 3, 4, 5, 6), shift=0):
    """Seed rules, two lotto draws and a Plus draw on Monday."""
    repo = Repository(conn)
    for i in range(shift):
        repo.start_run({"shift": i})
    store = EvidenceStore(root)
    run = repo.start_run({"test": "audit"})
    rule = repo.record_artifact(
        store.write(
            RULE_BODY,
            url=RULE_URL,
            http_status=200,
            content_type="application/pdf",
            status="valid",
            retrieved_at=RETRIEVED,
        ),
        run,
        "rules",
        "manual",
        evidence_root=store.root,
    )
    repo.add_rule("6/47", date(2026, 1, 1), None, 47, [0, 2], rule)
    results = repo.record_artifact(
        store.write(
            b"results " + bytes(str(mains), "ascii"),
            url=RESULT_URL,
            http_status=200,
            content_type="text/html",
            status="valid",
            retrieved_at=RETRIEVED,
        ),
        run,
        "results",
        "independent",
        evidence_root=store.root,
    )
    for day, numbers, bonus in ((MON, (7, 8, 9, 10, 11, 12), None), (WED, mains, 13)):
        repo.ingest(
            Observation(
                draw_date=day,
                mains=numbers,
                bonus=bonus,
                source_url=RESULT_URL,
                prizes=[
                    PrizeObservation(
                        tier="match_3",
                        winners=10,
                        amount="11.50",
                        currency="EUR",
                        original_text="€11.50",
                    )
                ]
                if day == WED
                else [],
            ),
            results,
        )
    plus = conn.execute(
        text("INSERT INTO games(code) VALUES('lotto_plus') RETURNING id")
    ).scalar_one()
    plus_rule = conn.execute(
        text(
            "INSERT INTO rule_regimes(game_id,code,starts_on,pool,schedule) "
            "VALUES(:g,'plus',DATE '2026-01-01',47,'[0,2]') RETURNING id"
        ),
        dict(g=plus),
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO draws(game_id,rule_id,draw_date,status) "
            "VALUES(:g,:r,DATE '2026-10-05','pending')"
        ),
        dict(g=plus, r=plus_rule),
    )
    return store


def test_reader_preserves_population(connection, tmp_path):
    seed(connection, tmp_path / "raw")
    inputs = read_inputs(connection, REQUEST, tmp_path, BINDINGS)
    assert [d["draw_date"] for d in inputs.draws] == [MON, WED]
    assert all(d["game"] == "lotto" and d["evidence_ok"] for d in inputs.draws)
    assert inputs.rules[0]["verified"] and inputs.rules[0]["binding_matches"]
    assert inputs.draws[0]["bonus"] is None
    assert len(inputs.observations) == 2
    assert {e["kind"] for e in inputs.enrichment} == {"prize"}
    result = audit_inputs(inputs, REQUEST)
    assert result.counts["included"] == 2
    assert result.schedule["missing_dates"] == []
    assert not result.blocking
    assert sha256(RULE_BODY) in result.evidence


def test_unbound_or_wrong_hash_rule_is_unverified(connection, tmp_path):
    seed(connection, tmp_path / "raw")
    store = EvidenceStore(tmp_path / "raw")
    other = store.write(
        b"another rules version",
        url=RULE_URL,
        http_status=200,
        content_type="application/pdf",
        status="valid",
    )
    repo = Repository(connection)
    repo.record_artifact(
        other, repo.start_run({}), "rules", "manual", evidence_root=store.root
    )
    wrong = RuleBindings(
        version=1,
        rules=[
            RuleBinding(rule_code="6/47", artifact_sha256="0" * 64, source_url=RULE_URL)
        ],
    )
    inputs = read_inputs(connection, REQUEST, tmp_path, wrong)
    assert not inputs.rules[0]["verified"]
    result = audit_inputs(read_inputs(connection, REQUEST, tmp_path, None), REQUEST)
    assert result.counts["exclusion_reasons"]["unverified_rule"] == 2
    exact = read_inputs(connection, REQUEST, tmp_path, BINDINGS)
    assert exact.rules[0]["verified"]


def test_missing_or_escaped_evidence_prevents_inclusion(connection, tmp_path):
    store = seed(connection, tmp_path / "raw")
    inputs = read_inputs(connection, REQUEST, tmp_path / "elsewhere", BINDINGS)
    assert not any(d["evidence_ok"] for d in inputs.draws)
    body = next(p for p in store.root.glob("*.body") if p.read_bytes() != RULE_BODY)
    body.write_bytes(b"corrupted")
    result = audit_inputs(read_inputs(connection, REQUEST, tmp_path, BINDINGS), REQUEST)
    assert result.counts["exclusion_reasons"]["invalid_evidence"] == 2


def test_number_conflict_excluded_and_lineage_kept(connection, tmp_path):
    seed(connection, tmp_path / "raw")
    store = EvidenceStore(tmp_path / "raw")
    repo = Repository(connection)
    artifact = repo.record_artifact(
        store.write(
            b"conflicting",
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
            draw_date=WED, mains=(1, 2, 3, 4, 5, 9), bonus=13, source_url=RESULT_URL
        ),
        artifact,
    )
    result = audit_inputs(read_inputs(connection, REQUEST, tmp_path, BINDINGS), REQUEST)
    assert result.exclusions[0]["reasons"] == ["invalid_status", "number_conflict"]
    assert result.schedule["missing_dates"] == [WED]
    assert (
        len([o for o in result.observations if o["payload"]["draw_date"] == str(WED)])
        == 2
    )
