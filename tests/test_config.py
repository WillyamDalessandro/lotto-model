import pytest
from pydantic import ValidationError

from lotto_model.config import Settings


def test_missing_url(monkeypatch):
    monkeypatch.delenv("LOTTO_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url", ["sqlite:///data.db", "not-a-url", "postgresql+psycopg://"]
)
def test_invalid_url(url):
    with pytest.raises(ValidationError):
        Settings(database_url=url, _env_file=None)


def test_env_url(monkeypatch):
    url = "postgresql+psycopg://user:secret@localhost:5432/lotto"
    monkeypatch.setenv("LOTTO_DATABASE_URL", url)
    settings = Settings(_env_file=None)
    assert settings.database_url.get_secret_value() == url
    assert "secret" not in repr(settings)
