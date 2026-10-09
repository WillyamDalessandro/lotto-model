from datetime import date, datetime, time, timezone

import pytest
from pydantic import ValidationError

from lotto_model.prospective.protocol import (
    ProspectiveProtocol,
    freeze_prospective,
    load_prospective,
    validate_protocol,
)

HASH = "a" * 64


def make(**changes):
    return ProspectiveProtocol(
        **dict(
            start_date=date(2026, 10, 12),
            rule_code="6/45",
            pool=45,
            schedule=(0, 2, 5),
            rule_evidence_sha256=HASH,
            schedule_evidence_sha256=HASH,
            deadline_local_time=time(19, 45),
            deadline_timezone="Europe/Dublin",
            deadline_evidence="reviewed operator sales-close notice",
            arms=[dict(id="uniform", policy="uniform", budgets=[1, 5, 10])],
            result_source_policy="permitted saved exports via lotto data batch",
        )
        | changes
    )


RULE = dict(
    code="6/45",
    starts_on=date(2026, 9, 5),
    ends_on=None,
    pool=45,
    schedule=[0, 2, 5],
    evidence_sha256=[HASH],
)


def test_current_rule_contract():
    assert validate_protocol(make(), [RULE])
    for rules in (
        [],
        [RULE | {"pool": 47}],
        [RULE | {"schedule": [2, 5]}],
        [RULE | {"evidence_sha256": []}],
        [RULE | {"ends_on": date(2026, 10, 1)}],
        [RULE | {"starts_on": date(2026, 11, 1)}],
    ):
        with pytest.raises(ValueError):
            validate_protocol(make(), rules)
    for changes in (
        dict(schedule=()),
        dict(deadline_timezone="Mars/Olympus"),
        dict(deadline_overrides={date(2026, 10, 12): datetime(2026, 10, 12, 19)}),
        dict(arms=[dict(id="model", policy="model", experimental=True)]),
        dict(
            arms=[
                dict(
                    id="model",
                    policy="model",
                    model_contract=dict(
                        frozen={}, rule_code="6/45", pool=45, reviewed=True
                    ),
                )
            ]
        ),
        dict(
            arms=[
                dict(
                    id="model",
                    policy="model",
                    experimental=True,
                    model_contract=dict(
                        frozen={}, rule_code="6/47", pool=47, reviewed=True
                    ),
                )
            ]
        ),
        dict(arms=[]),
    ):
        with pytest.raises(ValidationError):
            make(**changes)


def test_deadlines_are_explicit_and_dst_aware():
    protocol = make()
    summer = protocol.deadline(date(2026, 10, 24))
    winter = protocol.deadline(date(2026, 10, 26))
    assert summer.astimezone(timezone.utc).hour == 18
    assert winter.astimezone(timezone.utc).hour == 19
    override = datetime(2026, 12, 24, 12, tzinfo=timezone.utc)
    assert (
        make(deadline_overrides={date(2026, 12, 24): override}).deadline(
            date(2026, 12, 24)
        )
        == override
    )


def test_protocol_revision(tmp_path):
    protocol = make()
    path = freeze_prospective(protocol, tmp_path)
    assert freeze_prospective(make(), tmp_path) == path
    assert load_prospective(path) == protocol
    revised = make(arms=[dict(id="uniform", policy="uniform", budgets=[1])])
    assert revised.digest != protocol.digest
    (path / "protocol.json").write_text("{}")
    with pytest.raises((ValueError, ValidationError)):
        load_prospective(path)
