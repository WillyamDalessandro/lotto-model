import pytest
from pydantic import ValidationError

from lotto_model.ingestion.complementary import ComplementaryRecord


def test_period_scope_and_unknown_publication_retained():
    record = ComplementaryRecord(
        dataset="official_period_metrics",
        record_key="sales",
        payload=dict(
            period_start="2021-01-01",
            period_end="2021-12-31",
            game_scope="all_games",
            metric="sales",
            value="1",
            unit="EUR",
        ),
    )
    assert record.published_at is None
    assert record.payload["game_scope"] == "all_games"


@pytest.mark.parametrize(
    "payload",
    [
        dict(
            effective_from="2026-10-01",
            effective_to="2026-01-01",
            attribute="price",
            value=2,
        ),
    ],
)
def test_invalid_effective_interval(payload):
    with pytest.raises(ValidationError):
        ComplementaryRecord(
            dataset="rule_attributes", record_key="price", payload=payload
        )


def test_ticket_location_semantics_required():
    with pytest.raises(ValidationError):
        ComplementaryRecord(
            dataset="winning_ticket_reports",
            record_key="ticket",
            payload=dict(
                draw_date="2026-10-07",
                channel="online",
                location_meaning="retailer_address",
            ),
        )


def test_private_identity_rejected():
    with pytest.raises(ValidationError):
        ComplementaryRecord(
            dataset="winning_ticket_reports",
            record_key="ticket",
            payload=dict(
                draw_date="2026-10-07",
                channel="retail",
                location_meaning="purchase_county",
                person_name="Someone",
            ),
        )
