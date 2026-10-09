"""Independent recomputation of holdout outputs from raw files only."""

import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

from lotto_model.audit.bundle import verify_bundle


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf8"))))


def reconcile_outputs(output: Path, snapshot: Path) -> dict:
    """Recompute intersections, denominators and rates without runner helpers."""
    output, snapshot = Path(output), Path(snapshot)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf8"))
    for name, digest in manifest.items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Artifact hash mismatch: {name}")
    verify_bundle(snapshot)
    truth = {
        r["draw_date"]: {int(r[f"main_{i}"]) for i in range(1, 7)}
        for r in _rows(snapshot / "draws.csv")
    }
    predictions = {}
    for r in _rows(output / "prediction_log.csv"):
        key = (r["policy"], r["target_date"], r["budget"], r["line_index"])
        if key in predictions:
            raise ValueError("Duplicate prediction")
        mains = {int(n) for n in r["mains"].split()}
        if len(mains) != 6 or r["max_input_date"] >= r["target_date"]:
            raise ValueError("Invalid issued prediction")
        predictions[key] = mains
    lines = defaultdict(lambda: defaultdict(list))
    for r in _rows(output / "evaluation_results.csv"):
        key = (r["policy"], r["target_date"], r["budget"], r["line_index"])
        observed = truth.get(r["target_date"])
        if key not in predictions or observed is None:
            raise ValueError("Evaluation without prediction or outcome")
        if {int(n) for n in r["outcome"].split()} != observed:
            raise ValueError("Outcome differs from snapshot")
        matched = len(predictions[key] & observed)
        if matched != int(r["matched_mains"]) or int(r["hit_3_plus"]) != (matched >= 3):
            raise ValueError("Recorded match count differs from recomputation")
        lines[(r["policy"], int(r["budget"]))][r["target_date"]].append(matched)
    if len(predictions) != sum(len(v) for g in lines.values() for v in g.values()):
        raise ValueError("Predictions lack evaluations")
    date_sets = {frozenset(g) for g in lines.values()}
    if len(date_sets) != 1:
        raise ValueError("Compared policies cover different dates")
    recomputed = {}
    for (policy, budget), by_date in sorted(lines.items()):
        if any(len(v) != budget for v in by_date.values()):
            raise ValueError("Portfolio size differs from budget")
        flat = [m for v in by_date.values() for m in v]
        recomputed[f"{policy}:{budget}"] = dict(
            draws=len(by_date),
            lines=len(flat),
            line_hit_3_plus=sum(m >= 3 for m in flat),
            any_line_hit_3_plus=sum(max(v) >= 3 for v in by_date.values()),
            any_line_hit_5_plus=sum(max(v) >= 5 for v in by_date.values()),
        )
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf8"))
    for key, value in recomputed.items():
        reported = metrics["summary"].get(key)
        if reported is None or (
            reported["draws"],
            reported["lines"],
            reported["line_hit_3_plus"]["numerator"],
            reported["any_line_hit_3_plus"]["numerator"],
            reported["any_line_hit_5_plus"]["numerator"],
        ) != tuple(value.values()):
            raise ValueError(f"Reported metrics differ from recomputation: {key}")
    if set(metrics["summary"]) != set(recomputed):
        raise ValueError("Reported and recomputed populations differ")
    return dict(reconciled=True, selected=metrics["selected"], recomputed=recomputed)
