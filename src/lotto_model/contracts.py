from datetime import date

from pydantic import BaseModel, Field, StrictInt, model_validator


class DrawInput(BaseModel):
    game: str = Field(min_length=1)
    draw_date: date
    rule: str = Field(min_length=1)
    pool: StrictInt = Field(ge=7)
    mains: tuple[StrictInt, ...]
    bonus: StrictInt | None = None

    @model_validator(mode="after")
    def valid_numbers(self):
        if len(self.mains) != 6 or len(set(self.mains)) != 6:
            raise ValueError("Six distinct main numbers are required")
        # An unknown bonus stays null; it is never invented.
        bonus = () if self.bonus is None else (self.bonus,)
        if self.bonus in self.mains:
            raise ValueError("Bonus must differ from mains")
        if any(n < 1 or n > self.pool for n in (*self.mains, *bonus)):
            raise ValueError("Numbers must belong to the eligible pool")
        return self
