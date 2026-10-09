"""Score issued lines against accepted evidence; corrections add revisions."""

import json
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import text

from lotto_model.audit.contracts import observation_key
from lotto_model.prospective.protocol import ProspectiveProtocol


def _results(connection, game: str) -> dict:
    """Canonical results by date: accepted (with evidence key) or disputed."""
    rows = connection.execute(
        text(
            """SELECT d.draw_date,d.status,s.code AS source,a.url,a.sha256,
            o.parser_version,o.record_key,
            array_agg(n.number ORDER BY n.number) FILTER (WHERE n.role='main') AS mains
            FROM draws d JOIN games g ON g.id=d.game_id
            LEFT JOIN source_observations o ON o.id=d.accepted_observation_id
            LEFT JOIN raw_artifacts a ON a.id=o.artifact_id
            LEFT JOIN sources s ON s.id=a.source_id
            LEFT JOIN draw_numbers n ON n.draw_id=d.id
            WHERE g.code=:g GROUP BY d.id,s.code,a.url,a.sha256,o.parser_version,
            o.record_key"""
        ),
        dict(g=game),
    ).mappings()
    output = {}
    for r in rows:
        evidence = (
            observation_key(
                r["source"], r["url"], r["sha256"], r["parser_version"], r["record_key"]
            )
            if r["status"] == "accepted" and r["sha256"]
            else None
        )
        output[r["draw_date"]] = dict(
            status=r["status"], mains=r["mains"], evidence=evidence
        )
    return output


def evaluate_available(connection, protocol_digest: str) -> dict:
    """Append one evaluation per line per accepted result evidence (idempotent)."""
    protocol_id = connection.scalar(
        text("SELECT id FROM prospective_protocols WHERE digest=:d"),
        dict(d=protocol_digest),
    )
    if protocol_id is None:
        raise ValueError("Unknown prospective protocol")
    game = connection.scalar(
        text("SELECT protocol->>'game' FROM prospective_protocols WHERE id=:i"),
        dict(i=protocol_id),
    )
    results = _results(connection, game)
    lines = connection.execute(
        text(
            """SELECT l.id,l.mains,i.target_date FROM prospective_lines l
            JOIN prospective_issues i ON i.id=l.issue_id WHERE i.protocol_id=:p"""
        ),
        dict(p=protocol_id),
    ).mappings()
    counts = defaultdict(int)
    for line in lines:
        result = results.get(line["target_date"])
        if result is None:
            counts["pending"] += 1
            continue
        if result["evidence"] is None:
            counts["disputed"] += 1
            continue
        known = connection.execute(
            text(
                "SELECT result_evidence,revision FROM prospective_evaluations "
                "WHERE line_id=:l"
            ),
            dict(l=line["id"]),
        ).all()
        if result["evidence"] in {k.result_evidence for k in known}:
            counts["unchanged"] += 1
            continue
        matched = len(set(line["mains"]) & set(result["mains"]))
        connection.execute(
            text(
                """INSERT INTO prospective_evaluations(line_id,result_evidence,revision,
                outcome,matched_mains,hit_3_plus,hit_5_plus)
                VALUES(:l,:e,:r,CAST(:o AS jsonb),:m,:h3,:h5)"""
            ),
            dict(
                l=line["id"],
                e=result["evidence"],
                r=1 + max((k.revision for k in known), default=0),
                o=json.dumps(list(result["mains"])),
                m=matched,
                h3=matched >= 3,
                h5=matched >= 5,
            ),
        )
        counts["revised" if known else "scored"] += 1
    return dict(sorted(counts.items()))


def scheduled_dates(protocol: ProspectiveProtocol, through: date) -> list[date]:
    days, day = [], protocol.start_date
    while day <= through:
        if day.weekday() in protocol.schedule:
            days.append(day)
        day += timedelta(days=1)
    return days


def prospective_report(
    connection, protocol: ProspectiveProtocol, as_of: date | None = None
) -> dict:
    """Coverage and completed-issue performance, per arm, latest revisions."""
    as_of = as_of or connection.scalar(text("SELECT current_date"))
    protocol_id = connection.scalar(
        text("SELECT id FROM prospective_protocols WHERE digest=:d"),
        dict(d=protocol.digest),
    )
    results = _results(connection, protocol.game)
    scheduled = scheduled_dates(protocol, as_of)
    arms = {}
    for arm in protocol.arms:
        issues = {
            r.target_date: r
            for r in connection.execute(
                text(
                    "SELECT id,target_date,status,reason FROM prospective_issues "
                    "WHERE protocol_id=:p AND arm=:a"
                ),
                dict(p=protocol_id, a=arm.id),
            )
        }
        latest = defaultdict(dict)
        for row in connection.execute(
            text(
                """SELECT DISTINCT ON (l.id) i.target_date,l.budget,l.line_index,
                e.matched_mains,e.hit_3_plus,e.hit_5_plus FROM prospective_lines l
                JOIN prospective_issues i ON i.id=l.issue_id
                JOIN prospective_evaluations e ON e.line_id=l.id
                WHERE i.protocol_id=:p AND i.arm=:a ORDER BY l.id,e.revision DESC"""
            ),
            dict(p=protocol_id, a=arm.id),
        ):
            latest[(row.target_date, row.budget)][row.line_index] = row
        coverage = defaultdict(int)
        for day in scheduled:
            issue = issues.get(day)
            if issue is None:
                coverage["unrecorded"] += 1
            elif issue.status != "issued":
                coverage[issue.status] += 1
            elif results.get(day) is None:
                coverage["pending"] += 1
            elif results[day]["evidence"] is None:
                coverage["disputed"] += 1
            else:
                coverage["completed"] += 1
        performance = {}
        for budget in arm.budgets:
            scored = {
                d: v for (d, b), v in latest.items() if b == budget and len(v) == budget
            }
            performance[str(budget)] = dict(
                completed_draws=len(scored),
                any_line_hit_3_plus=sum(
                    any(r.hit_3_plus for r in v.values()) for v in scored.values()
                ),
                any_line_hit_5_plus=sum(
                    any(r.hit_5_plus for r in v.values()) for v in scored.values()
                ),
                line_hit_3_plus=sum(
                    r.hit_3_plus for v in scored.values() for r in v.values()
                ),
                lines=sum(len(v) for v in scored.values()),
            )
        completed = coverage["completed"]
        arms[arm.id] = dict(
            policy=arm.policy,
            experimental=arm.experimental,
            scheduled_denominator=len(scheduled),
            coverage=dict(sorted(coverage.items())),
            completed_issue_performance=performance,
            review_window=dict(
                size=protocol.review_window,
                completed=completed,
                reached=completed >= protocol.review_window,
            ),
        )
    return dict(
        protocol_digest=protocol.digest,
        rule_code=protocol.rule_code,
        pool=protocol.pool,
        start_date=protocol.start_date.isoformat(),
        as_of=as_of.isoformat(),
        arms=arms,
        label="Descriptive interim report; no confirmed advantage is claimed.",
    )
