"""Reviewed offline acquisition batches imported in one transaction."""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lotto_model.ingestion.complementary import (
    ComplementaryRecord,
    ingest_complementary,
)
from lotto_model.ingestion.contracts import Artifact
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.report import acquisition_status
from lotto_model.ingestion.repository import Repository
from lotto_model.ingestion.workflows import parse_saved

PAIRS = (
    ("rules_manifest", "rules_records"),
    ("enrichment_manifest", "enrichment_records"),
)
PATH_FIELDS = (
    "permission_evidence_path",
    "evidence_root",
    "draw_manifest",
    *(name for pair in PAIRS for name in pair),
)


class AcquisitionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    source_code: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
    permission_evidence_path: str
    permission_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    permitted_use: Literal["local_research"]
    evidence_root: str = "."
    draw_manifest: str | None = None
    adapter: Literal["csv", "observations"] = "csv"
    rules_manifest: str | None = None
    rules_records: str | None = None
    enrichment_manifest: str | None = None
    enrichment_records: str | None = None

    @model_validator(mode="after")
    def paired_inputs(self):
        for manifest, records in PAIRS:
            if (getattr(self, manifest) is None) != (getattr(self, records) is None):
                raise ValueError("Manifest and records must be supplied together")
        if not (self.draw_manifest or self.rules_manifest or self.enrichment_manifest):
            raise ValueError("Batch contains no inputs")
        return self


@dataclass
class PreparedBatch:
    """A batch whose every input was verified before any database write."""

    batch: AcquisitionBatch
    digest: str
    permission_sha256: str
    draws: list = field(default_factory=list)  # (Artifact, bytes, rows)
    rules: list = field(default_factory=list)  # (Artifact, bytes, definition)
    enrichment: list = field(default_factory=list)  # (Artifact, bytes, record)


def _contained(base: Path, roots: list[Path], value: str) -> Path:
    relative = Path(value)
    path = (relative if relative.is_absolute() else base / relative).resolve()
    if not any(path == r or path.is_relative_to(r) for r in roots):
        raise ValueError("Batch path escapes its directory and evidence root")
    return path


def _artifacts(path: Path, root: Path):
    store = EvidenceStore.__new__(EvidenceStore)
    store.root = root
    artifacts = store.load_manifest(path)
    return [(a, store.read(a, path.parent)) for a in artifacts]


def _indexed(artifacts, definition):
    index = definition.get("artifact_index")
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValueError("Record requires an integer artifact_index")
    if not 0 <= index < len(artifacts):
        raise ValueError("Record artifact_index out of range")
    artifact, body = artifacts[index]
    if artifact.status != "valid":
        raise ValueError("Records require valid evidence")
    return artifact, body


def _rule_definition(definition):
    if set(definition) - {
        "artifact_index",
        "code",
        "starts_on",
        "ends_on",
        "pool",
        "schedule",
    }:
        raise ValueError("Unexpected rule fields")
    starts = date.fromisoformat(definition["starts_on"])
    ends = definition.get("ends_on")
    ends = date.fromisoformat(ends) if ends else None
    pool, schedule = definition["pool"], definition["schedule"]
    if (
        not isinstance(definition["code"], str)
        or not definition["code"]
        or not isinstance(pool, int)
        or isinstance(pool, bool)
        or pool < 7
        or (ends and ends < starts)
        or not isinstance(schedule, list)
        or len(set(schedule)) != len(schedule)
        or any(
            not isinstance(d, int) or isinstance(d, bool) or d not in range(7)
            for d in schedule
        )
    ):
        raise ValueError("Invalid rule definition")
    return dict(
        code=definition["code"],
        starts_on=starts,
        ends_on=ends,
        pool=pool,
        schedule=schedule,
    )


def validate_batch(path: Path) -> PreparedBatch:
    """Resolve and verify every input; performs no database or network access."""
    path = Path(path).resolve()
    batch = AcquisitionBatch.model_validate_json(path.read_text(encoding="utf8"))
    base = path.parent
    root = _contained(base, [base], batch.evidence_root)
    roots = [base, root]
    resolve = {
        name: _contained(base, roots, getattr(batch, name))
        for name in PATH_FIELDS[2:]
        if getattr(batch, name) is not None
    }
    permission = _contained(base, roots, batch.permission_evidence_path).read_bytes()
    permission_hash = hashlib.sha256(permission).hexdigest()
    if permission_hash != batch.permission_evidence_sha256:
        raise ValueError("Permission evidence hash mismatch")
    prepared = PreparedBatch(batch, "", permission_hash)
    inputs = {"permission": permission_hash}
    if "draw_manifest" in resolve:
        artifacts = _artifacts(resolve["draw_manifest"], root)
        for artifact, body in artifacts:
            rows = (
                parse_saved(body, artifact.final_url, batch.adapter)
                if artifact.status == "valid"
                else []
            )
            prepared.draws.append((artifact, body, rows))
        if not any(rows for *_, rows in prepared.draws):
            raise ValueError("Draw manifest contains no valid observations")
        inputs["draws"] = sorted(a.sha256 for a, *_ in artifacts)
    if "rules_manifest" in resolve:
        artifacts = _artifacts(resolve["rules_manifest"], root)
        definitions = json.loads(resolve["rules_records"].read_text(encoding="utf8"))
        if not isinstance(definitions, list) or not definitions:
            raise ValueError("Rule records must be a nonempty list")
        codes = [d.get("code") for d in definitions]
        if len(set(codes)) != len(codes):
            raise ValueError("Duplicate rule codes")
        for definition in definitions:
            artifact, body = _indexed(artifacts, definition)
            prepared.rules.append((artifact, body, _rule_definition(definition)))
        inputs["rules"] = sorted(
            json.dumps(
                [
                    a.sha256,
                    {
                        **d,
                        "starts_on": str(d["starts_on"]),
                        "ends_on": str(d["ends_on"]),
                    },
                ],
                sort_keys=True,
            )
            for a, _, d in prepared.rules
        )
    if "enrichment_manifest" in resolve:
        artifacts = _artifacts(resolve["enrichment_manifest"], root)
        definitions = json.loads(
            resolve["enrichment_records"].read_text(encoding="utf8")
        )
        if not isinstance(definitions, list) or not definitions:
            raise ValueError("Enrichment records must be a nonempty list")
        for definition in definitions:
            artifact, body = _indexed(artifacts, definition)
            record = ComplementaryRecord.model_validate(definition["record"])
            prepared.enrichment.append((artifact, body, record))
        inputs["enrichment"] = sorted(
            json.dumps([a.sha256, r.model_dump(mode="json")], sort_keys=True)
            for a, _, r in prepared.enrichment
        )
    prepared.digest = batch_digest(batch, inputs)
    return prepared


def batch_digest(batch: AcquisitionBatch, inputs: dict) -> str:
    """Hash normalized configuration and input content, excluding host paths."""
    config = batch.model_dump(exclude=set(PATH_FIELDS))
    canonical = json.dumps(
        {"config": config, "inputs": inputs}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def preserve_evidence(prepared: PreparedBatch, store: EvidenceStore):
    """Copy verified bodies into the evidence store before the transaction."""
    preserved = {}
    for artifact, body, _ in [*prepared.draws, *prepared.rules, *prepared.enrichment]:
        key = (artifact.url, artifact.sha256)
        if key not in preserved:
            preserved[key] = store.write(
                body, **artifact.model_dump(exclude={"sha256", "body_path"})
            )
    return preserved


def import_batch(
    connection, prepared: PreparedBatch, preserved: dict, store_root: Path
) -> dict:
    """Import rules, then observations, then enrichment in the caller's transaction."""
    repo = Repository(connection)
    batch = prepared.batch
    run = repo.start_run(
        {
            "batch_digest": prepared.digest,
            "source_code": batch.source_code,
            "permitted_use": batch.permitted_use,
            "permission_sha256": prepared.permission_sha256,
        }
    )
    identifiers = {}

    def record(artifact: Artifact, prefix: str):
        stored = preserved[(artifact.url, artifact.sha256)]
        key = (prefix, stored.url, stored.sha256)
        if key not in identifiers:
            identifiers[key] = repo.record_artifact(
                stored,
                run,
                f"{prefix}:{batch.source_code}",
                "manual",
                evidence_root=store_root,
            )
        return identifiers[key]

    counts = Counter()
    for artifact, _, definition in prepared.rules:
        repo.add_rule(**definition, artifact_id=record(artifact, "rules"))
        counts["rules"] += 1
    for artifact, _, rows in prepared.draws:
        if artifact.status != "valid":
            counts[artifact.status] += 1
            continue
        identifier = record(artifact, "batch")
        for row in rows:
            counts[repo.ingest(row, identifier)] += 1
    for artifact, _, item in prepared.enrichment:
        ingest_complementary(repo, item, record(artifact, "curated"))
        counts["enrichment"] += 1
    repo.finish_run(run, "completed", json.dumps(counts, sort_keys=True))
    return dict(digest=prepared.digest, run_id=run, counts=dict(sorted(counts.items())))


def run_batch(
    engine, path: Path, receipt: Path | None = None, store_root: Path = Path("data/raw")
) -> dict:
    """Validate first, preserve evidence, then import atomically and write a receipt."""
    prepared = validate_batch(path)
    store = EvidenceStore(store_root)
    preserved = preserve_evidence(prepared, store)
    with engine.connect() as conn:
        before = acquisition_status(conn)
    with engine.begin() as conn:
        result = import_batch(conn, prepared, preserved, store.root)
    with engine.connect() as conn:
        after = acquisition_status(conn)
    result |= dict(
        status="committed",
        permission_sha256=prepared.permission_sha256,
        evidence_sha256=sorted(
            {
                a.sha256
                for a, *_ in [*prepared.draws, *prepared.rules, *prepared.enrichment]
            }
        ),
        coverage_before=before,
        coverage_after=after,
    )
    if receipt is not None:
        try:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(
                json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf8",
            )
        except OSError:
            result["receipt_error"] = (
                "Import committed; receipt not written. Replay is idempotent."
            )
    return result
