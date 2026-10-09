import json
from datetime import date
from functools import wraps
from pathlib import Path

import httpx
import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from lotto_model.config import Settings
from lotto_model.db import create_engine_from_settings
from lotto_model.ingestion.complementary import (
    ComplementaryRecord,
    ingest_complementary,
)
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.fetch import RESTRICTED
from lotto_model.ingestion.official import collect_official
from lotto_model.ingestion.report import coverage
from lotto_model.ingestion.repository import Repository
from lotto_model.ingestion.workflows import import_manifest

app = typer.Typer(
    help="Evidence-backed data acquisition, offline imports and coverage."
)


def safe_command(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (
            ValueError,
            OSError,
            SQLAlchemyError,
            httpx.HTTPError,
            KeyError,
            IndexError,
        ):
            typer.echo(
                "Data command failed; check inputs, saved evidence and database.",
                err=True,
            )
            raise typer.Exit(1) from None

    return guarded


@app.command()
@safe_command
def prepare(path: Path, root: Path = Path("data/raw")):
    """Preserve a local CSV as evidence and print its import manifest path."""
    from lotto_model.ingestion.workflows import parse_csv

    body = path.read_bytes()
    url = path.resolve().as_uri()
    parse_csv(body, url)
    store = EvidenceStore(root)
    store.write(
        body, url=url, http_status=None, content_type="text/csv", status="valid"
    )
    typer.echo(str(store.manifest))


@app.command()
@safe_command
def official(root: Path = Path("data/raw/official")):
    """Collect reviewed open government report evidence and annual metrics."""
    store = EvidenceStore(root)
    try:
        records = collect_official(store)
        engine = create_engine_from_settings(Settings())
        try:
            with engine.begin() as conn:
                repo = Repository(conn)
                run = repo.start_run({"dataset": "official_period_metrics"})
                for record, artifact in records:
                    identifier = repo.record_artifact(
                        artifact,
                        run,
                        "official:cag",
                        "independent",
                        evidence_root=store.root,
                    )
                    ingest_complementary(repo, record, identifier)
                    repo.checkpoint(artifact, identifier, run, "parsed")
                repo.finish_run(run, "completed")
            typer.echo(f"Imported {len(records)} official annual metrics")
        finally:
            engine.dispose()
    except (ValueError, OSError, SQLAlchemyError):
        typer.echo(
            "Official collection failed; inspect saved evidence and policy.", err=True
        )
        raise typer.Exit(1) from None


@app.command()
@safe_command
def discover():
    """Report reviewed source access limits without harvesting restricted sites."""
    typer.echo(
        json.dumps(
            {
                "sources": RESTRICTED,
                "historical_backfill": (
                    "Requires a permissible export or provider permission"
                ),
            },
            indent=2,
        )
    )


@app.command()
@safe_command
def calendar(start: str, end: str):
    """Build dates from reviewed rules; unknown schedules stay nullable."""
    from lotto_model.ingestion.calendar import materialize_calendar

    engine = create_engine_from_settings(Settings())
    try:
        with engine.begin() as conn:
            count = materialize_calendar(
                conn, date.fromisoformat(start), date.fromisoformat(end)
            )
        typer.echo(f"Materialized {count} calendar dates")
    finally:
        engine.dispose()


@app.command("import")
@safe_command
def import_data(manifest: Path, adapter: str = "auto", root: Path = Path("data/raw")):
    """Verify and ingest a saved evidence manifest; no network requests."""
    engine = create_engine_from_settings(Settings())
    try:
        result = import_manifest(engine, manifest, EvidenceStore(root), adapter)
        typer.echo(json.dumps(result))
    except (ValueError, OSError, ValidationError, SQLAlchemyError):
        typer.echo(
            "Import failed; check evidence, adapter and database. "
            "No credentials displayed.",
            err=True,
        )
        raise typer.Exit(1) from None
    finally:
        engine.dispose()


@app.command()
@safe_command
def report(output: Path | None = None):
    """Report actual coverage, issues and derived context."""
    engine = create_engine_from_settings(Settings())
    try:
        value = json.dumps(coverage(engine), default=str, indent=2)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(value, encoding="utf8")
        else:
            typer.echo(value)
    finally:
        engine.dispose()


@app.command()
@safe_command
def collect(start_year: int = 1988, end_year: int = 2026, max_requests: int = 100):
    """Report why the planned archive backfill cannot run under current policies."""
    if not 1988 <= start_year <= end_year <= date.today().year or max_requests < 1:
        raise typer.BadParameter("Invalid year range or request budget")
    typer.echo(
        "Historical collection is unavailable: reviewed archives prohibit "
        "harvesting. Import a permissible saved export with `lotto data import`.",
        err=True,
    )
    raise typer.Exit(2)


@app.command()
@safe_command
def enrich(manifest: Path, records: Path):
    """Import curated complementary records tied to saved evidence artifacts."""
    store = EvidenceStore(manifest.parent)
    artifacts = store.load_manifest(manifest)
    definitions = json.loads(records.read_text(encoding="utf8"))
    # Validate every record and artifact index before mutation.
    parsed = [
        (
            ComplementaryRecord.model_validate(r["record"]),
            artifacts[r["artifact_index"]],
        )
        for r in definitions
    ]
    if any(a.status != "valid" for _, a in parsed):
        raise typer.BadParameter("Complementary records require valid evidence")
    engine = create_engine_from_settings(Settings())
    try:
        with engine.begin() as conn:
            repo = Repository(conn)
            run = repo.start_run({"complementary": str(records)})
            for record, artifact in parsed:
                identifier = repo.record_artifact(
                    artifact,
                    run,
                    "curated:" + artifact.url,
                    "manual",
                    evidence_root=store.root,
                )
                ingest_complementary(repo, record, identifier)
            repo.finish_run(run, "completed")
        typer.echo(f"Imported {len(parsed)} complementary records")
    finally:
        engine.dispose()


@app.command()
@safe_command
def rules(manifest: Path, records: Path):
    """Register reviewed modern rule intervals supported by saved evidence."""
    artifacts = EvidenceStore(manifest.parent).load_manifest(manifest)
    definitions = json.loads(records.read_text(encoding="utf8"))
    engine = create_engine_from_settings(Settings())
    try:
        with engine.begin() as conn:
            repo = Repository(conn)
            run = repo.start_run({"rules": str(records)})
            for definition in definitions:
                artifact = artifacts[definition["artifact_index"]]
                if artifact.status != "valid":
                    raise ValueError("Rule requires valid evidence")
                identifier = repo.record_artifact(
                    artifact,
                    run,
                    "rules:" + artifact.url,
                    "manual",
                    evidence_root=manifest.parent.resolve(),
                )
                repo.add_rule(
                    definition["code"],
                    date.fromisoformat(definition["starts_on"]),
                    date.fromisoformat(definition["ends_on"])
                    if definition.get("ends_on")
                    else None,
                    definition["pool"],
                    definition["schedule"],
                    identifier,
                )
            repo.finish_run(run, "completed")
        typer.echo(f"Registered {len(definitions)} rule intervals")
    finally:
        engine.dispose()


@app.command()
@safe_command
def batch(batch_path: Path, receipt: Path | None = None, root: Path = Path("data/raw")):
    """Apply a reviewed offline acquisition batch in one transaction."""
    from lotto_model.ingestion.batch import run_batch

    engine = create_engine_from_settings(Settings())
    try:
        result = run_batch(engine, batch_path, receipt, root)
    except ValidationError:
        raise ValueError("Invalid batch") from None
    finally:
        engine.dispose()
    summary = {k: result[k] for k in ("digest", "counts", "status")}
    if "receipt_error" in result:
        summary["receipt_error"] = result["receipt_error"]
    typer.echo(json.dumps(summary, sort_keys=True))


@app.command("acquisition-status")
@safe_command
def acquisition_status_command(output: Path | None = None):
    """Report measured acquisition availability and outstanding mandatory inputs."""
    from lotto_model.ingestion.report import acquisition_status

    engine = create_engine_from_settings(Settings())
    try:
        with engine.connect() as conn:
            value = json.dumps(acquisition_status(conn), default=str, indent=2)
    finally:
        engine.dispose()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(value + "\n", encoding="utf8")
    else:
        typer.echo(value)
