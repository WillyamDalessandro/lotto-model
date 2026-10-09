"""Reviewed current-regime prospective protocols (immutable once frozen)."""

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lotto_model.audit.contracts import canonical_json, sha256
from lotto_model.research.contracts import ROOT_SEED


class Arm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    policy: Literal["uniform", "model"]
    budgets: tuple[int, ...] = (1,)
    experimental: bool = False
    # A model arm requires a reviewed current-regime training contract.
    model_contract: dict | None = None

    @model_validator(mode="after")
    def valid(self):
        if not self.budgets or len(set(self.budgets)) != len(self.budgets):
            raise ValueError("Arm budgets must be unique and nonempty")
        if any(b < 1 for b in self.budgets):
            raise ValueError("Budgets must be positive")
        if self.policy == "model":
            contract = self.model_contract or {}
            required = {"frozen", "rule_code", "pool", "reviewed"}
            if not required <= set(contract) or contract["reviewed"] is not True:
                raise ValueError(
                    "Model arm requires a reviewed current-regime contract"
                )
            if not self.experimental:
                raise ValueError("Model arms must be labelled experimental")
        elif self.model_contract is not None:
            raise ValueError("Uniform arms take no model contract")
        return self


class ProspectiveProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    start_date: date
    game: Literal["lotto"] = "lotto"
    rule_code: str
    pool: int = Field(ge=7)
    schedule: tuple[int, ...]
    rule_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deadline_local_time: time
    deadline_timezone: str
    deadline_evidence: str = Field(min_length=1)
    deadline_overrides: dict[date, datetime] = Field(default_factory=dict)
    arms: tuple[Arm, ...]
    root_seed: int = ROOT_SEED
    training_constraints: str = "Current-regime history only; no 6/47 transfer"
    result_source_policy: str = Field(min_length=1)
    review_window: int = Field(default=100, ge=1)
    reporting: str = "descriptive only; no interim confirmatory claims"

    @model_validator(mode="after")
    def valid(self):
        if not self.schedule or any(d not in range(7) for d in self.schedule):
            raise ValueError("A verified nonempty weekday schedule is required")
        if self.deadline_local_time.tzinfo is not None:
            raise ValueError("Deadline time is local to deadline_timezone")
        try:
            ZoneInfo(self.deadline_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown deadline timezone") from None
        if any(v.tzinfo is None for v in self.deadline_overrides.values()):
            raise ValueError("Deadline overrides must be timezone-aware")
        ids = [a.id for a in self.arms]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("Arms must be unique and nonempty")
        for arm in self.arms:
            contract = arm.model_contract
            if contract and (
                contract["pool"] != self.pool or contract["rule_code"] != self.rule_code
            ):
                raise ValueError("Model contract does not match the current regime")
        return self

    @property
    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))

    def arm(self, identifier: str) -> Arm:
        for arm in self.arms:
            if arm.id == identifier:
                return arm
        raise ValueError("Unknown arm")

    def deadline(self, target: date) -> datetime:
        """Explicit timezone-aware issue deadline instant for one draw date."""
        if target in self.deadline_overrides:
            return self.deadline_overrides[target]
        return datetime.combine(
            target, self.deadline_local_time, ZoneInfo(self.deadline_timezone)
        )


def validate_protocol(
    protocol: ProspectiveProtocol, verified_rules: list[dict]
) -> ProspectiveProtocol:
    """Require one evidence-backed rule matching the protocol's regime."""
    matches = [r for r in verified_rules if r["code"] == protocol.rule_code]
    if len(matches) != 1:
        raise ValueError("Protocol rule is not a verified current rule")
    rule = matches[0]
    if (
        rule["pool"] != protocol.pool
        or sorted(rule["schedule"]) != sorted(protocol.schedule)
        or protocol.rule_evidence_sha256 not in rule.get("evidence_sha256", ())
    ):
        raise ValueError("Protocol pool, schedule or evidence differs from rule")
    if rule["starts_on"] > protocol.start_date or (
        rule["ends_on"] is not None and rule["ends_on"] < protocol.start_date
    ):
        raise ValueError("Rule interval does not cover the protocol start (stale)")
    return protocol


def freeze_prospective(protocol: ProspectiveProtocol, output_root: Path) -> Path:
    body = canonical_json(protocol.model_dump(mode="json"))
    target = Path(output_root) / protocol.digest
    path = target / "protocol.json"
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError("Frozen prospective protocol differs from its digest")
        return target
    target.mkdir(parents=True, exist_ok=True)
    temporary = target / "protocol.json.tmp"
    temporary.write_bytes(body)
    temporary.replace(path)
    return target


def load_prospective(directory: Path) -> ProspectiveProtocol:
    directory = Path(directory)
    body = (directory / "protocol.json").read_bytes()
    protocol = ProspectiveProtocol.model_validate(json.loads(body))
    if (
        directory.name != protocol.digest
        or canonical_json(protocol.model_dump(mode="json")) != body
    ):
        raise ValueError("Prospective protocol does not match its digest")
    return protocol
