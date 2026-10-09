import typer
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from lotto_model.config import Settings
from lotto_model.db import create_engine_from_settings

app = typer.Typer(help="Irish Lotto research tools.")
db = typer.Typer(help="Database operations.")
app.add_typer(db, name="db")


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
