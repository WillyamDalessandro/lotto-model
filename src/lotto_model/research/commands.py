import json
from functools import wraps
from pathlib import Path

import typer
from pydantic import ValidationError

from lotto_model.audit.contracts import canonical_json

app = typer.Typer(help="Frozen research protocols, baselines and experiments.")


def safe_command(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, ValidationError, OSError, KeyError, TypeError) as exc:
            reason = str(exc) if str(exc).startswith("insufficient_data") else ""
            typer.echo(
                "Research command failed; check snapshot, protocol and inputs. "
                + reason,
                err=True,
            )
            raise typer.Exit(1) from None

    return guarded


def write_once(path: Path, body: bytes):
    """Create a result file once; an identical rerun is accepted."""
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError("Existing result differs; results are immutable")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(body)
    temporary.replace(path)


@app.command()
@safe_command
def protocol(
    snapshot: Path,
    rule_code: str = typer.Option(...),
    output_root: Path = Path("data/experiments"),
):
    """Freeze a chronological protocol from a verified snapshot."""
    from lotto_model.research.protocol import (
        build_protocol,
        freeze_protocol,
        load_population,
        snapshot_digest,
    )

    digest = snapshot_digest(snapshot)
    frozen = build_protocol(load_population(snapshot, rule_code), digest)
    path = freeze_protocol(frozen, output_root)
    typer.echo(
        json.dumps(
            dict(
                path=str(path),
                protocol_digest=frozen.digest,
                population=frozen.population,
                development=list(frozen.development),
                holdout=list(frozen.holdout),
                folds=[[f.start, f.end] for f in frozen.folds],
            )
        )
    )


@app.command()
@safe_command
def baselines(
    protocol_dir: Path,
    snapshot: Path = typer.Option(...),
    simulations: int | None = None,
):
    """Development-only baselines and seeded null simulations."""
    from lotto_model.research.backtest import BASELINES, evaluate, run_development
    from lotto_model.research.metrics import summarize
    from lotto_model.research.protocol import load_protocol, verified_population
    from lotto_model.research.simulation import simulate_baselines

    frozen = load_protocol(protocol_dir)
    draws = verified_population(frozen, snapshot)
    count = frozen.simulations if simulations is None else simulations
    records = []
    for policy in BASELINES:
        for budget in frozen.budgets:
            records += evaluate(run_development(frozen, draws, policy, budget), draws)
    result = dict(
        protocol_digest=frozen.digest,
        snapshot_digest=frozen.snapshot_digest,
        scope="development folds only; holdout not evaluated",
        summary=summarize(records),
        simulation=simulate_baselines(frozen, draws, count),
        official=count == frozen.simulations,
    )
    out = protocol_dir / "baselines" / f"simulations-{count}"
    write_once(out / "results.json", canonical_json(result))
    write_once(
        out / "predictions.jsonl",
        b"".join(canonical_json(r.model_dump(mode="json")) for r in records),
    )
    typer.echo(json.dumps(dict(path=str(out), summary=result["summary"])))


def _engine():
    from lotto_model.config import Settings
    from lotto_model.db import create_engine_from_settings

    return create_engine_from_settings(Settings())


@app.command()
@safe_command
def develop(protocol_dir: Path, snapshot: Path = typer.Option(...)):
    """Score the six fixed candidates on development folds only."""
    from lotto_model.research.experiment import run_development_outputs

    out = run_development_outputs(protocol_dir, snapshot)
    summary = json.loads((out / "development.json").read_text(encoding="utf8"))
    typer.echo(json.dumps(dict(path=str(out), selected=summary["selected"])))


@app.command()
@safe_command
def freeze(development_dir: Path):
    """Freeze the selected configuration before any holdout access."""
    from lotto_model.research.experiment import freeze_selection

    out = freeze_selection(development_dir)
    typer.echo(json.dumps(dict(path=str(out), identity=out.name)))


@app.command()
@safe_command
def holdout(frozen_dir: Path, snapshot: Path = typer.Option(...)):
    """Run (or resume) the locked holdout once under the frozen identity."""
    from sqlalchemy.exc import SQLAlchemyError

    from lotto_model.research.experiment import run_holdout

    engine = _engine()
    try:
        out = run_holdout(engine, frozen_dir, snapshot)
    except SQLAlchemyError:
        raise ValueError("Database failure") from None
    finally:
        engine.dispose()
    typer.echo(json.dumps(dict(path=str(out))))


@app.command()
@safe_command
def nulls(
    frozen_dir: Path,
    snapshot: Path = typer.Option(...),
    count: int = 10_000,
    workers: int = typer.Option(1, help="Parallel processes; results are identical."),
):
    """Checkpointed null-history refits of the frozen pipeline (resumable)."""
    from lotto_model.research.experiment import load_frozen
    from lotto_model.research.inference import run_null_replicates
    from lotto_model.research.protocol import verified_population

    frozen, _, protocol = load_frozen(frozen_dir)
    draws = verified_population(protocol, snapshot)
    result = run_null_replicates(
        frozen,
        protocol,
        draws,
        count,
        Path(frozen_dir) / "holdout" / "nulls",
        workers,
    )
    typer.echo(json.dumps(dict(count=result["count"], final=result["final"])))


@app.command()
@safe_command
def reconcile(frozen_dir: Path, snapshot: Path = typer.Option(...)):
    """Independently recompute holdout outputs from raw files."""
    from lotto_model.research.reconcile import reconcile_outputs

    result = reconcile_outputs(Path(frozen_dir) / "holdout", snapshot)
    typer.echo(json.dumps(result))


@app.command()
@safe_command
def report(frozen_dir: Path, snapshot: Path = typer.Option(...)):
    """Write report.md and model-card.md from reconciled outputs."""
    from lotto_model.research.experiment import load_frozen
    from lotto_model.research.inference import run_null_replicates
    from lotto_model.research.protocol import verified_population
    from lotto_model.research.reconcile import reconcile_outputs
    from lotto_model.research.reporting import build_findings, write_findings

    frozen, identity, protocol = load_frozen(frozen_dir)
    output = Path(frozen_dir) / "holdout"
    reconciled = reconcile_outputs(output, snapshot)
    checkpoints = output / "nulls"
    existing = len(list(checkpoints.glob("*.json"))) if checkpoints.exists() else 0
    null = None
    if existing:
        draws = verified_population(protocol, snapshot)
        null = run_null_replicates(frozen, protocol, draws, existing, checkpoints)
    findings = build_findings(
        output, reconciled, null, protocol.pool, int(identity[:8], 16)
    )
    path = write_findings(output, findings, protocol.digest)
    typer.echo(json.dumps(dict(path=str(path), verdict=findings["verdict"])))


@app.command("predict")
@safe_command
def predict_command(
    frozen_dir: Path,
    snapshot: Path = typer.Option(...),
    target_date: str = typer.Option(...),
    target_gap: bool = typer.Option(
        False, help="A scheduled draw is missing immediately before the target."
    ),
):
    """Research inference for a later date from the verified snapshot history."""
    from datetime import date

    from lotto_model.research.experiment import load_frozen
    from lotto_model.research.predictor import predict_next
    from lotto_model.research.protocol import load_population

    frozen, _, protocol = load_frozen(frozen_dir)
    # Any verified snapshot of the same regime may supply the later history.
    history = load_population(snapshot, protocol.rule_code)
    target = date.fromisoformat(target_date)
    value = predict_next(
        frozen,
        [d for d in history if d.draw_date < target],
        target,
        protocol.pool,
        target_gap,
        root_seed=protocol.root_seed,
    )
    typer.echo(json.dumps(value))


@app.command("study")
@safe_command
def study_command(
    snapshot: Path,
    rule_code: str = typer.Option(...),
    output_root: Path = Path("data/studies"),
    evaluation_days: int = typer.Option(1826, help="Evaluation window length."),
    training_window: int | None = typer.Option(
        None, help="Train on only the latest N earlier draws of the regime."
    ),
    pool_with: list[str] = typer.Option(
        [], help="Earlier rule codes whose draws are added to training."
    ),
):
    """Phase 7: tune on earlier draws, evaluate the last five years, compare."""
    from lotto_model.research.protocol import load_population, snapshot_digest
    from lotto_model.research.study import StudyConfig, best, run_study

    draws = load_population(snapshot, rule_code)
    if not draws:
        raise ValueError("insufficient_data: no draws for this rule code")
    config = StudyConfig(
        snapshot_digest=snapshot_digest(snapshot),
        rule_code=rule_code,
        pool=draws[0].pool,
        evaluation_days=evaluation_days,
        training_window=training_window,
        pooled_regimes=tuple(pool_with),
    )
    pooled = {code: load_population(snapshot, code) for code in pool_with}
    output, reported = run_study(config, draws, output_root, pooled)
    top = best(reported["summary"])
    typer.echo(
        json.dumps(
            dict(
                path=str(output),
                significant=[
                    f"{r['source']}:{r['method']}"
                    for r in reported["summary"]
                    if r["significant"]
                ],
                best_observed=f"{top['source']}:{top['method']}",
            )
        )
    )


@app.command("compare")
@safe_command
def compare_command(
    studies: list[Path],
    output: Path | None = typer.Option(None, help="Write the table here too."),
):
    """Compare study folders that share an evaluation window (dataset variants)."""
    from lotto_model.research.study import compare_studies

    table = compare_studies(studies)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(table, encoding="utf8")
    typer.echo(table)
