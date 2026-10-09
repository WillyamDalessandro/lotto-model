from datetime import date

import pytest
from pydantic import ValidationError

from lotto_model.contracts import DrawInput


def draw(**changes):
    return DrawInput(
        **dict(
            game="lotto",
            draw_date=date(2026, 10, 7),
            rule="6/45",
            pool=45,
            mains=[1, 2, 3, 4, 5, 6],
            bonus=7,
        )
        | changes
    )


@pytest.mark.parametrize("pool", [45, 47])
def test_valid_draw(pool):
    assert draw(pool=pool).mains == (1, 2, 3, 4, 5, 6)


@pytest.mark.parametrize(
    "changes",
    [
        {"mains": [1, 2, 3, 4, 5]},
        {"mains": [1, 2, 3, 4, 5, 6, 7]},
        {"mains": [1, 1, 2, 3, 4, 5]},
        {"bonus": 6},
        {"bonus": 46},
        {"mains": [0, 2, 3, 4, 5, 6]},
        {"mains": [1, 2, 3, 4, 5, 46]},
        {"mains": [1, 2, 3, 4, 5, 6.5]},
        {"bonus": True},
    ],
)
def test_invalid_draw(changes):
    with pytest.raises(ValidationError):
        draw(**changes)
