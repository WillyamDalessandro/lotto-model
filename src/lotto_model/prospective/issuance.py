"""Atomic pre-result issuance using the database clock as authority."""

import json
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text

from lotto_model.audit.contracts import canonical_json
from lotto_model.locks import lock_draw
from lotto_model.prospective.protocol import ProspectiveProtocol, validate_protocol
from lotto_model.research.contracts import ResearchDraw
from lotto_model.research.policies import derive_seed, uniform_portfolio


@dataclass
class IssueResult:
    status: str  # issued | existing | missed | failed
    issue_id: int
    reason: str | None = None
    lines: dict = field(default_factory=dict)  # budget -> list of lines


def verified_rules(connection, game: str = "lotto") -> list[dict]:
    rows = connection.execute(
        text(
            """SELECT r.code,r.starts_on,r.ends_on,r.pool,r.schedule,
            coalesce(array_agg(a.sha256) FILTER (WHERE a.sha256 IS NOT NULL),'{}')
              AS evidence_sha256
            FROM rule_regimes r JOIN games g ON g.id=r.game_id
            LEFT JOIN raw_artifacts a ON a.url=r.evidence_url AND a.status='valid'
            WHERE g.code=:g GROUP BY r.id ORDER BY r.starts_on"""
        ),
        dict(g=game),
    ).mappings()
    return [dict(r) for r in rows]


def register_protocol(connection, protocol: ProspectiveProtocol) -> int:
    """Validate against verified rules, then insert-or-return by digest."""
    validate_protocol(protocol, verified_rules(connection, protocol.game))
    connection.execute(
        text(
            """INSERT INTO prospective_protocols(digest,protocol)
            VALUES(:d,CAST(:p AS jsonb)) ON CONFLICT(digest) DO NOTHING"""
        ),
        dict(
            d=protocol.digest,
            p=canonical_json(protocol.model_dump(mode="json")).decode(),
        ),
    )
    return connection.scalar(
        text("SELECT id FROM prospective_protocols WHERE digest=:d"),
        dict(d=protocol.digest),
    )


def _existing(connection, protocol_id, arm, target):
    row = (
        connection.execute(
            text(
                """SELECT * FROM prospective_issues WHERE protocol_id=:p AND arm=:a
                AND target_date=:t"""
            ),
            dict(p=protocol_id, a=arm, t=target),
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    lines = {}
    for line in connection.execute(
        text(
            "SELECT budget,line_index,mains FROM prospective_lines WHERE issue_id=:i "
            "ORDER BY budget,line_index"
        ),
        dict(i=row["id"]),
    ):
        lines.setdefault(line.budget, []).append(tuple(line.mains))
    status = "existing" if row["status"] == "issued" else row["status"]
    return IssueResult(status, row["id"], row["reason"], lines)


def _history(connection, protocol, target) -> list[ResearchDraw]:
    rows = connection.execute(
        text(
            """SELECT d.draw_date,array_agg(n.number ORDER BY n.number) AS mains
            FROM draws d JOIN games g ON g.id=d.game_id
            JOIN rule_regimes r ON r.id=d.rule_id
            JOIN draw_numbers n ON n.draw_id=d.id AND n.role='main'
            WHERE g.code=:g AND r.code=:r AND d.status='accepted' AND d.draw_date<:t
            GROUP BY d.id ORDER BY d.draw_date"""
        ),
        dict(g=protocol.game, r=protocol.rule_code, t=target),
    )
    return [
        ResearchDraw(r.draw_date, protocol.rule_code, protocol.pool, tuple(r.mains))
        for r in rows
    ]


def _lines(protocol, arm, target, history):
    if arm.policy == "uniform":
        output = {}
        for budget in arm.budgets:
            seed = derive_seed(
                protocol.digest, arm.id, target, budget, 0, protocol.root_seed
            )
            output[budget] = (seed, uniform_portfolio(protocol.pool, budget, seed))
        return output
    from lotto_model.research.policies import weighted_portfolio
    from lotto_model.research.predictor import predict_next

    value = predict_next(arm.model_contract["frozen"], history, target, protocol.pool)
    output = {}
    for budget in arm.budgets:
        seed = derive_seed(
            protocol.digest, arm.id, target, budget, 0, protocol.root_seed
        )
        lines = (
            (tuple(value["mains"]),)
            if budget == 1
            else weighted_portfolio(value["probabilities"], budget, seed)
        )
        output[budget] = (seed, lines)
    return output


def _record(
    connection, protocol_id, arm, target, status, reason, deadline, now, cutoff
):
    return connection.scalar(
        text(
            """INSERT INTO prospective_issues(protocol_id,arm,target_date,status,
            reason,deadline,recorded_at,cutoff_date)
            VALUES(:p,:a,:t,:s,:r,:d,:n,:c) RETURNING id"""
        ),
        dict(
            p=protocol_id,
            a=arm,
            t=target,
            s=status,
            r=reason,
            d=deadline,
            n=now,
            c=cutoff,
        ),
    )


def issue(
    connection, protocol: ProspectiveProtocol, target_date: date, arm_id: str
) -> IssueResult:
    """Issue complete portfolios before the deadline and before any result.

    Runs inside the caller's transaction. The draw lock is taken before the
    clock and result checks, so concurrent ingestion cannot slip in between.
    """
    arm = protocol.arm(arm_id)
    if target_date < protocol.start_date:
        raise ValueError("Target precedes the protocol start; no retroactive issues")
    if target_date.weekday() not in protocol.schedule:
        raise ValueError("Target is not a verified scheduled draw date")
    protocol_id = register_protocol(connection, protocol)
    lock_draw(connection, protocol.game, target_date)
    existing = _existing(connection, protocol_id, arm.id, target_date)
    if existing is not None:
        return existing
    rules = [
        r
        for r in verified_rules(connection, protocol.game)
        if r["starts_on"] <= target_date
        and (r["ends_on"] is None or target_date <= r["ends_on"])
    ]
    if len(rules) != 1 or rules[0]["code"] != protocol.rule_code:
        raise ValueError("No single verified current rule covers the target")
    deadline = protocol.deadline(target_date)
    now = connection.scalar(text("SELECT clock_timestamp()"))
    result_exists = connection.scalar(
        text(
            """SELECT EXISTS(SELECT 1 FROM draws d JOIN games g ON g.id=d.game_id
            WHERE g.code=:g AND d.draw_date=:t)"""
        ),
        dict(g=protocol.game, t=target_date),
    )
    history = _history(connection, protocol, target_date)
    cutoff = history[-1].draw_date if history else None
    reason = (
        "result_available"
        if result_exists
        else "deadline_passed"
        if now >= deadline
        else None
    )
    if reason:
        identifier = _record(
            connection,
            protocol_id,
            arm.id,
            target_date,
            "missed",
            reason,
            deadline,
            now,
            cutoff,
        )
        return IssueResult("missed", identifier, reason)
    try:
        portfolios = _lines(protocol, arm, target_date, history)
    except ValueError as exc:
        identifier = _record(
            connection,
            protocol_id,
            arm.id,
            target_date,
            "failed",
            str(exc)[:200],
            deadline,
            now,
            cutoff,
        )
        return IssueResult("failed", identifier, str(exc)[:200])
    identifier = _record(
        connection,
        protocol_id,
        arm.id,
        target_date,
        "issued",
        None,
        deadline,
        now,
        cutoff,
    )
    lines = {}
    for budget, (seed, portfolio) in portfolios.items():
        if len(set(portfolio)) != budget or any(
            len(set(line)) != 6 or not all(1 <= n <= protocol.pool for n in line)
            for line in portfolio
        ):
            raise ValueError("Ineligible or incomplete portfolio")
        for index, line in enumerate(portfolio):
            connection.execute(
                text(
                    """INSERT INTO prospective_lines(issue_id,budget,line_index,
                    mains,seed)
                    VALUES(:i,:b,:k,CAST(:m AS jsonb),:s)"""
                ),
                dict(i=identifier, b=budget, k=index, m=json.dumps(list(line)), s=seed),
            )
        lines[budget] = list(portfolio)
    return IssueResult("issued", identifier, None, lines)
