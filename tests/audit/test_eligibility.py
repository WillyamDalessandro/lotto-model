from datetime import date
from decimal import Decimal

from lotto_model.audit.contracts import AuditRequest
from lotto_model.audit.eligibility import audit_inputs

MON, TUE, WED, THU = (date(2026, 10, d) for d in (5, 6, 7, 8))
REQUEST = AuditRequest(start=MON, end=THU)


def test_draw_eligibility_reasons(audit_factory):
    f = audit_factory
    cases = {
        "ok": (f.draw(WED, bonus=None), []),
        "dup": (f.draw(WED, mains=(1, 1, 2, 3, 4, 5)), ["invalid_mains"]),
        "pool": (f.draw(WED, mains=(1, 2, 3, 4, 5, 48)), ["invalid_mains"]),
        "bonus": (f.draw(WED, bonus=6), ["invalid_bonus"]),
        "status": (f.draw(WED, status="quarantined"), ["invalid_status"]),
        "evidence": (f.draw(WED, evidence_ok=False), ["invalid_evidence"]),
        "conflict": (f.draw(WED, number_conflict=True), ["number_conflict"]),
    }
    for name, (draw, reasons) in cases.items():
        result = audit_inputs(f.inputs([draw]), REQUEST)
        got = result.exclusions[0]["reasons"] if result.exclusions else []
        assert got == reasons, name
    mismatch = f.draw(WED)
    mismatch["observation"] = mismatch["observation"] | {"mains": [1, 2, 3, 4, 5, 9]}
    result = audit_inputs(f.inputs([mismatch]), REQUEST)
    assert result.exclusions[0]["reasons"] == ["observation_mismatch"]
    unverified = f.rule(verified=False)
    result = audit_inputs(f.inputs([f.draw(WED)], rules=[unverified]), REQUEST)
    assert result.exclusions[0]["reasons"] == ["unverified_rule"]
    late = f.rule(starts_on=THU)
    result = audit_inputs(f.inputs([f.draw(WED)], rules=[late]), REQUEST)
    assert result.exclusions[0]["reasons"] == ["rule_mismatch"]
    many = f.draw(WED, bonus=3, status="pending", evidence_ok=False)
    result = audit_inputs(f.inputs([many]), REQUEST)
    assert result.exclusions[0]["reasons"] == [
        "invalid_bonus",
        "invalid_evidence",
        "invalid_status",
    ]
    assert result.counts["included"] + result.counts["excluded"] == 1


def test_schedule_populations(audit_factory):
    f = audit_factory
    plus = f.draw(MON, game="lotto_plus")
    result = audit_inputs(f.inputs([f.draw(WED), plus]), REQUEST)
    assert result.schedule["expected"] == 2
    assert result.schedule["eligible_observed"] == 1
    assert result.schedule["missing_dates"] == [MON]
    assert result.counts["canonical_candidates"] == 1
    assert not result.blocking
    empty = audit_inputs(f.inputs([f.draw(WED)], rules=[f.rule(schedule=[])]), REQUEST)
    assert empty.schedule["expected"] == 0
    assert empty.schedule["unknown_schedule_days"] == 4
    assert empty.schedule["missing_dates"] == []
    assert empty.schedule["unexpected_dates"] == []
    unknown = audit_inputs(
        f.inputs([f.draw(WED)], rules=[f.rule(verified=False)]), REQUEST
    )
    assert unknown.schedule["unknown_schedule_days"] == 4
    assert unknown.schedule["missing_dates"] == []


def test_boundaries_and_exceptions(audit_factory):
    f = audit_factory
    first = f.rule(ends_on=TUE)
    second = f.rule(code="next", starts_on=WED, schedule=[2])
    result = audit_inputs(
        f.inputs([f.draw(MON), f.draw(WED, rule_code="next")], rules=[first, second]),
        REQUEST,
    )
    assert result.counts["included"] == 2 and not result.blocking
    overlap = f.rule(code="next", starts_on=TUE)
    result = audit_inputs(f.inputs([f.draw(MON)], rules=[f.rule(), overlap]), REQUEST)
    assert any(b.startswith("overlapping_rules") for b in result.blocking)
    tuesday = audit_inputs(f.inputs([f.draw(TUE)]), REQUEST)
    assert tuesday.schedule["unexpected_dates"] == [TUE]
    assert "unexpected_dates_require_reviewed_exception" in tuesday.blocking
    event = dict(day=TUE, scheduled=True, record_key="k", artifact_sha256="a" * 64)
    reviewed = audit_inputs(f.inputs([f.draw(TUE)], events=[event]), REQUEST)
    assert reviewed.schedule["unexpected_dates"] == [] and not reviewed.blocking
    inputs = f.inputs([f.draw(WED)])
    inputs.blocking.append("conflicting_calendar_events:2026-10-06")
    assert (
        "conflicting_calendar_events:2026-10-06"
        in audit_inputs(inputs, REQUEST).blocking
    )
    assert "zero_eligible_draws" in audit_inputs(f.inputs([]), REQUEST).blocking


def test_enrichment_does_not_drop_numbers(audit_factory):
    f = audit_factory
    draw = f.draw(WED)
    prize = dict(
        kind="prize",
        draw_date=WED,
        tier="match_6",
        winners=None,
        amount=Decimal("1.20"),
        currency="EUR",
        disputed=True,
        observation_key=draw["observation_key"],
        evidence_ok=True,
    )
    bad = prize | dict(tier="match_5", disputed=False, evidence_ok=False)
    result = audit_inputs(f.inputs([draw], enrichment=[prize, bad]), REQUEST)
    assert result.counts["included"] == 1
    assert result.enrichment == [{k: v for k, v in prize.items() if k != "evidence_ok"}]
    assert result.enrichment[0]["winners"] is None
    assert result.counts["enrichment_disputed"] == 1
    assert result.enrichment_omitted == {"unverifiable_evidence": 1}
