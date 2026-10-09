"""Experiment claims, append-only issuance and separate evaluations."""

import json
from collections import defaultdict

from sqlalchemy import text

from lotto_model.research.contracts import EvaluatedRecord, PredictionRecord


def lock_key(identity: str) -> int:
    """Stable signed 64-bit advisory-lock key derived from a hex digest."""
    value = int(identity[:16], 16)
    return value - 2**64 if value >= 2**63 else value


def acquire_run_lock(connection, identity: str):
    """Session lock so two processes cannot run the same identity."""
    if not connection.scalar(
        text("SELECT pg_try_advisory_lock(:k)"), dict(k=lock_key(identity))
    ):
        raise ValueError("Experiment identity is already running")


def release_run_lock(connection, identity: str):
    connection.execute(
        text("SELECT pg_advisory_unlock(:k)"), dict(k=lock_key(identity))
    )


def claim_experiment(connection, identity: str, frozen: dict) -> dict:
    """Insert-or-return; a different frozen configuration is rejected."""
    connection.execute(
        text(
            """INSERT INTO experiments(identity,protocol_digest,snapshot_digest,
            frozen,status) VALUES(:i,:p,:s,CAST(:f AS jsonb),'selected')
            ON CONFLICT(identity) DO NOTHING"""
        ),
        dict(
            i=identity,
            p=frozen["protocol_digest"],
            s=frozen["snapshot_digest"],
            f=json.dumps(frozen),
        ),
    )
    row = dict(
        connection.execute(
            text("SELECT * FROM experiments WHERE identity=:i FOR UPDATE"),
            dict(i=identity),
        )
        .mappings()
        .one()
    )
    if row["frozen"] != frozen:
        raise ValueError("Experiment identity exists with different configuration")
    return row


def set_status(connection, experiment_id: int, status: str, error: str | None = None):
    connection.execute(
        text(
            """UPDATE experiments SET status=:s,last_error=:e,updated_at=now(),
            attempts=attempts + CASE WHEN :s='evaluating' THEN 1 ELSE 0 END
            WHERE id=:i"""
        ),
        dict(s=status, e=error, i=experiment_id),
    )


def issue_predictions(
    connection, experiment_id: int, records: list[PredictionRecord], probabilities=None
):
    """Insert complete portfolios atomically (caller's transaction)."""
    portfolios = defaultdict(set)
    for record in records:
        portfolios[(record.target_date, record.budget)].add(record.line_index)
    if any(v != set(range(b)) for (_, b), v in portfolios.items()):
        raise ValueError("Incomplete portfolio cannot be issued")
    for record in records:
        connection.execute(
            text(
                """INSERT INTO experiment_predictions(experiment_id,target_date,budget,
                line_index,mains,probabilities,seed,max_input_date)
                VALUES(:e,:d,:b,:k,CAST(:m AS jsonb),CAST(:p AS jsonb),:s,:c)"""
            ),
            dict(
                e=experiment_id,
                d=record.target_date,
                b=record.budget,
                k=record.line_index,
                m=json.dumps(list(record.mains)),
                p=json.dumps(probabilities)
                if probabilities is not None and record.line_index == 0
                else None,
                s=record.seed,
                c=record.max_input_date,
            ),
        )


def issued(connection, experiment_id: int) -> list[dict]:
    return [
        dict(r)
        for r in connection.execute(
            text(
                """SELECT p.*,e.matched_mains,e.outcome,e.hit_3_plus,e.hit_5_plus
                FROM experiment_predictions p LEFT JOIN experiment_evaluations e
                ON e.prediction_id=p.id WHERE p.experiment_id=:e
                ORDER BY p.target_date,p.budget,p.line_index"""
            ),
            dict(e=experiment_id),
        ).mappings()
    ]


def record_evaluations(connection, experiment_id: int, records: list[EvaluatedRecord]):
    for record in records:
        p = record.prediction
        prediction_id = connection.scalar(
            text(
                """SELECT id FROM experiment_predictions WHERE experiment_id=:e
                AND target_date=:d AND budget=:b AND line_index=:k
                AND mains=CAST(:m AS jsonb)"""
            ),
            dict(
                e=experiment_id,
                d=p.target_date,
                b=p.budget,
                k=p.line_index,
                m=json.dumps(list(p.mains)),
            ),
        )
        if prediction_id is None:
            raise ValueError("Evaluation requires an issued prediction")
        connection.execute(
            text(
                """INSERT INTO experiment_evaluations(prediction_id,outcome,
                matched_mains,hit_3_plus,hit_5_plus) VALUES(:p,CAST(:o AS jsonb),
                :m,:h3,:h5) ON CONFLICT(prediction_id) DO NOTHING"""
            ),
            dict(
                p=prediction_id,
                o=json.dumps(list(record.outcome)),
                m=record.matched_mains,
                h3=record.hit_3_plus,
                h5=record.hit_5_plus,
            ),
        )
