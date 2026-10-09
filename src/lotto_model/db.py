from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from lotto_model.config import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
        hide_parameters=True,
    )
