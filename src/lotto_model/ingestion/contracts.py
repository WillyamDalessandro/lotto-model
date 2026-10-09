from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, StrictInt, model_validator


def validate_source_url(value):
    parsed = urlparse(value)
    if any(c.isspace() for c in value) or parsed.username or parsed.password:
        raise ValueError("Invalid evidence source identity")
    if parsed.scheme in ("http", "https") and parsed.hostname:
        return value
    if (
        parsed.scheme == "file"
        and parsed.netloc in ("", "localhost")
        and parsed.path.startswith("/")
        and len(parsed.path) > 1
    ):
        return value
    raise ValueError("Evidence requires an HTTP(S) URL or absolute local file URI")


class PrizeObservation(BaseModel):
    tier: str
    winners: StrictInt | None = Field(default=None, ge=0)
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    original_text: str
    prize_type: str = "unresolved"


class Observation(BaseModel):
    game: Literal["lotto"] = "lotto"
    draw_date: date
    mains: tuple[StrictInt, ...]
    bonus: StrictInt | None = None
    source_url: str
    jackpot: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    outcome: Literal["Won", "Roll"] | None = None
    prizes: list[PrizeObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid(self):
        validate_source_url(self.source_url)
        numbers = (*self.mains, *((self.bonus,) if self.bonus is not None else ()))
        if len(self.mains) != 6 or len(set(numbers)) != len(numbers):
            raise ValueError("Six unique mains and a distinct optional bonus required")
        if any(n < 1 or n > 99 for n in numbers):
            raise ValueError("Invalid observed number")
        self.mains = tuple(sorted(self.mains))
        if len({p.tier for p in self.prizes}) != len(self.prizes):
            raise ValueError("Duplicate prize tiers")
        return self


class Artifact(BaseModel):
    url: str
    final_url: str
    retrieved_at: datetime
    http_status: int | None
    content_type: str | None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_path: str
    status: Literal["valid", "blocked", "invalid", "error"]

    @model_validator(mode="after")
    def identity(self):
        validate_source_url(self.url)
        validate_source_url(self.final_url)
        if self.retrieved_at.tzinfo is None:
            raise ValueError("Retrieval time requires a timezone")
        return self
