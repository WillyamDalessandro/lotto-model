"""Deterministic portable bundles and standalone verification (no DB/network)."""

import csv
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath

from lotto_model.audit.contracts import (
    SCHEMA_VERSION,
    AuditRequest,
    AuditResult,
    VerificationResult,
    canonical_json,
    sha256,
)

DRAW_COLUMNS = (
    "game",
    "draw_date",
    "rule_code",
    *(f"main_{i}" for i in range(1, 7)),
    "bonus",
    "observation_key",
)
CONTENT = ("draws.csv", "rules.json", "enrichment.json", "audit.json", "lineage.json")


def _draws_csv(draws) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(DRAW_COLUMNS)
    for draw in sorted(draws, key=lambda d: (d["game"], d["draw_date"])):
        writer.writerow(
            [
                draw["game"],
                draw["draw_date"].isoformat(),
                draw["rule_code"],
                *sorted(draw["mains"]),
                "" if draw["bonus"] is None else draw["bonus"],
                draw["observation_key"],
            ]
        )
    return buffer.getvalue().encode("utf8")


def _rule(rule):
    return dict(
        code=rule["code"],
        starts_on=rule["starts_on"],
        ends_on=rule["ends_on"],
        pool=rule["pool"],
        schedule=sorted(rule["schedule"]),
        evidence_url=rule["evidence_url"],
        binding=rule["binding"],
        verified=rule["verified"],
        binding_matches=rule["binding_matches"],
    )


def build_content(audit: AuditResult, request: AuditRequest) -> dict[str, bytes]:
    """Serialize content files; no IDs, run IDs, host paths or current times."""
    if audit.blocking:
        raise ValueError("Audit has blocking conditions: " + ", ".join(audit.blocking))
    files = {
        "draws.csv": _draws_csv(audit.eligible),
        "rules.json": canonical_json(
            sorted((_rule(r) for r in audit.rules), key=lambda r: r["code"])
        ),
        "enrichment.json": canonical_json(
            dict(
                records=sorted(
                    audit.enrichment,
                    key=lambda e: (e["draw_date"], e["kind"], e["tier"]),
                ),
                omitted=dict(sorted(audit.enrichment_omitted.items())),
                summary_policy=(
                    "disputed records are excluded from totals; null is unknown"
                ),
            )
        ),
        "audit.json": canonical_json(
            dict(
                request=request.model_dump(mode="json"),
                counts=audit.counts,
                exclusions=audit.exclusions,
                issues=audit.issues,
                schedule=audit.schedule,
                warnings=sorted(audit.warnings),
            )
        ),
        "lineage.json": canonical_json(
            dict(
                observations=sorted(
                    audit.observations, key=lambda o: o["observation_key"]
                ),
                rule_bindings=sorted(
                    (r["binding"] for r in audit.rules if r["binding"]),
                    key=lambda b: b["rule_code"],
                ),
                calendar_events=audit.events,
            )
        ),
    }
    for digest, body in sorted(audit.evidence.items()):
        files[f"evidence/{digest}.body"] = body
    return files


def content_digest(files: dict[str, bytes]) -> str:
    listing = {
        path: sha256(body) for path, body in files.items() if path != "manifest.json"
    }
    return sha256(canonical_json(listing))


def build_manifest(
    files: dict[str, bytes],
    request: AuditRequest,
    included: int,
    source_revision: str,
    extracted_at: datetime | None = None,
) -> bytes:
    return canonical_json(
        dict(
            schema_version=SCHEMA_VERSION,
            game=request.game,
            start=request.start,
            end=request.end,
            included_draws=included,
            files={
                p: dict(sha256=sha256(b), size=len(b)) for p, b in sorted(files.items())
            },
            content_sha256=content_digest(files),
            source_revision=source_revision,
            extracted_at=extracted_at or datetime.now(timezone.utc),
        )
    )


def _safe(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        bool(path)
        and "\\" not in path
        and not pure.is_absolute()
        and ".." not in pure.parts
        and str(pure) == path
        and (
            path in CONTENT or (pure.parent.name == "evidence" and len(pure.parts) == 2)
        )
    )


def _files(root: Path) -> dict[str, bytes]:
    found = {}
    for item in root.rglob("*"):
        if item.is_symlink():
            raise ValueError("Bundle contains a symlink")
        if item.is_dir():
            continue
        found[item.relative_to(root).as_posix()] = item.read_bytes()
    return found


def verify_files(files: dict[str, bytes]) -> VerificationResult:
    """Independently recheck hashes, counts, eligibility and lineage."""
    try:
        manifest = json.loads(files.pop("manifest.json"))
    except (KeyError, ValueError):
        raise ValueError("Manifest missing or unreadable") from None
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("game") != "lotto"
    ):
        raise ValueError("Unsupported bundle schema or game")
    listed = manifest.get("files")
    if not isinstance(listed, dict) or not all(_safe(p) for p in listed):
        raise ValueError("Unsafe or malformed manifest paths")
    if set(listed) != set(files) or not set(CONTENT) <= set(files):
        raise ValueError("Bundle files differ from manifest")
    for path, meta in listed.items():
        if meta != dict(sha256=sha256(files[path]), size=len(files[path])):
            raise ValueError(f"Hash or size mismatch: {path}")
        if (
            path.startswith("evidence/")
            and path != f"evidence/{sha256(files[path])}.body"
        ):
            raise ValueError("Evidence name differs from its hash")
    digest = content_digest(files)
    if manifest.get("content_sha256") != digest:
        raise ValueError("Content digest mismatch")

    try:
        rules = {r["code"]: r for r in json.loads(files["rules.json"])}
        lineage = json.loads(files["lineage.json"])
        audit = json.loads(files["audit.json"])
        rows = list(
            csv.reader(io.StringIO(files["draws.csv"].decode("utf8"), newline=""))
        )
    except (ValueError, KeyError, TypeError):
        raise ValueError("Unreadable bundle content") from None
    if not rows or tuple(rows[0]) != DRAW_COLUMNS:
        raise ValueError("Unexpected draw columns")
    observations = {o["observation_key"]: o for o in lineage["observations"]}
    evidence = {
        p[len("evidence/") : -len(".body")] for p in files if p.startswith("evidence/")
    }
    previous = None
    for row in rows[1:]:
        if len(row) != len(DRAW_COLUMNS):
            raise ValueError("Malformed draw row")
        record = dict(zip(DRAW_COLUMNS, row))
        try:
            day = date.fromisoformat(record["draw_date"])
            mains = [int(record[f"main_{i}"]) for i in range(1, 7)]
            bonus = int(record["bonus"]) if record["bonus"] else None
        except ValueError:
            raise ValueError("Invalid draw values") from None
        rule = rules.get(record["rule_code"])
        if (
            record["game"] != "lotto"
            or (previous is not None and day <= previous)
            or rule is None
            or not rule["verified"]
            or not rule["binding_matches"]
            or rule["binding"]["artifact_sha256"] not in evidence
            or date.fromisoformat(rule["starts_on"]) > day
            or (rule["ends_on"] and date.fromisoformat(rule["ends_on"]) < day)
            or mains != sorted(set(mains))
            or len(mains) != 6
            or any(not 1 <= n <= rule["pool"] for n in mains)
            or (
                bonus is not None and (bonus in mains or not 1 <= bonus <= rule["pool"])
            )
        ):
            raise ValueError(f"Ineligible draw in bundle: {record['draw_date']}")
        observed = observations.get(record["observation_key"])
        if (
            observed is None
            or observed["artifact_sha256"] not in evidence
            or observed["payload"].get("draw_date") != record["draw_date"]
            or sorted(observed["payload"].get("mains") or []) != mains
        ):
            raise ValueError(f"Draw lacks verified lineage: {record['draw_date']}")
        previous = day
    count = len(rows) - 1
    if (
        not count
        or count != manifest.get("included_draws")
        or count != audit["counts"]["included"]
    ):
        raise ValueError("Draw count mismatch")
    return VerificationResult(content_sha256=digest, included_draws=count)


def verify_bundle(path: Path) -> VerificationResult:
    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Bundle directory missing")
    return verify_files(_files(root))
