import json
from datetime import date

from pydantic import ValidationError
from sqlalchemy import text

from lotto_model.contracts import DrawInput
from lotto_model.ingestion.contracts import Observation


class Repository:
    """Operations run within the caller's PostgreSQL transaction."""

    def __init__(self, connection):
        self.connection = connection

    def sql(self, statement, **params):
        return self.connection.execute(text(statement), params)

    def start_run(self, config):
        return self.sql(
            "INSERT INTO ingestion_runs(configuration) VALUES(CAST(:c AS jsonb)) RETURNING id",
            c=json.dumps(config),
        ).scalar_one()

    def finish_run(self, run, status, summary=None):
        self.sql(
            "UPDATE ingestion_runs SET status=:s,finished_at=now(),error_summary=:e WHERE id=:r",
            s=status,
            e=summary,
            r=run,
        )

    def record_artifact(self, artifact, run_id, code, authority, evidence_root=None):
        source = self.sql(
            "INSERT INTO sources(code,base_url,authority) VALUES(:c,:u,:a) ON CONFLICT(code) DO UPDATE SET code=EXCLUDED.code RETURNING id",
            c=code,
            u=artifact.url,
            a=authority,
        ).scalar_one()
        identifier = self.sql(
            """INSERT INTO raw_artifacts(source_id,run_id,url,final_url,retrieved_at,http_status,content_type,sha256,body_path,status,parser_version)
            VALUES(:s,:r,:u,:f,:t,:h,:c,:sha,:p,:st,'1')
            ON CONFLICT(source_id,url,sha256) DO UPDATE SET body_path=EXCLUDED.body_path RETURNING id""",
            s=source,
            r=run_id,
            u=artifact.url,
            f=artifact.final_url,
            t=artifact.retrieved_at,
            h=artifact.http_status,
            c=artifact.content_type,
            sha=artifact.sha256,
            p=str((evidence_root / artifact.body_path).resolve())
            if evidence_root
            else artifact.body_path,
            st=artifact.status,
        ).scalar_one()
        self.sql(
            "INSERT INTO retrieval_events(artifact_id,run_id,retrieved_at) VALUES(:a,:r,:t) ON CONFLICT DO NOTHING",
            a=identifier,
            r=run_id,
            t=artifact.retrieved_at,
        )
        return identifier

    def checkpoint(self, artifact, identifier, run, status):
        self.sql(
            """INSERT INTO fetch_checkpoints(source_url,artifact_id,run_id,status) VALUES(:u,:a,:r,:s)
            ON CONFLICT(source_url) DO UPDATE SET artifact_id=:a,run_id=:r,status=:s,updated_at=now()""",
            u=artifact.url,
            a=identifier,
            r=run,
            s=status,
        )

    def add_rule(self, code, starts_on, ends_on, pool, schedule, artifact_id):
        game = self.sql(
            "INSERT INTO games(code) VALUES('lotto') ON CONFLICT(code) DO UPDATE SET code=EXCLUDED.code RETURNING id"
        ).scalar_one()
        existing = (
            self.sql(
                "SELECT * FROM rule_regimes WHERE game_id=:g AND code=:c",
                g=game,
                c=code,
            )
            .mappings()
            .first()
        )
        expected = (starts_on, ends_on, pool, schedule)
        if existing:
            if (
                existing["starts_on"],
                existing["ends_on"],
                existing["pool"],
                existing["schedule"],
            ) != expected:
                raise ValueError("Existing rule differs; create a reviewed correction")
            return existing["id"]
        overlap = self.sql(
            """SELECT id FROM rule_regimes WHERE game_id=:g AND starts_on<=:end
            AND (ends_on IS NULL OR ends_on>=:start)""",
            g=game,
            start=starts_on,
            end=ends_on or date.max,
        ).first()
        if overlap:
            raise ValueError("Overlapping rule intervals")
        if (
            pool < 7
            or ends_on
            and ends_on < starts_on
            or any(x not in range(7) for x in schedule)
        ):
            raise ValueError("Invalid rule interval")
        url = self.sql(
            "SELECT url FROM raw_artifacts WHERE id=:a", a=artifact_id
        ).scalar_one()
        return self.sql(
            """INSERT INTO rule_regimes(game_id,code,starts_on,ends_on,pool,schedule,evidence_url)
            VALUES(:g,:c,:s,:e,:p,CAST(:w AS jsonb),:u) RETURNING id""",
            g=game,
            c=code,
            s=starts_on,
            e=ends_on,
            p=pool,
            w=json.dumps(schedule),
            u=url,
        ).scalar_one()

    def issue(self, observation, draw, kind, **detail):
        self.sql(
            """INSERT INTO quality_issues(observation_id,draw_id,kind,detail)
            VALUES(:o,:d,:k,CAST(:v AS jsonb)) ON CONFLICT(observation_id,kind) DO NOTHING""",
            o=observation,
            d=draw,
            k=kind,
            v=json.dumps(detail),
        )

    def ingest(self, observation: Observation, artifact_id: int, parser_version="1"):
        if (
            self.sql(
                "SELECT status FROM raw_artifacts WHERE id=:a", a=artifact_id
            ).scalar_one()
            != "valid"
        ):
            raise ValueError("Draw ingestion requires valid evidence")
        payload = observation.model_dump(mode="json")
        # A refreshed source body creates new evidence; repeated parsing is idempotent.
        key = f"{observation.game}:{observation.draw_date}:{observation.source_url}"
        obs = self.sql(
            """INSERT INTO source_observations(artifact_id,parser_version,record_key,payload)
            VALUES(:a,:p,:k,CAST(:v AS jsonb)) ON CONFLICT(artifact_id,parser_version,record_key)
            DO UPDATE SET id=source_observations.id RETURNING id""",
            a=artifact_id,
            p=parser_version,
            k=key,
            v=json.dumps(payload),
        ).scalar_one()
        if (
            self.sql(
                "SELECT payload FROM source_observations WHERE id=:o", o=obs
            ).scalar_one()
            != payload
        ):
            raise ValueError(
                "Changed payload requires a new parser version or artifact"
            )
        rules = (
            self.sql(
                """SELECT r.* FROM rule_regimes r JOIN games g ON g.id=r.game_id
            WHERE g.code=:g AND starts_on<=:d AND (ends_on IS NULL OR ends_on>=:d)""",
                g=observation.game,
                d=observation.draw_date,
            )
            .mappings()
            .all()
        )
        if len(rules) != 1:
            self.issue(
                obs, None, "unverified_rule", draw_date=str(observation.draw_date)
            )
            self.sql(
                "UPDATE source_observations SET status='staged' WHERE id=:o", o=obs
            )
            return "staged"
        rule = rules[0]
        try:
            DrawInput(
                game=observation.game,
                draw_date=observation.draw_date,
                rule=rule["code"],
                pool=rule["pool"],
                mains=observation.mains,
                bonus=observation.bonus,
            )
        except ValidationError:
            self.issue(
                obs, None, "invalid_numbers", draw_date=str(observation.draw_date)
            )
            self.sql(
                "UPDATE source_observations SET status='staged' WHERE id=:o", o=obs
            )
            return "staged"
        self.sql(
            """UPDATE quality_issues SET resolved_at=now(),resolution_observation_id=:o
                 WHERE observation_id=:o AND kind IN ('unverified_rule','invalid_numbers')
                 AND resolved_at IS NULL""",
            o=obs,
        )
        existing = (
            self.sql(
                "SELECT * FROM draws WHERE game_id=:g AND draw_date=:d FOR UPDATE",
                g=rule["game_id"],
                d=observation.draw_date,
            )
            .mappings()
            .first()
        )
        if existing:
            draw = existing["id"]
            numbers = self.sql(
                "SELECT number,role FROM draw_numbers WHERE draw_id=:d", d=draw
            ).all()
            old_mains = tuple(sorted(n for n, r in numbers if r == "main"))
            old_bonus = next((n for n, r in numbers if r == "bonus"), None)
            bonus_conflict = None not in (old_bonus, observation.bonus) and (
                old_bonus != observation.bonus
            )
            if old_mains != observation.mains or bonus_conflict:
                resolved = self.sql(
                    """SELECT id FROM quality_issues WHERE draw_id=:d AND kind='number_conflict'
                    AND resolved_at IS NOT NULL AND resolution_observation_id=:accepted
                    AND (observation_id=:o OR detail->>'previous_observation'=:old)""",
                    d=draw,
                    accepted=existing["accepted_observation_id"],
                    o=obs,
                    old=str(obs),
                ).first()
                if resolved:
                    self.sql(
                        "UPDATE source_observations SET status='superseded' WHERE id=:o",
                        o=obs,
                    )
                    return "superseded"
                self.issue(
                    obs,
                    draw,
                    "number_conflict",
                    previous_observation=existing["accepted_observation_id"],
                )
                self.sql("UPDATE draws SET status='quarantined' WHERE id=:d", d=draw)
                self.sql(
                    "UPDATE source_observations SET status='quarantined' WHERE id=:o",
                    o=obs,
                )
                return "quarantined"
            if existing["status"] == "quarantined":
                return "quarantined"
            if old_bonus is None and observation.bonus is not None:
                # A compatible later observation may supply an unknown bonus.
                self.sql(
                    "INSERT INTO draw_numbers(draw_id,number,role) VALUES(:d,:n,'bonus')",
                    d=draw,
                    n=observation.bonus,
                )
            result = "corroborated"
        else:
            draw = self.sql(
                "INSERT INTO draws(game_id,rule_id,draw_date,accepted_observation_id,status) VALUES(:g,:r,:d,:o,'accepted') RETURNING id",
                g=rule["game_id"],
                r=rule["id"],
                d=observation.draw_date,
                o=obs,
            ).scalar_one()
            for number in observation.mains:
                self.sql(
                    "INSERT INTO draw_numbers(draw_id,number,role) VALUES(:d,:n,'main')",
                    d=draw,
                    n=number,
                )
            if observation.bonus is not None:
                self.sql(
                    "INSERT INTO draw_numbers(draw_id,number,role) VALUES(:d,:n,'bonus')",
                    d=draw,
                    n=observation.bonus,
                )
            result = "accepted"
        if observation.draw_date.weekday() not in rule["schedule"]:
            self.issue(
                obs, draw, "schedule_exception", draw_date=str(observation.draw_date)
            )
        self._context(observation, obs, draw)
        for prize in observation.prizes:
            old = (
                self.sql(
                    "SELECT * FROM prize_tiers WHERE draw_id=:d AND tier=:t",
                    d=draw,
                    t=prize.tier,
                )
                .mappings()
                .first()
            )
            if old and any(
                old[field] is not None and value is not None and old[field] != value
                for field, value in [
                    ("winners", prize.winners),
                    ("original_amount", prize.amount),
                    ("currency", prize.currency),
                    (
                        "prize_type",
                        prize.prize_type
                        if prize.prize_type != "unresolved"
                        and old["prize_type"] != "unresolved"
                        else None,
                    ),
                ]
            ):
                self.issue(
                    obs,
                    draw,
                    "prize_conflict:" + prize.tier,
                    previous_observation=old["observation_id"],
                )
                continue
            if old:
                values = (prize.winners, prize.amount, prize.currency)
                previous = (old["winners"], old["original_amount"], old["currency"])
                if all(
                    v is not None or p is None for v, p in zip(values, previous)
                ) and (
                    any(p is None and v is not None for v, p in zip(values, previous))
                    or (
                        old["prize_type"] == "unresolved"
                        and prize.prize_type != "unresolved"
                    )
                ):
                    self.sql(
                        """UPDATE prize_tiers SET winners=:w,original_amount=:a,currency=:c,
                    prize_eur=:e,prize_as_published=:v,prize_type=:k,observation_id=:o WHERE id=:id""",
                        w=prize.winners,
                        a=prize.amount,
                        c=prize.currency,
                        e=prize.amount if prize.currency == "EUR" else None,
                        v=prize.original_text,
                        k=prize.prize_type,
                        o=obs,
                        id=old["id"],
                    )
                    continue
                # Do not combine partially observed fields from different publishers.
                if (old["winners"], old["original_amount"], old["currency"]) != (
                    prize.winners,
                    prize.amount,
                    prize.currency,
                ):
                    self.issue(
                        obs,
                        draw,
                        "partial_prize:" + prize.tier,
                        reason="Preserved as observation; no synthetic combined tier",
                    )
                continue
            self.sql(
                """INSERT INTO prize_tiers(draw_id,tier,winners,prize_eur,original_amount,currency,prize_as_published,prize_type,observation_id)
                VALUES(:d,:t,:w,:e,:a,:c,:v,:k,:o)""",
                d=draw,
                t=prize.tier,
                w=prize.winners,
                e=prize.amount if prize.currency == "EUR" else None,
                a=prize.amount,
                c=prize.currency,
                v=prize.original_text,
                k=prize.prize_type,
                o=obs,
            )
        self.sql("UPDATE source_observations SET status='accepted' WHERE id=:o", o=obs)
        return result

    def resolve_numbers(self, observation_id):
        evidence = (
            self.sql(
                """SELECT o.*,s.authority,a.status AS artifact_status FROM source_observations o
            JOIN raw_artifacts a ON a.id=o.artifact_id JOIN sources s ON s.id=a.source_id
            WHERE o.id=:o""",
                o=observation_id,
            )
            .mappings()
            .one()
        )
        if (
            evidence["authority"] != "operator"
            or evidence["artifact_status"] != "valid"
        ):
            raise ValueError("Resolution requires valid operator evidence")
        row = Observation.model_validate(evidence["payload"])
        draw = (
            self.sql(
                """SELECT d.id,d.status,r.code,r.pool FROM draws d JOIN games g ON g.id=d.game_id
            JOIN rule_regimes r ON r.id=d.rule_id WHERE g.code=:g AND draw_date=:day FOR UPDATE""",
                g=row.game,
                day=row.draw_date,
            )
            .mappings()
            .one()
        )
        if draw["status"] != "quarantined":
            raise ValueError("Resolution requires a quarantined draw")
        DrawInput(
            game=row.game,
            draw_date=row.draw_date,
            rule=draw["code"],
            pool=draw["pool"],
            mains=row.mains,
            bonus=row.bonus,
        )
        self.sql("DELETE FROM draw_numbers WHERE draw_id=:d", d=draw["id"])
        # Old enrichment remains in immutable observations; do not attach it to corrected numbers.
        self.sql("DELETE FROM prize_tiers WHERE draw_id=:d", d=draw["id"])
        self.sql("DELETE FROM draw_context WHERE draw_id=:d", d=draw["id"])
        bonus = [] if row.bonus is None else [(row.bonus, "bonus")]
        for number, role in [*((n, "main") for n in row.mains), *bonus]:
            self.sql(
                "INSERT INTO draw_numbers(draw_id,number,role) VALUES(:d,:n,:r)",
                d=draw["id"],
                n=number,
                r=role,
            )
        self.sql(
            "UPDATE draws SET status='accepted',accepted_observation_id=:o WHERE id=:d",
            o=observation_id,
            d=draw["id"],
        )
        self.sql(
            """UPDATE quality_issues SET resolved_at=now(),resolution_observation_id=:o
                 WHERE draw_id=:d AND kind='number_conflict' AND resolved_at IS NULL""",
            o=observation_id,
            d=draw["id"],
        )
        self.ingest(row, evidence["artifact_id"], evidence["parser_version"])

    def _context(self, row, obs, draw):
        if row.jackpot is None and row.outcome is None:
            return
        old = (
            self.sql("SELECT * FROM draw_context WHERE draw_id=:d", d=draw)
            .mappings()
            .first()
        )
        values = (row.jackpot, row.currency, row.outcome)
        if old:
            if any(
                old[k] is not None and v is not None and old[k] != v
                for k, v in zip(("jackpot_amount", "currency", "outcome"), values)
            ):
                self.issue(
                    obs,
                    draw,
                    "context_conflict",
                    previous_observation=old["observation_id"],
                )
                self.sql(
                    "UPDATE draw_context SET disputed=true WHERE draw_id=:d", d=draw
                )
            elif all(
                v is not None or old[k] is None
                for k, v in zip(("jackpot_amount", "currency", "outcome"), values)
            ) and any(
                old[k] is None and v is not None
                for k, v in zip(("jackpot_amount", "currency", "outcome"), values)
            ):
                self.sql(
                    """UPDATE draw_context SET jackpot_amount=:a,currency=:c,outcome=:v,
                observation_id=:o WHERE draw_id=:d""",
                    a=row.jackpot,
                    c=row.currency,
                    v=row.outcome,
                    o=obs,
                    d=draw,
                )
            return
        self.sql(
            "INSERT INTO draw_context(draw_id,jackpot_amount,currency,outcome,observation_id) VALUES(:d,:a,:c,:v,:o)",
            d=draw,
            a=row.jackpot,
            c=row.currency,
            v=row.outcome,
            o=obs,
        )
