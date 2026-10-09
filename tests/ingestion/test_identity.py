import pytest

from lotto_model.ingestion.contracts import Artifact, Observation
from lotto_model.ingestion.workflows import parse_saved


@pytest.mark.parametrize(
    "url", ["garbage", "ftp://example.test/a", "https://user:secret@example.test/a"]
)
def test_invalid_observation_identity(url):
    with pytest.raises(ValueError):
        Observation(draw_date="2026-10-07", mains=[1, 2, 3, 4, 5, 6], source_url=url)


def test_invalid_blocked_artifact_identity():
    with pytest.raises(ValueError):
        Artifact(
            url="garbage",
            final_url="garbage",
            retrieved_at="2026-10-09T00:00:00Z",
            http_status=403,
            content_type=None,
            sha256="a" * 64,
            body_path="a.body",
            status="blocked",
        )


def test_file_identity_is_supported():
    row = Observation(
        draw_date="2026-10-07",
        mains=[1, 2, 3, 4, 5, 6],
        source_url="file:///C:/exports/lotto.csv",
    )
    assert row.source_url.startswith("file:")


def test_auto_adapter_rejects_unrecognized_source_path():
    with pytest.raises(ValueError):
        parse_saved(b"", "https://www.lottery.ie/play?game=lotto", "auto")
