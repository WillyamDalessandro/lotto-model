import pytest
from conftest import require_test_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://user:secret@localhost/lotto",
        "sqlite:///lotto_test",
        "postgresql+psycopg://user:secret@localhost/lotto_test?dbname=lotto",
        "postgresql+psycopg://user:secret@localhost/lotto_test?service=research",
    ],
)
def test_research_database_refused(url):
    with pytest.raises(ValueError):
        require_test_url(url)
