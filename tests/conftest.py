import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def require_test_url(url):
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg" or not (
        parsed.database and parsed.database.endswith("_test")
    ):
        raise ValueError("Integration tests require a PostgreSQL database ending _test")
    return url


@pytest.fixture(scope="session")
def test_url():
    load_dotenv()
    url = os.environ.get("LOTTO_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set LOTTO_TEST_DATABASE_URL; integration tests are mandatory")
    return require_test_url(url)


@pytest.fixture(scope="session")
def migration_config(test_url):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = test_url
    return config


@pytest.fixture(scope="session")
def db_engine(migration_config, test_url):
    command.upgrade(migration_config, "head")
    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(db_engine):
    with db_engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()
