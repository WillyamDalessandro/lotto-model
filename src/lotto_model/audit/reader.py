"""Read one consistent audit population and verify its evidence bytes.

The reader performs SELECT statements only. Callers open the connection with
REPEATABLE READ isolation so every query sees the same database snapshot.
"""

import hashlib
import re
from datetime import date
from pathlib import Path

from sqlalchemy import text

from lotto_model.audit.contracts import (
    AuditInputs,
    AuditRequest,
    RuleBindings,
    observation_key,
)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_evidence(path: str, expected_sha256: str, evidence_root: Path) -> bytes:
    """Return evidence bytes contained in evidence_root with the expected hash."""
    root = Path(evidence_root).resolve()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Evidence path escapes evidence root")
    if not resolved.is_file():
        raise ValueError("Evidence file missing")
    body = resolved.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError("Evidence hash mismatch")
    return body


class _Evidence:
    """Verify each artifact hash once; any readable stored copy is equivalent."""

    def __init__(self, root: Path):
        self.root = root
        self.verified: dict[str, bytes] = {}
        self.failed: set[tuple[str, str]] = set()

    def check(self, sha: str | None, path: str | None, status: str | None) -> bool:
        if sha is None or path is None or status != "valid":
            return False
        if sha in self.verified:
            return True
        if (sha, path) in self.failed:
            return False
        try:
            self.verified[sha] = read_evidence(path, sha, self.root)
        except (ValueError, OSError):
            self.failed.add((sha, path))
            return False
        return True


def _rows(connection, sql, **params):
    return [dict(r) for r in connection.execute(text(sql), params).mappings()]


def _lineage(row, prefix=""):
    return dict(
        observation_key=observation_key(
            row[prefix + "source"],
            row[prefix + "url"],
            row[prefix + "sha256"],
            row[prefix + "parser_version"],
            row[prefix + "record_key"],
        ),
        source=row[prefix + "source"],
        url=row[prefix + "url"],
        artifact_sha256=row[prefix + "sha256"],
        retrieved_at=row[prefix + "retrieved_at"],
        parser_version=row[prefix + "parser_version"],
        record_key=row[prefix + "record_key"],
        payload=row[prefix + "payload"],
        status=row[prefix + "status"],
    )


OBSERVATION_COLUMNS = """o.id AS obs_id,o.payload,o.record_key,o.parser_version,
o.status,a.sha256,a.url,a.body_path,a.status AS artifact_status,a.retrieved_at,
s.code AS source"""
OBSERVATION_JOIN = """JOIN raw_artifacts a ON a.id=o.artifact_id
JOIN sources s ON s.id=a.source_id"""


def read_inputs(
    connection,
    request: AuditRequest,
    evidence_root: Path,
    bindings: RuleBindings | None,
) -> AuditInputs:
    evidence = _Evidence(Path(evidence_root))
    inputs = AuditInputs()
    window = dict(game=request.game, start=request.start, end=request.end)

    rules = _rows(
        connection,
        """SELECT r.code,r.starts_on,r.ends_on,r.pool,r.schedule,r.evidence_url
        FROM rule_regimes r JOIN games g ON g.id=r.game_id
        WHERE g.code=:game AND r.starts_on<=:end
        AND (r.ends_on IS NULL OR r.ends_on>=:start) ORDER BY r.code""",
        **window,
    )
    known = set(
        connection.execute(
            text(
                "SELECT r.code FROM rule_regimes r JOIN games g ON g.id=r.game_id "
                "WHERE g.code=:game"
            ),
            dict(game=request.game),
        ).scalars()
    )
    bound = {b.rule_code: b for b in (bindings.rules if bindings else [])}
    if set(bound) - known:
        raise ValueError("Rule binding names an unknown rule")
    for rule in rules:
        rule["schedule"] = sorted(rule["schedule"])
        binding = bound.get(rule["code"])
        rule["binding"] = binding.model_dump() if binding else None
        rule["verified"] = False
        rule["binding_matches"] = False
        if binding:
            artifacts = _rows(
                connection,
                "SELECT sha256,url,body_path,status FROM raw_artifacts "
                "WHERE sha256=:h AND url=:u AND status='valid' ORDER BY id",
                h=binding.artifact_sha256,
                u=binding.source_url,
            )
            # Rows sharing an exact hash and URL are byte-identical evidence.
            rule["verified"] = any(
                evidence.check(a["sha256"], a["body_path"], a["status"])
                for a in artifacts
            )
            rule["binding_matches"] = rule["evidence_url"] == binding.source_url
    inputs.rules = rules

    draws = _rows(
        connection,
        f"""SELECT d.id,d.draw_date,d.status AS draw_status,g.code AS game,
        r.code AS rule_code,{OBSERVATION_COLUMNS}
        FROM draws d JOIN games g ON g.id=d.game_id
        JOIN rule_regimes r ON r.id=d.rule_id
        LEFT JOIN source_observations o ON o.id=d.accepted_observation_id
        LEFT JOIN raw_artifacts a ON a.id=o.artifact_id
        LEFT JOIN sources s ON s.id=a.source_id
        WHERE g.code=:game AND d.draw_date BETWEEN :start AND :end
        ORDER BY d.draw_date""",
        **window,
    )
    ids = [d["id"] for d in draws]
    numbers = {}
    for row in _rows(
        connection,
        "SELECT draw_id,number,role FROM draw_numbers WHERE draw_id = ANY(:ids)",
        ids=ids,
    ):
        numbers.setdefault(row["draw_id"], []).append(row)
    issues = _rows(
        connection,
        """SELECT q.draw_id,q.kind,o.payload->>'draw_date' AS observed_date
        FROM quality_issues q JOIN source_observations o ON o.id=q.observation_id
        WHERE q.resolved_at IS NULL AND (q.draw_id = ANY(:ids)
        OR (o.payload->>'game'=:game AND o.payload->>'draw_date' BETWEEN :s AND :e))
        ORDER BY q.kind""",
        ids=ids,
        game=request.game,
        s=request.start.isoformat(),
        e=request.end.isoformat(),
    )
    dates = {d["id"]: d["draw_date"] for d in draws}
    inputs.issues = sorted(
        (
            dict(
                draw_date=dates.get(i["draw_id"])
                or (
                    date.fromisoformat(i["observed_date"])
                    if i["observed_date"] and ISO_DATE.match(i["observed_date"])
                    else None
                ),
                kind=i["kind"],
            )
            for i in issues
        ),
        key=lambda i: (str(i["draw_date"]), i["kind"]),
    )
    conflicts = {
        i["draw_id"] for i in issues if i["kind"] == "number_conflict" and i["draw_id"]
    }
    for draw in draws:
        own = numbers.get(draw["id"], [])
        accepted = draw["obs_id"] is not None
        inputs.draws.append(
            dict(
                game=draw["game"],
                draw_date=draw["draw_date"],
                status=draw["draw_status"],
                rule_code=draw["rule_code"],
                mains=sorted(n["number"] for n in own if n["role"] == "main"),
                bonus=next((n["number"] for n in own if n["role"] == "bonus"), None),
                observation_key=_lineage(draw)["observation_key"] if accepted else None,
                observation=draw["payload"],
                evidence_ok=evidence.check(
                    draw["sha256"], draw["body_path"], draw["artifact_status"]
                ),
                number_conflict=draw["id"] in conflicts,
            )
        )

    observations = _rows(
        connection,
        f"""SELECT {OBSERVATION_COLUMNS} FROM source_observations o {OBSERVATION_JOIN}
        WHERE o.id IN (SELECT accepted_observation_id FROM draws WHERE id = ANY(:ids))
        OR (o.payload->>'game'=:game AND o.payload->>'draw_date' BETWEEN :s AND :e)""",
        ids=ids,
        game=request.game,
        s=request.start.isoformat(),
        e=request.end.isoformat(),
    )
    inputs.observations = sorted(
        (_lineage(o) for o in observations), key=lambda o: o["observation_key"]
    )
    counts = _rows(
        connection,
        """SELECT count(*) FILTER (WHERE payload->>'observation_kind'='undated')
        AS undated,
        count(*) FILTER (WHERE payload->>'draw_date' IS NOT NULL
          AND payload->>'draw_date' !~ '^\\d{4}-\\d{2}-\\d{2}$') AS malformed_date,
        count(*) FILTER (WHERE status='staged' AND payload->>'draw_date'
          BETWEEN :s AND :e) AS staged_in_range,
        count(*) FILTER (WHERE status='quarantined' AND payload->>'draw_date'
          BETWEEN :s AND :e) AS quarantined_in_range
        FROM source_observations WHERE coalesce(payload->>'game','lotto')=:game""",
        game=request.game,
        s=request.start.isoformat(),
        e=request.end.isoformat(),
    )[0]
    inputs.staged = counts

    for row in _rows(
        connection,
        f"""SELECT d.draw_date,p.tier,p.winners,p.original_amount,p.currency,
        p.prize_type,p.prize_as_published,{OBSERVATION_COLUMNS},
        EXISTS (SELECT 1 FROM quality_issues q WHERE q.draw_id=p.draw_id
          AND q.kind='prize_conflict:'||p.tier AND q.resolved_at IS NULL) AS disputed
        FROM prize_tiers p JOIN draws d ON d.id=p.draw_id
        JOIN source_observations o ON o.id=p.observation_id {OBSERVATION_JOIN}
        WHERE p.draw_id = ANY(:ids)""",
        ids=ids,
    ):
        inputs.enrichment.append(
            dict(
                kind="prize",
                draw_date=row["draw_date"],
                tier=row["tier"],
                winners=row["winners"],
                amount=row["original_amount"],
                currency=row["currency"],
                prize_type=row["prize_type"],
                published=row["prize_as_published"],
                disputed=row["disputed"],
                observation_key=_lineage(row)["observation_key"],
                evidence_ok=evidence.check(
                    row["sha256"], row["body_path"], row["artifact_status"]
                ),
            )
        )
    for row in _rows(
        connection,
        f"""SELECT d.draw_date,c.jackpot_amount,c.currency AS jackpot_currency,
        c.outcome,c.disputed,{OBSERVATION_COLUMNS}
        FROM draw_context c JOIN draws d ON d.id=c.draw_id
        JOIN source_observations o ON o.id=c.observation_id {OBSERVATION_JOIN}
        WHERE c.draw_id = ANY(:ids)""",
        ids=ids,
    ):
        inputs.enrichment.append(
            dict(
                kind="context",
                draw_date=row["draw_date"],
                tier="jackpot",
                amount=row["jackpot_amount"],
                currency=row["jackpot_currency"],
                outcome=row["outcome"],
                disputed=row["disputed"],
                observation_key=_lineage(row)["observation_key"],
                evidence_ok=evidence.check(
                    row["sha256"], row["body_path"], row["artifact_status"]
                ),
            )
        )

    keys = bindings.calendar_events if bindings else []
    events = _rows(
        connection,
        """SELECT e.record_key,e.payload,a.sha256,a.url,a.body_path,a.status
        FROM calendar_events e JOIN raw_artifacts a ON a.id=e.artifact_id
        WHERE e.record_key = ANY(:keys) ORDER BY e.record_key,a.sha256""",
        keys=keys,
    )
    if {e["record_key"] for e in events} != set(keys):
        raise ValueError("Bound calendar event not found")
    by_day = {}
    for event in events:
        payload = event["payload"]
        if (
            payload.get("game") != request.game
            or not isinstance(payload.get("scheduled"), bool)
            or not ISO_DATE.match(str(payload.get("day")))
        ):
            raise ValueError("Bound calendar event lacks game, day or scheduled")
        if not evidence.check(event["sha256"], event["body_path"], event["status"]):
            raise ValueError("Bound calendar event evidence invalid")
        day = date.fromisoformat(payload["day"])
        if by_day.setdefault(day, payload["scheduled"]) != payload["scheduled"]:
            inputs.blocking.append(f"conflicting_calendar_events:{day}")
        inputs.events.append(
            dict(
                day=day,
                scheduled=payload["scheduled"],
                record_key=event["record_key"],
                artifact_sha256=event["sha256"],
                url=event["url"],
            )
        )
    inputs.evidence = evidence.verified
    return inputs
