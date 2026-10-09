import pytest
from conftest import require_test_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://user:secret@localhost/lotto",
        "sqlite:///lotto_test",
    ],
)
def test_research_database_refused(url):
    with pytest.raises(ValueError):
        require_test_url(url)
