"""Pure audit policy: draw eligibility, schedule coverage and enrichment."""

from collections import Counter
from datetime import timedelta

from lotto_model.audit.contracts import AuditInputs, AuditRequest, AuditResult


def _covers(rule, day):
    return rule["starts_on"] <= day and (
        rule["ends_on"] is None or day <= rule["ends_on"]
    )


def draw_reasons(draw: dict, rules: dict) -> list[str]:
    """Return every applicable exclusion reason in sorted order."""
    reasons = set()
    rule = rules.get(draw["rule_code"])
    pool = rule["pool"] if rule else None
    mains = draw["mains"]
    if draw["status"] != "accepted":
        reasons.add("invalid_status")
    if (
        len(mains) != 6
        or len(set(mains)) != 6
        or pool is None
        or any(not 1 <= n <= pool for n in mains)
    ):
        reasons.add("invalid_mains")
    bonus = draw["bonus"]
    if bonus is not None and (bonus in mains or pool is None or not 1 <= bonus <= pool):
        reasons.add("invalid_bonus")
    observed = draw["observation"]
    if observed is None or (
        observed.get("game") != draw["game"]
        or observed.get("draw_date") != draw["draw_date"].isoformat()
        or sorted(observed.get("mains") or []) != sorted(mains)
        or (observed.get("bonus") is not None and observed.get("bonus") != bonus)
    ):
        reasons.add("observation_mismatch")
    if draw["number_conflict"]:
        reasons.add("number_conflict")
    if rule is None or not rule["verified"]:
        reasons.add("unverified_rule")
    if (
        rule is None
        or not _covers(rule, draw["draw_date"])
        or not rule["binding_matches"]
    ):
        reasons.add("rule_mismatch")
    if not draw["evidence_ok"]:
        reasons.add("invalid_evidence")
    return sorted(reasons)


def schedule_coverage(
    request: AuditRequest, rules: list[dict], events: list[dict], eligible_dates: set
):
    """Classify every requested date; unknown schedules never imply missing draws."""
    verified = [r for r in rules if r["verified"]]
    overrides = {e["day"]: e["scheduled"] for e in events}
    expected, missing, unexpected, unknown, blocking = 0, [], [], 0, []
    observed = 0
    day = request.start
    while day <= request.end:
        active = [r for r in verified if _covers(r, day)]
        if len(active) > 1:
            blocking.append(f"overlapping_rules:{day}")
        # An empty schedule is unknown, never proof that no draw was scheduled.
        scheduled = (
            day.weekday() in active[0]["schedule"]
            if len(active) == 1 and active[0]["schedule"]
            else None
        )
        scheduled = overrides.get(day, scheduled)
        if scheduled is None:
            unknown += 1
        elif scheduled:
            expected += 1
            if day in eligible_dates:
                observed += 1
            else:
                missing.append(day)
        elif day in eligible_dates:
            unexpected.append(day)
        day += timedelta(days=1)
    return (
        dict(
            expected=expected,
            eligible_observed=observed,
            missing_dates=missing,
            unexpected_dates=unexpected,
            unknown_schedule_days=unknown,
            eligible_on_unknown_days=len(eligible_dates) - observed - len(unexpected),
        ),
        sorted(set(blocking)),
    )


def audit_inputs(inputs: AuditInputs, request: AuditRequest) -> AuditResult:
    rules = {r["code"]: r for r in inputs.rules}
    population = [d for d in inputs.draws if d["game"] == request.game]
    eligible, exclusions = [], []
    for draw in sorted(population, key=lambda d: d["draw_date"]):
        reasons = draw_reasons(draw, rules)
        if reasons:
            exclusions.append(
                dict(
                    draw_date=draw["draw_date"],
                    rule_code=draw["rule_code"],
                    reasons=reasons,
                )
            )
        else:
            eligible.append(draw)
    dates = {d["draw_date"] for d in eligible}
    schedule, blocking = schedule_coverage(request, inputs.rules, inputs.events, dates)
    blocking = sorted({*inputs.blocking, *blocking})
    if schedule["unexpected_dates"]:
        blocking.append("unexpected_dates_require_reviewed_exception")
    if not eligible:
        blocking.append("zero_eligible_draws")

    enrichment, omitted = [], Counter()
    for item in sorted(
        inputs.enrichment, key=lambda e: (e["draw_date"], e["kind"], e["tier"])
    ):
        if item["draw_date"] not in dates:
            continue
        if not item["evidence_ok"]:
            omitted["unverifiable_evidence"] += 1
            continue
        enrichment.append({k: v for k, v in item.items() if k != "evidence_ok"})

    used = {d["observation_key"] for d in eligible} | {
        e["observation_key"] for e in enrichment
    }
    reason_counts = Counter(r for e in exclusions for r in e["reasons"])
    warnings = []
    if schedule["unknown_schedule_days"]:
        warnings.append("unknown_schedule_days")
    if schedule["missing_dates"]:
        warnings.append("missing_scheduled_draws")
    if any(not r["verified"] for r in inputs.rules):
        warnings.append("unverified_rules")
    counts = dict(
        canonical_candidates=len(population),
        included=len(eligible),
        excluded=len(exclusions),
        exclusion_reasons=dict(sorted(reason_counts.items())),
        observations=len(inputs.observations),
        **{k: v for k, v in sorted(inputs.staged.items())},
        enrichment_included=len(enrichment),
        enrichment_disputed=sum(e["disputed"] for e in enrichment),
    )
    assert counts["included"] + counts["excluded"] == counts["canonical_candidates"]
    # Keep selected and competing observations for exported or excluded draws.
    relevant = {d["draw_date"].isoformat() for d in population}
    keys = used | {d["observation_key"] for d in population}
    lineage = [
        o
        for o in inputs.observations
        if o["observation_key"] in keys or o["payload"].get("draw_date") in relevant
    ]
    shas = {o["artifact_sha256"] for o in lineage if o["observation_key"] in used}
    shas |= {r["binding"]["artifact_sha256"] for r in inputs.rules if r["verified"]}
    shas |= {e["artifact_sha256"] for e in inputs.events}
    return AuditResult(
        eligible=eligible,
        exclusions=exclusions,
        counts=counts,
        schedule=schedule,
        enrichment=enrichment,
        enrichment_omitted=dict(omitted),
        issues=inputs.issues,
        warnings=warnings,
        blocking=sorted(set(blocking)),
        rules=inputs.rules,
        observations=lineage,
        events=sorted(inputs.events, key=lambda e: (e["day"], e["record_key"])),
        evidence={k: v for k, v in inputs.evidence.items() if k in shas},
    )
