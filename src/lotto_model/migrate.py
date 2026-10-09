from pathlib import Path

from alembic import command
from alembic.config import Config

from lotto_model.config import Settings


def upgrade_database(settings: Settings) -> None:
    """Upgrade a source checkout's schema without embedding credentials in INI."""
    root = Path(__file__).resolve().parents[2]
    if not (root / "alembic.ini").is_file():
        raise RuntimeError("Run migrations from an editable source checkout")
    config = Config(str(root / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url.get_secret_value()
    command.upgrade(config, "head")
