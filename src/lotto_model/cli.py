import typer
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from lotto_model.audit.commands import app as audit_app
from lotto_model.config import Settings
from lotto_model.db import create_engine_from_settings
from lotto_model.ingestion.commands import app as data_app
from lotto_model.migrate import upgrade_database
from lotto_model.research.commands import app as research_app

app = typer.Typer(help="Irish Lotto research tools.")
db = typer.Typer(help="Database operations.")
app.add_typer(db, name="db")
app.add_typer(data_app, name="data")
app.add_typer(audit_app, name="audit")
app.add_typer(research_app, name="research")


@db.command()
def health():
    """Check database connectivity without displaying credentials."""
    engine = None
    try:
        engine = create_engine_from_settings(Settings())
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    except (ValidationError, SQLAlchemyError):
        typer.echo("Database unavailable; check configuration and service.", err=True)
        raise typer.Exit(1) from None
    finally:
        if engine is not None:
            engine.dispose()
    typer.echo("Database healthy")


@db.command()
def migrate():
    """Apply versioned schema migrations to the configured database."""
    try:
        upgrade_database(Settings())
    except (ValidationError, SQLAlchemyError, RuntimeError):
        typer.echo("Migration failed; check configuration and database.", err=True)
        raise typer.Exit(1) from None
    typer.echo("Database migrated to head")
