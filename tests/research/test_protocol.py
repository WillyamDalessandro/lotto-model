import json

import pytest

from lotto_model.research.protocol import (
    build_protocol,
    freeze_protocol,
    load_population,
    load_protocol,
    verified_population,
)

DIGEST = "a" * 64


def test_split_boundaries(research_draws):
    protocol = build_protocol(research_draws(282), DIGEST)
    assert protocol.development == (0, 225) and protocol.holdout == (225, 282)
    assert [(f.start, f.end) for f in protocol.folds] == [(175, 200), (200, 225)]
    with pytest.raises(ValueError, match="insufficient_data"):
        build_protocol(research_draws(281), DIGEST)
    assert build_protocol(research_draws(283), DIGEST).holdout == (226, 283)
    assert build_protocol(research_draws(283), DIGEST).holdout[1] - 226 == 57
    partial = build_protocol(research_draws(300), DIGEST)
    assert [(f.start, f.end) for f in partial.folds] == [
        (175, 200),
        (200, 225),
        (225, 240),
    ]
    short = build_protocol(research_draws(290), DIGEST)
    assert [(f.start, f.end) for f in short.folds] == [(175, 200), (200, 225)]


def test_mixed_regimes_fail(research_draws):
    from dataclasses import replace

    draws = research_draws(300)
    draws[-1] = replace(draws[-1], rule_code="6/45", pool=45)
    with pytest.raises(ValueError, match="regime"):
        build_protocol(draws, DIGEST)


def test_population_from_verified_snapshot(synthetic_snapshot):
    result = synthetic_snapshot(290, drop=(10,))
    draws = load_population(result.path, "6/47")
    assert len(draws) == 290
    assert [d.gap_before for d in draws].count(True) == 1 and draws[10].gap_before
    protocol = build_protocol(draws, result.content_sha256)
    assert verified_population(protocol, result.path) == draws
    with pytest.raises(ValueError):
        load_population(result.path, "unknown")
    (result.path / "draws.csv").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        load_population(result.path, "6/47")


def test_protocol_immutability(research_draws, tmp_path):
    draws = research_draws(282)
    protocol = build_protocol(draws, DIGEST)
    path = freeze_protocol(protocol, tmp_path)
    assert path.name == protocol.digest
    assert freeze_protocol(build_protocol(draws, DIGEST), tmp_path) == path
    assert load_protocol(path) == protocol
    other = build_protocol(draws, DIGEST, root_seed=1)
    assert other.digest != protocol.digest
    assert build_protocol(draws, "b" * 64).digest != protocol.digest
    data = json.loads((path / "protocol.json").read_text())
    data["simulations"] = 5
    (path / "protocol.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_protocol(path)
    with pytest.raises(ValueError):
        freeze_protocol(protocol, tmp_path)
