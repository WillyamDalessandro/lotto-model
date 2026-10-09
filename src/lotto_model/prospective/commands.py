import json
from datetime import date
from functools import wraps
from pathlib import Path

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

app = typer.Typer(help="Prospective pre-result research records (no purchasing).")


def safe_command(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, ValidationError, OSError, SQLAlchemyError, KeyError):
            typer.echo(
                "Prospective command failed; check protocol, rules and database.",
                err=True,
            )
            raise typer.Exit(1) from None

    return guarded


def _engine():
    from lotto_model.config import Settings
    from lotto_model.db import create_engine_from_settings

    return create_engine_from_settings(Settings())


@app.command()
@safe_command
def protocol(path: Path, output_root: Path = Path("data/prospective")):
    """Validate a reviewed protocol against verified rules, freeze and register it."""
    from lotto_model.prospective.issuance import register_protocol
    from lotto_model.prospective.protocol import (
        ProspectiveProtocol,
        freeze_prospective,
    )

    value = ProspectiveProtocol.model_validate_json(path.read_text(encoding="utf8"))
    engine = _engine()
    try:
        with engine.begin() as conn:
            register_protocol(conn, value)
    finally:
        engine.dispose()
    out = freeze_prospective(value, output_root)
    typer.echo(json.dumps(dict(path=str(out), digest=value.digest)))


@app.command("issue")
@safe_command
def issue_command(
    protocol_dir: Path, target_date: str = typer.Option(...), arm: str = "uniform"
):
    """Issue immutable lines for a future scheduled draw before its deadline."""
    from lotto_model.prospective.issuance import issue
    from lotto_model.prospective.protocol import load_prospective

    value = load_prospective(protocol_dir)
    engine = _engine()
    try:
        with engine.begin() as conn:
            result = issue(conn, value, date.fromisoformat(target_date), arm)
    finally:
        engine.dispose()
    typer.echo(
        json.dumps(
            dict(
                status=result.status,
                reason=result.reason,
                lines={str(k): [list(x) for x in v] for k, v in result.lines.items()},
            )
        )
    )


@app.command()
@safe_command
def evaluate(protocol_dir: Path):
    """Score issued lines against accepted results imported via permitted sources."""
    from lotto_model.prospective.evaluation import evaluate_available
    from lotto_model.prospective.protocol import load_prospective

    value = load_prospective(protocol_dir)
    engine = _engine()
    try:
        with engine.begin() as conn:
            counts = evaluate_available(conn, value.digest)
    finally:
        engine.dispose()
    typer.echo(json.dumps(counts))


@app.command()
@safe_command
def report(protocol_dir: Path, output: Path | None = None):
    """Descriptive coverage and completed-issue performance per arm."""
    from lotto_model.prospective.evaluation import prospective_report
    from lotto_model.prospective.protocol import load_prospective

    value = load_prospective(protocol_dir)
    engine = _engine()
    try:
        with engine.connect() as conn:
            result = prospective_report(conn, value)
    finally:
        engine.dispose()
    text = json.dumps(result, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf8")
    else:
        typer.echo(text)
