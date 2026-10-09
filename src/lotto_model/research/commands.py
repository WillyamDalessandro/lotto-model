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
