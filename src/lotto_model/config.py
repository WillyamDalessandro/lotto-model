from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOTTO_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def postgres_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and url.host
                and url.database
                and url.username
            )
            if not valid:
                raise ValueError
        except (ValueError, ArgumentError) as exc:
            raise ValueError("A complete PostgreSQL psycopg URL is required") from exc
        return value
