import json
import subprocess
from datetime import date
from functools import wraps
from pathlib import Path

import typer
from sqlalchemy.exc import SQLAlchemyError

from lotto_model.audit.bundle import verify_bundle
from lotto_model.audit.contracts import AuditRequest, RuleBindings, canonical_json

app = typer.Typer(help="Audit canonical draws and build verified snapshots.")


def safe_command(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, OSError, SQLAlchemyError, KeyError, TypeError):
            typer.echo(
                "Audit command failed; check dates, bindings, evidence and database.",
                err=True,
            )
            raise typer.Exit(1) from None

    return guarded


def _request(start: str, end: str) -> AuditRequest:
    return AuditRequest(start=date.fromisoformat(start), end=date.fromisoformat(end))


def _bindings(path: Path | None) -> RuleBindings | None:
    if path is None:
        return None
    return RuleBindings.model_validate_json(path.read_text(encoding="utf8"))


def source_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _engine():
    from lotto_model.config import Settings
    from lotto_model.db import create_engine_from_settings

    return create_engine_from_settings(Settings())


@app.command()
@safe_command
def report(
    start: str = typer.Option(...),
    end: str = typer.Option(...),
    evidence_root: Path = typer.Option(...),
    bindings: Path | None = None,
    output: Path | None = None,
):
    """Audit JSON; never writes canonical data or the registry."""
    from lotto_model.audit.eligibility import audit_inputs
    from lotto_model.audit.reader import read_inputs
    from lotto_model.audit.registry import audit_connection

    request = _request(start, end)
    engine = _engine()
    try:
        with audit_connection(engine) as connection, connection.begin():
            audit = audit_inputs(
                read_inputs(connection, request, evidence_root, _bindings(bindings)),
                request,
            )
    finally:
        engine.dispose()
    value = json.loads(
        canonical_json(
            dict(
                request=request.model_dump(mode="json"),
                counts=audit.counts,
                exclusions=audit.exclusions,
                issues=audit.issues,
                schedule=audit.schedule,
                warnings=audit.warnings,
                blocking=audit.blocking,
                rules=[
                    {k: r[k] for k in ("code", "verified", "binding_matches")}
                    for r in audit.rules
                ],
                enrichment_omitted=audit.enrichment_omitted,
                snapshot_ready=not audit.blocking,
            )
        )
    )
    text = json.dumps(value, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf8")
    else:
        typer.echo(text)


@app.command()
@safe_command
def snapshot(
    start: str = typer.Option(...),
    end: str = typer.Option(...),
    evidence_root: Path = typer.Option(...),
    bindings: Path = typer.Option(...),
    output_root: Path = Path("data/snapshots"),
):
    """Create, verify and register an immutable audited bundle."""
    from lotto_model.audit.registry import create_snapshot

    request = _request(start, end)
    engine = _engine()
    try:
        result = create_snapshot(
            engine,
            request,
            evidence_root,
            _bindings(bindings),
            output_root,
            source_revision(),
        )
    finally:
        engine.dispose()
    typer.echo(
        json.dumps(
            dict(
                path=str(result.path),
                content_sha256=result.content_sha256,
                included_draws=result.included_draws,
            )
        )
    )


@app.command()
@safe_command
def verify(path: Path):
    """Verify a bundle offline: no database or network access."""
    result = verify_bundle(path)
    typer.echo(
        json.dumps(
            dict(
                content_sha256=result.content_sha256,
                included_draws=result.included_draws,
            )
        )
    )
