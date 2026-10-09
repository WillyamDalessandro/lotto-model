"""Atomic bundle publication and the snapshot registry (the sole DB write)."""

import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import text

from lotto_model.audit.bundle import (
    build_content,
    build_manifest,
    content_digest,
    verify_bundle,
)
from lotto_model.audit.contracts import (
    SCHEMA_VERSION,
    AuditRequest,
    RuleBindings,
    SnapshotResult,
)
from lotto_model.audit.eligibility import audit_inputs
from lotto_model.audit.reader import read_inputs


def _write(root: Path, files: dict[str, bytes]):
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())


def publish_bundle(
    files: dict[str, bytes], manifest: bytes, output_root: Path, included: int
) -> SnapshotResult:
    """Write to a temporary sibling, verify, then rename; never overwrite."""
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    digest = content_digest(files)
    final = output_root / digest
    if final.exists():
        verified = verify_bundle(final)
        if verified.content_sha256 != digest:
            raise ValueError("Existing bundle content differs from its name")
        return SnapshotResult(final, digest, verified.included_draws)
    temporary = output_root / f".tmp-{digest}-{uuid.uuid4().hex}"
    try:
        _write(temporary, {**files, "manifest.json": manifest})
        verified = verify_bundle(temporary)
        if verified.content_sha256 != digest or verified.included_draws != included:
            raise ValueError("Written bundle failed verification")
        temporary.rename(final)
    except BaseException:
        if temporary.exists() and temporary.parent == output_root:
            shutil.rmtree(temporary)
        if final.exists():
            # A concurrent writer won the rename; accept only verified content.
            verified = verify_bundle(final)
            return SnapshotResult(final, digest, verified.included_draws)
        raise
    return SnapshotResult(final, digest, verified.included_draws)


def register_snapshot(connection, result: SnapshotResult, request: AuditRequest) -> int:
    """Insert-or-return; the first creation time and path are preserved."""
    verified = verify_bundle(result.path)
    if verified.content_sha256 != result.content_sha256:
        raise ValueError("Bundle digest differs from registration request")
    connection.execute(
        text(
            """INSERT INTO dataset_snapshots(content_sha256,schema_version,game,
            starts_on,ends_on,included_draws,manifest_path)
            VALUES(:h,:v,:g,:s,:e,:n,:p) ON CONFLICT(content_sha256) DO NOTHING"""
        ),
        dict(
            h=result.content_sha256,
            v=SCHEMA_VERSION,
            g=request.game,
            s=request.start,
            e=request.end,
            n=verified.included_draws,
            p=str(Path(result.path) / "manifest.json"),
        ),
    )
    return connection.scalar(
        text("SELECT id FROM dataset_snapshots WHERE content_sha256=:h"),
        dict(h=result.content_sha256),
    )


def audit_connection(engine):
    """Open a REPEATABLE READ connection so every audit query shares one view."""
    return engine.connect().execution_options(isolation_level="REPEATABLE READ")


def create_snapshot(
    engine,
    request: AuditRequest,
    evidence_root: Path,
    bindings: RuleBindings,
    output_root: Path,
    source_revision: str,
) -> SnapshotResult:
    with audit_connection(engine) as connection:
        with connection.begin():
            audit = audit_inputs(
                read_inputs(connection, request, evidence_root, bindings), request
            )
            files = build_content(audit, request)
            manifest = build_manifest(
                files, request, len(audit.eligible), source_revision
            )
            result = publish_bundle(files, manifest, output_root, len(audit.eligible))
            register_snapshot(connection, result, request)
    return result
