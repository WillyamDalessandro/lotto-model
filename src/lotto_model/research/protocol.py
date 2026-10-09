"""Verified populations and immutable chronological protocols."""

import csv
import io
import json
import os
import uuid
from datetime import date
from pathlib import Path

from lotto_model.audit.bundle import verify_bundle
from lotto_model.audit.contracts import canonical_json
from lotto_model.research.contracts import Fold, Protocol, ResearchDraw


def load_population(snapshot: Path, rule_code: str) -> list[ResearchDraw]:
    """Verify the bundle first, then read one regime in chronological order."""
    snapshot = Path(snapshot)
    verify_bundle(snapshot)
    rules = {
        r["code"]: r for r in json.loads((snapshot / "rules.json").read_text("utf8"))
    }
    if rule_code not in rules:
        raise ValueError("Rule code absent from snapshot")
    pool = rules[rule_code]["pool"]
    audit = json.loads((snapshot / "audit.json").read_text("utf8"))
    missing = sorted(date.fromisoformat(d) for d in audit["schedule"]["missing_dates"])
    rows = csv.DictReader(io.StringIO((snapshot / "draws.csv").read_text("utf8")))
    draws, previous = [], None
    for row in rows:
        if row["rule_code"] != rule_code:
            continue
        day = date.fromisoformat(row["draw_date"])
        gap = previous is not None and any(previous < m < day for m in missing)
        draws.append(
            ResearchDraw(
                draw_date=day,
                rule_code=rule_code,
                pool=pool,
                mains=tuple(int(row[f"main_{i}"]) for i in range(1, 7)),
                gap_before=gap,
            )
        )
        previous = day
    return draws


def snapshot_digest(snapshot: Path) -> str:
    return verify_bundle(Path(snapshot)).content_sha256


def holdout_size(n: int) -> int:
    """ceil(0.20 * n) with exact integer arithmetic."""
    return -(-n // 5)


def build_protocol(
    draws: list[ResearchDraw], snapshot_digest: str, **overrides
) -> Protocol:
    if not draws:
        raise ValueError("insufficient_data: empty population")
    if len({(d.rule_code, d.pool) for d in draws}) != 1:
        raise ValueError("Population mixes rule regimes")
    if [d.draw_date for d in draws] != sorted({d.draw_date for d in draws}):
        raise ValueError("Population must be strictly chronological")
    minimum = overrides.get("minimum_population", 282)
    n = len(draws)
    if n < minimum:
        raise ValueError(f"insufficient_data: {n} eligible draws, need {minimum}")
    start = overrides.get("validation_start", 175)
    block = overrides.get("block_size", 25)
    partial = overrides.get("minimum_partial_block", 10)
    development = n - holdout_size(n)
    dates = [d.draw_date for d in draws]
    folds, cursor = [], start
    while cursor < development:
        end = min(cursor + block, development)
        if end - cursor == block or end - cursor >= partial:
            folds.append(
                Fold(
                    start=cursor,
                    end=end,
                    first_date=dates[cursor],
                    last_date=dates[end - 1],
                )
            )
        cursor = end
    if sum(f.end - f.start == block for f in folds) < 2:
        raise ValueError("insufficient_data: fewer than two full validation blocks")
    return Protocol(
        snapshot_digest=snapshot_digest,
        rule_code=draws[0].rule_code,
        pool=draws[0].pool,
        population=n,
        dates=tuple(dates),
        development=(0, development),
        holdout=(development, n),
        holdout_first_date=dates[development],
        holdout_last_date=dates[-1],
        folds=tuple(folds),
        **overrides,
    )


def freeze_protocol(protocol: Protocol, output_root: Path) -> Path:
    """Write <root>/<digest>/protocol.json once; identical replays are reused."""
    body = canonical_json(protocol.payload())
    target = Path(output_root) / protocol.digest
    path = target / "protocol.json"
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError("Frozen protocol bytes differ from their digest")
        return target
    target.mkdir(parents=True, exist_ok=True)
    temporary = target / f".protocol-{uuid.uuid4().hex}.tmp"
    with open(temporary, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return target


def load_protocol(directory: Path) -> Protocol:
    """Load a frozen protocol, refusing any byte or digest change."""
    directory = Path(directory)
    body = (directory / "protocol.json").read_bytes()
    protocol = Protocol.model_validate(json.loads(body))
    if canonical_json(protocol.payload()) != body or directory.name != protocol.digest:
        raise ValueError("Protocol content does not match its frozen digest")
    return protocol


def verified_population(protocol: Protocol, snapshot: Path) -> list[ResearchDraw]:
    """Load the snapshot population and require it to match the protocol."""
    if snapshot_digest(snapshot) != protocol.snapshot_digest:
        raise ValueError("Snapshot differs from the protocol snapshot")
    draws = load_population(snapshot, protocol.rule_code)
    if tuple(d.draw_date for d in draws) != protocol.dates:
        raise ValueError("Snapshot population differs from protocol dates")
    return draws
