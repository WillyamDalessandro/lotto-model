"""Typed audit contracts and canonical normalization shared by every audit step."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1
REASONS = (
    "invalid_bonus",
    "invalid_evidence",
    "invalid_mains",
    "invalid_status",
    "number_conflict",
    "observation_mismatch",
    "rule_mismatch",
    "unverified_rule",
)


class AuditRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    game: Literal["lotto"] = "lotto"
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("Audit start must not follow end")
        return self


class RuleBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_code: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str = Field(min_length=1)


class RuleBindings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    rules: list[RuleBinding]
    calendar_events: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique(self):
        codes = [r.rule_code for r in self.rules]
        if len(set(codes)) != len(codes):
            raise ValueError("Duplicate rule bindings")
        if len(set(self.calendar_events)) != len(self.calendar_events):
            raise ValueError("Duplicate calendar event bindings")
        return self


@dataclass
class AuditInputs:
    """Normalized, evidence-checked rows read from one consistent database view.

    draws: game, draw_date, status, rule_code, mains, bonus, observation_key,
      observation (payload) and evidence_ok.
    rules: code, starts_on, ends_on, pool, schedule, evidence_url, binding
      (artifact_sha256/source_url or None) and verified.
    observations: lineage records keyed by observation_key.
    issues: unresolved issues with draw_date and kind.
    enrichment: prize and context records with evidence_ok and disputed.
    events: reviewed calendar events (day, scheduled, record_key, sha256).
    evidence: sha256 -> verified bytes.
    """

    draws: list[dict] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    enrichment: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    evidence: dict[str, bytes] = field(default_factory=dict)
    staged: dict = field(default_factory=dict)
    blocking: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    eligible: list[dict]
    exclusions: list[dict]
    counts: dict
    schedule: dict
    enrichment: list[dict]
    enrichment_omitted: dict
    issues: list[dict]
    warnings: list[str]
    blocking: list[str]
    rules: list[dict]
    observations: list[dict]
    events: list[dict]
    evidence: dict[str, bytes]


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    content_sha256: str
    included_draws: int


@dataclass(frozen=True)
class VerificationResult:
    content_sha256: str
    included_draws: int


def _default(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Naive timestamps cannot be serialized")
        text = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return text
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"Unserializable {type(value).__name__}")


def canonical_json(value) -> bytes:
    """UTF-8, sorted keys, compact separators, ISO dates, Z timestamps, LF end."""
    text = json.dumps(
        value,
        default=_default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return (text + "\n").encode("utf8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def observation_key(
    source: str, url: str, artifact_sha256: str, parser_version: str, record_key
) -> str:
    """Portable observation identity independent of database surrogate IDs."""
    return sha256(
        canonical_json(
            dict(
                source=source,
                url=url,
                artifact_sha256=artifact_sha256,
                parser_version=parser_version,
                record_key=record_key,
            )
        )
    )
