from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ComplementaryRecord(BaseModel):
    dataset: Literal[
        "rule_attributes",
        "calendar_events",
        "winning_ticket_reports",
        "official_period_metrics",
    ]
    record_key: str = Field(min_length=1)
    published_at: datetime | None = None
    payload: dict

    @model_validator(mode="after")
    def required_fields(self):
        required = {
            "rule_attributes": ("effective_from", "effective_to", "attribute", "value"),
            "calendar_events": ("day", "scheduled", "description"),
            "winning_ticket_reports": ("draw_date", "channel", "location_meaning"),
            "official_period_metrics": (
                "period_start",
                "period_end",
                "game_scope",
                "metric",
                "value",
                "unit",
            ),
        }[self.dataset]
        if any(k not in self.payload for k in required):
            raise ValueError("Missing complementary dimensions")
        for key in (
            "effective_from",
            "effective_to",
            "day",
            "draw_date",
            "period_start",
            "period_end",
            "claim_date",
        ):
            if self.payload.get(key) is not None:
                date.fromisoformat(self.payload[key])
        if self.dataset == "calendar_events" and not isinstance(
            self.payload["scheduled"], bool
        ):
            raise ValueError("Scheduled must be boolean")
        if (
            self.dataset == "rule_attributes"
            and self.payload["effective_to"] is not None
        ):
            if self.payload["effective_from"] > self.payload["effective_to"]:
                raise ValueError("Invalid effective interval")
        if self.dataset == "official_period_metrics":
            if date.fromisoformat(self.payload["period_start"]) > date.fromisoformat(
                self.payload["period_end"]
            ):
                raise ValueError("Invalid reporting period")
            value = Decimal(str(self.payload["value"]))
            if not value.is_finite():
                raise ValueError("Invalid metric value")
        if self.dataset == "winning_ticket_reports":
            if any(
                k in self.payload
                for k in ("person_name", "player_name", "address", "email")
            ):
                raise ValueError("Private identities excluded")
            if self.payload["channel"] not in ("retail", "online", None):
                raise ValueError("Invalid channel")
            if self.payload["location_meaning"] not in (
                "purchase_county",
                "online_player_county",
                "unresolved",
                None,
            ):
                raise ValueError("Unverified location meaning")
            if (
                self.payload["channel"] == "online"
                and self.payload["location_meaning"] == "purchase_county"
            ):
                raise ValueError("Online location cannot imply a purchase county")
        return self


def ingest_complementary(repository, record: ComplementaryRecord, artifact_id):
    import json

    if (
        repository.sql(
            "SELECT status FROM raw_artifacts WHERE id=:a", a=artifact_id
        ).scalar_one()
        != "valid"
    ):
        raise ValueError("Complementary ingestion requires valid evidence")
    old = (
        repository.sql(
            f"SELECT payload,published_at FROM {record.dataset} WHERE record_key=:k AND artifact_id=:a",
            k=record.record_key,
            a=artifact_id,
        )
        .mappings()
        .first()
    )
    if old and (
        old["payload"] != record.payload or old["published_at"] != record.published_at
    ):
        raise ValueError("Changed curated payload requires new evidence or record key")
    # Dataset is an enum, so this identifier cannot contain user-provided SQL.
    repository.sql(
        f"INSERT INTO {record.dataset}(record_key,artifact_id,payload,published_at) VALUES(:k,:a,CAST(:p AS jsonb),:t) ON CONFLICT(record_key,artifact_id) DO NOTHING",
        k=record.record_key,
        a=artifact_id,
        p=json.dumps(record.payload),
        t=record.published_at,
    )
