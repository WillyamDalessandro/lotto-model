"""Findings and model card from reconciled outputs only; never tunes models."""

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from lotto_model.research.inference import (
    FINAL_REPLICATES,
    calibration_bins,
    holm,
    infer_primary,
    monte_carlo_p,
    paired_bootstrap,
)
from lotto_model.research.odds import p_at_least

BOOTSTRAP_REPLICATES = 10_000


def _rows(path: Path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf8"))))


def _any_hits(rows, policy, budget, threshold):
    by_date = defaultdict(int)
    for r in rows:
        if r["policy"] == policy and int(r["budget"]) == budget:
            by_date[r["target_date"]] = max(
                by_date[r["target_date"]], int(r["matched_mains"])
            )
    dates = sorted(by_date)
    return dates, [by_date[d] >= threshold for d in dates]


def minimum_detectable_rate(p0: float, trials: int, alpha=0.05, power=0.8) -> float:
    """Smallest true rate an exact one-sided binomial test detects with power."""
    from scipy.stats import binom

    critical = int(binom.isf(alpha, trials, p0)) + 1
    while binom.sf(critical - 1, trials, p0) > alpha:
        critical += 1
    low, high = p0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if binom.sf(critical - 1, trials, middle) >= power:
            high = middle
        else:
            low = middle
    return high


def build_findings(
    output: Path, reconciled: dict, nulls: dict | None, pool: int, seed: int
) -> dict:
    output = Path(output)
    if not reconciled.get("reconciled"):
        raise ValueError("Findings require reconciled outputs")
    rows = _rows(output / "evaluation_results.csv")
    selected = reconciled["selected"]
    dates, model = _any_hits(rows, selected, 1, 3)
    base_dates, uniform = _any_hits(rows, "uniform", 1, 3)
    if dates != base_dates:
        raise ValueError("Model and baseline dates differ")
    primary = infer_primary(model, pool)
    primary["minimum_detectable_rate"] = minimum_detectable_rate(
        primary["p0"], len(dates)
    )
    bootstrap = paired_bootstrap(model, uniform, BOOTSTRAP_REPLICATES, seed)
    sensitivity = paired_bootstrap(
        model, uniform, BOOTSTRAP_REPLICATES, seed + 1, block=5
    )
    null = None
    if nulls is not None:
        null = dict(
            replicates=nulls["count"],
            final=nulls["count"] >= FINAL_REPLICATES,
            p_value=monte_carlo_p(primary["rate"], nulls["statistics"]),
        )
    secondary = {}
    _, five = _any_hits(rows, selected, 1, 5)
    secondary["one_line_5_plus_vs_exact"] = binomtest(
        sum(five), len(five), float(p_at_least(pool, 5)), alternative="greater"
    ).pvalue
    for budget in (5, 10):
        _, m = _any_hits(rows, selected, budget, 3)
        _, u = _any_hits(rows, "uniform", budget, 3)
        boot = paired_bootstrap(m, u, BOOTSTRAP_REPLICATES, seed + budget)
        diffs = np.asarray(m, float) - np.asarray(u, float)
        # One-sided bootstrap p: share of resampled means at or below zero.
        rng = np.random.Generator(np.random.PCG64(seed + 100 + budget))
        means = diffs[
            rng.integers(0, len(diffs), (BOOTSTRAP_REPLICATES, len(diffs)))
        ].mean(axis=1)
        secondary[f"budget_{budget}_any_line_3_plus_vs_uniform"] = float(
            (1 + np.sum(means <= 0)) / (BOOTSTRAP_REPLICATES + 1)
        )
        secondary[f"budget_{budget}_interval"] = boot["interval"]
    pvalues = {k: v for k, v in secondary.items() if not k.endswith("interval")}
    probabilities = _rows(output / "probabilities.csv")
    calibration = calibration_bins(
        [float(r["probability"]) for r in probabilities],
        [int(r["drawn"]) for r in probabilities],
    )
    promising = bool(
        primary["improvement"] > 0
        and primary["interval_excludes_zero"]
        and null is not None
        and null["final"]
        and null["p_value"] <= 0.05
    )
    if promising:
        verdict = "Promising; prospective confirmation still required."
    elif null is None or not null["final"]:
        verdict = "Not final: 10,000 null replicates are required before inference."
    else:
        verdict = (
            "No demonstrated advantage. Low power is not evidence of equality; "
            f"rates below {primary['minimum_detectable_rate']:.4f} were not detectable."
        )
    return dict(
        selected=selected,
        holdout_draws=len(dates),
        first_date=dates[0],
        last_date=dates[-1],
        primary=primary,
        paired_bootstrap=bootstrap,
        block_bootstrap_sensitivity=sensitivity,
        null=null,
        secondary_pvalues=pvalues,
        secondary_holm=holm(pvalues),
        calibration=calibration,
        promising=promising,
        verdict=verdict,
    )


def write_findings(output: Path, findings: dict, protocol_digest: str) -> Path:
    output = Path(output)
    p = findings["primary"]
    lines = [
        "# Historical experiment findings",
        "",
        f"Verdict: **{findings['verdict']}**",
        "",
        "Retrospective simulation: issue times are execution times and cutoffs are",
        "target-relative; these are not real pre-draw forecasts.",
        "",
        f"- Protocol: `{protocol_digest}`",
        f"- Selected configuration: `{findings['selected']}`",
        f"- Holdout: {findings['holdout_draws']} draws, "
        f"{findings['first_date']} to {findings['last_date']}",
        f"- One-line 3-plus: {p['events']}/{p['trials']} = {p['rate']:.4f} "
        f"(exact uniform p0 = {p['p0']:.5f})",
        f"- 95% Clopper-Pearson interval: [{p['rate_interval'][0]:.4f}, "
        f"{p['rate_interval'][1]:.4f}]; improvement interval "
        f"[{p['improvement_interval'][0]:.4f}, {p['improvement_interval'][1]:.4f}]",
        f"- Minimum detectable rate (alpha 0.05, power 0.8): "
        f"{p['minimum_detectable_rate']:.4f}",
        f"- Paired bootstrap vs uniform (mean difference "
        f"{findings['paired_bootstrap']['mean_difference']:.4f}): "
        f"{findings['paired_bootstrap']['interval']}; block-5 sensitivity "
        f"{findings['block_bootstrap_sensitivity']['interval']}",
    ]
    null = findings["null"]
    lines.append(
        "- Null refits: not run"
        if null is None
        else f"- Null refits: {null['replicates']} (final={null['final']}), "
        f"Monte Carlo p = {null['p_value']:.4f}"
    )
    lines += ["", "## Secondary comparisons (Holm-adjusted, descriptive)", ""]
    for name, value in findings["secondary_holm"].items():
        raw = findings["secondary_pvalues"][name]
        lines.append(f"- {name}: raw p={raw:.4f}, Holm p={value:.4f}")
    lines += [
        "",
        "## Calibration (10 equal-width bins)",
        "",
        "| bin | count | mean p | observed |",
        "|---|---|---|---|",
    ]
    for b in findings["calibration"]:
        if b["count"]:
            close = "]" if b["upper"] == 1 else ")"
            lines.append(
                f"| [{b['lower']:.1f}, {b['upper']:.1f}{close} | {b['count']} "
                f"| {b['mean_probability']:.4f} | {b['observed_rate']:.4f} |"
            )
    report = output / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf8")
    card = [
        "# Model card",
        "",
        f"- Configuration: `{findings['selected']}` (fixed six-candidate grid)",
        "- Output: per-number marginal inclusion probabilities; the line is the six",
        "  largest. Marginals are not a joint distribution over combinations.",
        "- Training: expanding history of one verified regime, refit before every",
        "  target; features use only earlier draws.",
        f"- Evidence: {findings['verdict']}",
        "- Intended use: research only. Not betting advice; lottery draws are",
        "  designed to be independent and uniform.",
        "- Artifact: `model.json` (JSON parameters / reproducible refit spec).",
    ]
    (output / "model-card.md").write_text("\n".join(card) + "\n", encoding="utf8")
    (output / "findings.json").write_text(
        json.dumps(findings, indent=2, default=str) + "\n", encoding="utf8"
    )
    return report
