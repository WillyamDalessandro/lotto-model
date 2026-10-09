"""Development outputs, freezing and the resumable once-only holdout run."""

import csv
import io
import json
from datetime import date
from pathlib import Path

from lotto_model.audit.contracts import canonical_json, sha256
from lotto_model.research.backtest import BASELINES, evaluate, predict
from lotto_model.research.contracts import (
    PredictionRecord,
    Protocol,
    ResearchDraw,
)
from lotto_model.research.features import FEATURE_COLUMNS, FEATURE_VERSION
from lotto_model.research.ledger import (
    acquire_run_lock,
    claim_experiment,
    issue_predictions,
    issued,
    record_evaluations,
    release_run_lock,
    set_status,
)
from lotto_model.research.metrics import summarize
from lotto_model.research.models import config_from_id
from lotto_model.research.odds import p_at_least
from lotto_model.research.protocol import load_protocol, verified_population
from lotto_model.research.selection import (
    candidate_records,
    develop,
    predict_target,
    require_candidate_protocol,
)

LOCK_FILE = Path(__file__).resolve().parents[3] / "uv.lock"


def dependency_lock_sha256() -> str:
    try:
        return sha256(LOCK_FILE.read_bytes())
    except OSError:
        return "unavailable"


def write_once(path: Path, body: bytes):
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError(f"Existing {path.name} differs; outputs are immutable")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(body)
    temporary.replace(path)


def jsonl(rows) -> bytes:
    return b"".join(canonical_json(r) for r in rows)


def run_development_outputs(
    protocol_dir: Path, snapshot: Path, candidates=None
) -> Path:
    """Score fixed candidates on development folds and persist results once."""
    protocol = load_protocol(protocol_dir)
    draws = verified_population(protocol, snapshot)
    result = develop(protocol, draws, *([candidates] if candidates else []))
    out = Path(protocol_dir) / "development"
    write_once(
        out / "predictions.jsonl",
        jsonl(r.model_dump(mode="json") for r in result["records"]),
    )
    summary = dict(
        protocol_digest=protocol.digest,
        snapshot_digest=protocol.snapshot_digest,
        scores=result["scores"],
        selected=result["selected"],
        candidates=[s["candidate"] for s in result["scores"]],
        predictions_sha256=sha256((out / "predictions.jsonl").read_bytes()),
        scope="development folds only",
    )
    write_once(out / "development.json", canonical_json(summary))
    return out


def freeze_selection(development_dir: Path) -> Path:
    """Freeze the selected configuration before any holdout access."""
    development_dir = Path(development_dir)
    body = (development_dir / "development.json").read_bytes()
    development = json.loads(body)
    protocol = load_protocol(development_dir.parent)
    if development["protocol_digest"] != protocol.digest:
        raise ValueError("Development results belong to another protocol")
    predictions = (development_dir / "predictions.jsonl").read_bytes()
    if sha256(predictions) != development["predictions_sha256"]:
        raise ValueError("Development predictions changed after scoring")
    config = config_from_id(development["selected"])
    frozen = dict(
        version=1,
        protocol_digest=protocol.digest,
        snapshot_digest=protocol.snapshot_digest,
        selected=config.as_dict(),
        feature_version=FEATURE_VERSION,
        feature_columns=list(FEATURE_COLUMNS),
        development_sha256=sha256(body),
        dependency_lock_sha256=dependency_lock_sha256(),
        retraining="expanding history; refit before every holdout target",
        line_policy="top six probabilities, ties to smaller numbers",
        budgets=list(protocol.budgets),
    )
    identity = sha256(canonical_json(frozen))
    out = development_dir.parent / "frozen" / identity
    write_once(out / "frozen.json", canonical_json(frozen))
    return out


def load_frozen(frozen_dir: Path) -> tuple[dict, str, Protocol]:
    frozen_dir = Path(frozen_dir)
    body = (frozen_dir / "frozen.json").read_bytes()
    frozen = json.loads(body)
    identity = sha256(body)
    if frozen_dir.name != identity or canonical_json(frozen) != body:
        raise ValueError("Frozen selection does not match its identity")
    protocol = load_protocol(frozen_dir.parents[1])
    if frozen["protocol_digest"] != protocol.digest:
        raise ValueError("Frozen selection belongs to another protocol")
    if frozen["dependency_lock_sha256"] != dependency_lock_sha256():
        raise ValueError("Dependency lock differs from the frozen environment")
    if frozen["feature_columns"] != list(FEATURE_COLUMNS):
        raise ValueError("Feature schema differs from the frozen schema")
    return frozen, identity, protocol


def _records_from_rows(rows, protocol, policy) -> list[PredictionRecord]:
    return [
        PredictionRecord(
            protocol_digest=protocol.digest,
            snapshot_digest=protocol.snapshot_digest,
            target_date=r["target_date"],
            policy=policy,
            budget=r["budget"],
            line_index=r["line_index"],
            mains=tuple(r["mains"]),
            seed=None if r["seed"] is None else int(r["seed"]),
            max_input_date=r["max_input_date"],
        )
        for r in rows
    ]


def run_holdout(engine, frozen_dir: Path, snapshot: Path) -> Path:
    """Issue each holdout target before scoring it; resume reuses issued lines."""
    frozen, identity, protocol = load_frozen(frozen_dir)
    require_candidate_protocol(protocol)
    draws = verified_population(protocol, snapshot)
    candidate = config_from_id(frozen["selected"]["id"])
    with engine.connect() as lock_connection:
        acquire_run_lock(lock_connection, identity)
        try:
            with engine.begin() as conn:
                row = claim_experiment(conn, identity, frozen)
                experiment = row["id"]
                if row["status"] != "evaluated":
                    set_status(conn, experiment, "evaluating")
            if row["status"] != "evaluated":
                try:
                    _execute(engine, experiment, protocol, draws, candidate)
                except Exception as exc:
                    with engine.begin() as conn:
                        set_status(conn, experiment, "failed", type(exc).__name__)
                    raise
                with engine.begin() as conn:
                    set_status(conn, experiment, "evaluated")
            with engine.connect() as conn:
                rows = issued(conn, experiment)
        finally:
            release_run_lock(lock_connection, identity)
            lock_connection.commit()
    return export_holdout(Path(frozen_dir), protocol, draws, rows, frozen, identity)


def _execute(engine, experiment, protocol, draws, candidate):
    cache = {}
    start, end = protocol.holdout
    for index in range(start, end):
        target = draws[index]
        with engine.connect() as conn:
            existing = [
                r
                for r in issued(conn, experiment)
                if r["target_date"] == target.draw_date
            ]
        if not existing:
            probabilities, cutoff = predict_target(
                protocol, draws, index, candidate, cache
            )
            records = []
            for budget in protocol.budgets:
                records += candidate_records(
                    protocol,
                    candidate.identifier,
                    target.draw_date,
                    budget,
                    probabilities,
                    cutoff,
                )
            # Predictions are committed before the outcome is attached.
            with engine.begin() as conn:
                issue_predictions(
                    conn, experiment, records, [float(p) for p in probabilities]
                )
            with engine.connect() as conn:
                existing = [
                    r
                    for r in issued(conn, experiment)
                    if r["target_date"] == target.draw_date
                ]
        pending = [r for r in existing if r["matched_mains"] is None]
        if pending:
            records = _records_from_rows(pending, protocol, candidate.identifier)
            with engine.begin() as conn:
                record_evaluations(conn, experiment, evaluate(records, [target]))


def _csv(header, rows) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf8")


def export_holdout(frozen_dir, protocol, draws, rows, frozen, identity) -> Path:
    """Write immutable holdout exports and a hash manifest."""
    policy = frozen["selected"]["id"]
    out = frozen_dir / "holdout"
    holdout_dates = set(protocol.dates[protocol.holdout[0] :])
    if {r["target_date"] for r in rows} != holdout_dates or any(
        r["matched_mains"] is None for r in rows
    ):
        raise ValueError("Holdout ledger is incomplete")
    model = evaluate(_records_from_rows(rows, protocol, policy), draws)
    indices = list(range(*protocol.holdout))
    baselines = []
    for name in BASELINES:
        for budget in protocol.budgets:
            baselines += evaluate(
                predict(protocol, draws, name, budget, indices, allow_holdout=True),
                draws,
            )
    summary = summarize(model + baselines)
    files = {
        "prediction_log.csv": _csv(
            (
                "policy",
                "target_date",
                "budget",
                "line_index",
                "mains",
                "seed",
                "max_input_date",
                "issued_at",
            ),
            [
                (
                    policy,
                    r["target_date"],
                    r["budget"],
                    r["line_index"],
                    " ".join(map(str, r["mains"])),
                    r["seed"] or "",
                    r["max_input_date"],
                    r["issued_at"].isoformat(),
                )
                for r in rows
            ]
            + [
                (
                    e.prediction.policy,
                    e.prediction.target_date,
                    e.prediction.budget,
                    e.prediction.line_index,
                    " ".join(map(str, e.prediction.mains)),
                    e.prediction.seed,
                    e.prediction.max_input_date,
                    "",
                )
                for e in baselines
            ],
        ),
        "evaluation_results.csv": _csv(
            (
                "policy",
                "target_date",
                "budget",
                "line_index",
                "outcome",
                "matched_mains",
                "hit_3_plus",
                "hit_5_plus",
            ),
            [
                (
                    e.prediction.policy,
                    e.prediction.target_date,
                    e.prediction.budget,
                    e.prediction.line_index,
                    " ".join(map(str, e.outcome)),
                    e.matched_mains,
                    int(e.hit_3_plus),
                    int(e.hit_5_plus),
                )
                for e in model + baselines
            ],
        ),
        "model_comparison.csv": _csv(
            (
                "policy",
                "budget",
                "draws",
                "line_hit_3_plus",
                "line_hit_5_plus",
                "any_line_hit_3_plus",
                "any_line_hit_5_plus",
                "mean_matches",
            ),
            [
                (
                    v["policy"],
                    v["budget"],
                    v["draws"],
                    f"{v['line_hit_3_plus']['numerator']}/{v['line_hit_3_plus']['denominator']}",
                    f"{v['line_hit_5_plus']['numerator']}/{v['line_hit_5_plus']['denominator']}",
                    f"{v['any_line_hit_3_plus']['numerator']}/{v['any_line_hit_3_plus']['denominator']}",
                    f"{v['any_line_hit_5_plus']['numerator']}/{v['any_line_hit_5_plus']['denominator']}",
                    f"{v['mean_matches']:.6f}",
                )
                for v in summary.values()
            ],
        ),
        "baseline_simulation_summary.csv": _csv(
            ("statistic", "pool", "exact_probability"),
            [
                ("line_hit_3_plus", protocol.pool, float(p_at_least(protocol.pool, 3))),
                ("line_hit_5_plus", protocol.pool, float(p_at_least(protocol.pool, 5))),
            ],
        ),
        "metrics.json": canonical_json(
            dict(
                identity=identity,
                protocol_digest=protocol.digest,
                snapshot_digest=protocol.snapshot_digest,
                selected=policy,
                holdout=dict(
                    first_date=protocol.holdout_first_date,
                    last_date=protocol.holdout_last_date,
                    draws=len(indices),
                ),
                summary=summary,
                note="Retrospective simulation: issue time is execution time, "
                "cutoffs are target-relative; not real pre-draw forecasts.",
            )
        ),
    }
    outcomes = {d.draw_date: set(d.mains) for d in draws}
    files["probabilities.csv"] = _csv(
        ("target_date", "number", "probability", "drawn"),
        [
            (
                r["target_date"],
                number,
                repr(float(value)),
                int(number in outcomes[r["target_date"]]),
            )
            for r in rows
            if r["budget"] == 1 and r["line_index"] == 0
            for number, value in enumerate(r["probabilities"], start=1)
        ],
    )
    files["model.json"] = canonical_json(model_artifact(frozen, protocol, draws))
    for name, body in files.items():
        write_once(out / name, body)
    manifest = {name: sha256(body) for name, body in sorted(files.items())}
    write_once(out / "manifest.json", canonical_json(manifest))
    return out


def model_artifact(frozen: dict, protocol: Protocol, draws: list[ResearchDraw]) -> dict:
    """Reproducible JSON artifact: no pickle; refit deterministically from data."""
    candidate = config_from_id(frozen["selected"]["id"])
    from lotto_model.research.features import training_rows
    from lotto_model.research.models import fit_candidate
    from lotto_model.research.selection import model_seed

    features, y = training_rows(draws, len(draws), protocol.feature_warmup)
    fitted = fit_candidate(
        candidate, features, y, model_seed(protocol, candidate, draws[-1].draw_date)
    )
    parameters = None
    if candidate.family == "logistic":
        scale, model = fitted.estimator["scale"], fitted.estimator["model"]
        parameters = dict(
            mean=scale.mean_.tolist(),
            scale=scale.scale_.tolist(),
            coefficients=model.coef_[0].tolist(),
            intercept=float(model.intercept_[0]),
        )
    return dict(
        frozen=frozen,
        training_cutoff=draws[-1].draw_date,
        training_rows=fitted.training_rows,
        feature_columns=list(FEATURE_COLUMNS),
        parameters=parameters,
        reproduction="Refit the frozen configuration on the verified snapshot; "
        "binary model files are never loaded.",
    )


def parse_date(value: str) -> date:
    return date.fromisoformat(value)
