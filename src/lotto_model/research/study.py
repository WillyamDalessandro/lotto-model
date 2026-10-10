"""Phase 7 study: leakage-safe tuning, five-year walk-forward, model comparison.

Tuning uses only chronological blocks that end before the evaluation window.
Every evaluated draw is predicted by a model fitted on earlier draws only.
"""

import csv
import io
import json
import warnings
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from lotto_model.audit.contracts import canonical_json, sha256
from lotto_model.research.contracts import ROOT_SEED, ResearchDraw
from lotto_model.research.experiment import write_once
from lotto_model.research.features import (
    FEATURE_COLUMNS,
    FEATURE_VERSION,
    labels,
    target_features,
    training_rows,
)
from lotto_model.research.inference import clopper_pearson, holm
from lotto_model.research.odds import p_at_least
from lotto_model.research.policies import (
    derive_seed,
    frequency_marginals,
    top_line,
    uniform_portfolio,
)
from lotto_model.research.selection import brier_and_log_loss

SEARCH_SPACE = {
    "logistic": {"C": [0.001, 0.01, 0.1, 1.0]},
    "boosting": {"max_leaf_nodes": [3, 7, 15], "learning_rate": [0.03, 0.1]},
    "forest": {"max_depth": [4, 8], "min_samples_leaf": [50, 200]},
    "mlp": {"hidden": [8, 32], "alpha": [0.001, 0.1]},
}
FAMILIES = tuple(SEARCH_SPACE)
MARGINAL_METHODS = ("top6", "weighted", "coverage5", "coverage10")
RANDOM_METHODS = ("random1", "random5", "random10")
HEURISTIC_METHODS = ("hot", "cold", "overdue")
BUDGET = {"coverage5": 5, "coverage10": 10, "random5": 5, "random10": 10}
SIGNIFICANCE = 0.05


class StudyConfig(BaseModel):
    """Every predeclared choice; any change gives a different digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_code: str
    pool: int = Field(ge=7)
    feature_version: int = FEATURE_VERSION
    # 2: coverage lines shift one rank per wrap (pools divisible by six).
    method_version: Literal[2] = 2
    evaluation_days: int = Field(default=1826, ge=1)
    feature_warmup: int = Field(default=150, ge=1)
    block_size: int = Field(default=25, ge=1)
    tuning_blocks: int = Field(default=4, ge=1)
    families: tuple[str, ...] = FAMILIES
    search_space: dict = Field(default_factory=lambda: SEARCH_SPACE)
    null_samples: int = Field(default=20_000, ge=1000)
    root_seed: int = ROOT_SEED
    # Training-data variants; evaluation draws and tests never change.
    training_window: int | None = Field(default=None, ge=25)
    pooled_regimes: tuple[str, ...] = ()
    tuning: str = (
        "full predeclared grid; each setting walk-forward over the tuning blocks "
        "immediately before the evaluation window, refit at each block start"
    )
    selection: str = (
        "lowest mean validation log loss, then highest validation 3-plus rate, "
        "then stable setting identifier"
    )
    evaluation: str = (
        "expanding history, refit every block_size draws on earlier draws only; "
        "null: uniform outcome with the issued lines fixed; Holm over every "
        "source-method pair"
    )

    @model_validator(mode="after")
    def known_families(self):
        if not self.families or not set(self.families) <= set(self.search_space):
            raise ValueError("Every model family needs a predeclared search space")
        return self

    @property
    def digest(self) -> str:
        data = self.model_dump(mode="json")
        # Default training data keeps the digests of earlier studies.
        for name in ("training_window", "pooled_regimes"):
            if not data[name]:
                data.pop(name)
        return sha256(canonical_json(data))


def settings(config: StudyConfig, family: str) -> list[dict]:
    space = config.search_space[family]
    names = sorted(space)
    return [dict(zip(names, values)) for values in product(*(space[n] for n in names))]


def setting_id(family: str, params: dict) -> str:
    return family + "-" + "-".join(f"{k}{params[k]:g}" for k in sorted(params))


def estimator(family: str, params: dict, seed: int):
    state = seed % (2**32)
    if family == "logistic":
        model = LogisticRegression(C=params["C"], max_iter=2000)
        return Pipeline([("scale", StandardScaler()), ("model", model)])
    if family == "boosting":
        return HistGradientBoostingClassifier(
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            learning_rate=params["learning_rate"],
            max_iter=100,
            min_samples_leaf=47,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=state,
        )
    if family == "forest":
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            n_jobs=-1,
            random_state=state,
        )
    if family == "mlp":
        model = MLPClassifier(
            hidden_layer_sizes=(int(params["hidden"]),),
            alpha=params["alpha"],
            max_iter=60,
            random_state=state,
        )
        return Pipeline([("scale", StandardScaler()), ("model", model)])
    raise ValueError(f"Unknown model family {family}")


def split(config: StudyConfig, draws: list[ResearchDraw]) -> dict:
    """Chronological boundaries: warmup, tuning blocks, then evaluation."""
    if not draws or any(d.rule_code != config.rule_code for d in draws):
        raise ValueError("Study draws must come from the configured regime")
    if any(a.draw_date >= b.draw_date for a, b in zip(draws, draws[1:])):
        raise ValueError("Study draws must be chronological and unique")
    cutoff = draws[-1].draw_date - timedelta(days=config.evaluation_days)
    first = next(i for i, d in enumerate(draws) if d.draw_date > cutoff)
    tuning = first - config.tuning_blocks * config.block_size
    if tuning - config.feature_warmup < config.block_size:
        raise ValueError(
            "insufficient_data: need feature warmup, one training block and the "
            "tuning blocks before the evaluation window"
        )
    return dict(tuning_start=tuning, evaluation_start=first, end=len(draws))


class FeatureCache(dict):
    def __init__(self, draws, pooled=None):
        super().__init__()
        self.draws = draws
        # Rows from earlier regimes: (values with base rate, labels) or None.
        self.pooled = pooled

    def features(self, index):
        if index not in self:
            self[index] = target_features(self.draws, index)
        return self[index]


def with_base_rate(values: np.ndarray, pool: int) -> np.ndarray:
    """Pooled regimes differ in base rate 6/pool; give the model that column."""
    return np.column_stack([values, np.full(len(values), 6 / pool)])


def pooled_rows(config, regimes: dict[str, list[ResearchDraw]], first_date):
    """Supervised rows of earlier regimes, all drawn before the studied one."""
    if set(regimes) != set(config.pooled_regimes):
        raise ValueError("Pooled draws must match the configured regimes")
    values, y = [], []
    for code in config.pooled_regimes:
        draws = regimes[code]
        if not draws or draws[-1].draw_date >= first_date:
            raise ValueError(f"Pooled regime {code} must end before the study")
        if len(draws) <= config.feature_warmup:
            raise ValueError(f"insufficient_data: pooled regime {code}")
        rows, labels_ = training_rows(draws, len(draws), config.feature_warmup)
        values.append(with_base_rate(rows.values, draws[0].pool))
        y.append(labels_)
    return np.vstack(values), np.concatenate(y)


def model_inputs(config, values: np.ndarray) -> np.ndarray:
    return with_base_rate(values, config.pool) if config.pooled_regimes else values


def walk_forward(config, draws, cache, family, params, start, end, label):
    """Marginals for targets start..end-1; fit at each block on earlier rows."""
    marginals, converged = {}, True
    for block in range(start, end, config.block_size):
        first = config.feature_warmup
        if config.training_window is not None:
            first = max(first, block - config.training_window)
        rows, y = training_rows(draws, block, first, cache)
        values = model_inputs(config, rows.values)
        if cache.pooled is not None:
            values = np.vstack([cache.pooled[0], values])
            y = np.concatenate([cache.pooled[1], y])
        seed = derive_seed(
            config.digest, label, draws[block].draw_date, 0, 0, config.root_seed
        )
        model = estimator(family, params, seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            model.fit(values, y)
        converged &= not any(issubclass(w.category, ConvergenceWarning) for w in caught)
        for index in range(block, min(block + config.block_size, end)):
            features = cache.features(index)
            if features.max_input_date >= draws[index].draw_date:
                raise ValueError("Feature leakage detected")
            inputs = model_inputs(config, features.values)
            marginals[index] = model.predict_proba(inputs)[:, 1]
    return marginals, converged


def hits(marginals: dict, draws) -> tuple[float, float]:
    """Mean log loss and top-six 3-plus rate over the given targets."""
    losses, events = [], 0
    for index, p in marginals.items():
        outcome = labels(draws[index])
        losses.append(brier_and_log_loss(p, outcome)[1])
        events += len(set(top_line(p)) & set(draws[index].mains)) >= 3
    return float(np.mean(losses)), events / len(marginals)


def tune(config, draws, cache, bounds) -> tuple[list[dict], dict]:
    rows, chosen = [], {}
    for family in config.families:
        scored = []
        for params in settings(config, family):
            identifier = setting_id(family, params)
            marginals, converged = walk_forward(
                config,
                draws,
                cache,
                family,
                params,
                bounds["tuning_start"],
                bounds["evaluation_start"],
                identifier,
            )
            loss, rate = hits(marginals, draws)
            scored.append((loss, -rate, identifier, params))
            rows.append(
                dict(
                    family=family,
                    setting=identifier,
                    params=json.dumps(params, sort_keys=True),
                    validation_targets=len(marginals),
                    log_loss=loss,
                    hit_3_plus_rate=rate,
                    converged=converged,
                )
            )
        loss, _, identifier, params = min(scored, key=lambda s: s[:3])
        chosen[family] = dict(setting=identifier, params=params)
    for row in rows:
        row["selected"] = chosen[row["family"]]["setting"] == row["setting"]
    return rows, chosen


def coverage_lines(scores, budget: int) -> tuple[tuple[int, ...], ...]:
    """Rank-ordered lines cycling through the ranking to maximise coverage."""
    pool = len(scores)
    ranked = sorted(range(pool), key=lambda j: (-float(scores[j]), j))
    # Shift by one rank on each wrap so a pool divisible by six cannot repeat.
    lines = tuple(
        tuple(sorted(ranked[(6 * k + 6 * k // pool + i) % pool] + 1 for i in range(6)))
        for k in range(budget)
    )
    if len(set(lines)) != budget:
        raise ValueError("Coverage portfolio produced duplicate lines")
    return lines


def method_lines(method, scores, seed) -> tuple[tuple[int, ...], ...]:
    if method == "top6":
        return (top_line(scores),)
    if method == "weighted":
        p = np.asarray(scores, dtype=float)
        rng = np.random.Generator(np.random.PCG64(seed))
        chosen = rng.choice(len(p), 6, replace=False, p=p / p.sum())
        return (tuple(sorted(int(n) + 1 for n in chosen)),)
    return coverage_lines(scores, BUDGET[method])


def heuristic_lines(method, features) -> tuple[tuple[int, ...], ...]:
    """Hot/cold use the last-25 frequency; overdue uses capped recency."""
    column = FEATURE_COLUMNS.index("recency" if method == "overdue" else "freq_25")
    values = features.values[:, column]
    return (top_line(-values if method == "cold" else values),)


class NullModel:
    """Chance behaviour of the issued lines under a uniformly random outcome."""

    def __init__(self, pool: int, samples: int, seed: int):
        rng = np.random.Generator(np.random.PCG64(seed))
        chosen = np.argpartition(rng.random((samples, pool)), 6, axis=1)[:, :6]
        self.outcomes = np.zeros((samples, pool), dtype=np.int8)
        np.put_along_axis(self.outcomes, chosen, 1, axis=1)
        self.single = float(p_at_least(pool, 3))
        # One line's matches are hypergeometric: mean 36/N and exact variance.
        share = 6 / pool
        self.single_moments = (
            6 * share,
            6 * share * (1 - share) * (pool - 6) / (pool - 1),
        )
        self.cache = {}

    def _estimate(self, lines):
        # Chance depends only on how lines overlap, so relabel numbers in order
        # of first appearance; repeated structures reuse one estimate.
        labels = {}
        for line in lines:
            for number in line:
                labels.setdefault(number, len(labels))
        key = tuple(sorted(tuple(sorted(labels[n] for n in line)) for line in lines))
        if key not in self.cache:
            best = self.outcomes[:, np.asarray(key)].sum(axis=2).max(axis=1)
            self.cache[key] = (
                float(np.mean(best >= 3)),
                float(best.mean()),
                float(best.var()),
            )
        return self.cache[key]

    def probability(self, lines) -> float:
        """P(any issued line matches three or more)."""
        return self.single if len(lines) == 1 else self._estimate(lines)[0]

    def match_moments(self, lines) -> tuple[float, float]:
        """Mean and variance of the best line's matched numbers."""
        return self.single_moments if len(lines) == 1 else self._estimate(lines)[1:]


def poisson_binomial_tail(probabilities, observed: int) -> float:
    """Exact P(sum of independent Bernoulli(p_i) >= observed)."""
    distribution = np.zeros(len(probabilities) + 1)
    distribution[0] = 1.0
    for p in probabilities:
        distribution[1:] = distribution[1:] * (1 - p) + distribution[:-1] * p
        distribution[0] *= 1 - p
    return float(min(1.0, distribution[observed:].sum()))


def evaluate(config, draws, cache, bounds, chosen) -> dict:
    start, end = bounds["evaluation_start"], bounds["end"]
    sources = {}
    for family in config.families:
        marginals, converged = walk_forward(
            config,
            draws,
            cache,
            family,
            chosen[family]["params"],
            start,
            end,
            chosen[family]["setting"],
        )
        chosen[family]["evaluation_converged"] = converged
        sources[family] = marginals
    sources["frequency"] = {
        i: frequency_marginals(draws[:i], config.pool) for i in range(start, end)
    }
    null = NullModel(
        config.pool,
        config.null_samples,
        derive_seed(config.digest, "null", draws[start].draw_date, 0, 0),
    )
    predictions, outcomes, calibration = [], [], []
    uniform = np.full(config.pool, 6 / config.pool)
    for index in range(start, end):
        draw = draws[index]
        issued = []
        for source, marginals in sources.items():
            for method in MARGINAL_METHODS:
                seed = derive_seed(
                    config.digest, f"{source}:{method}", draw.draw_date, 1, 0
                )
                issued.append(
                    (source, method, method_lines(method, marginals[index], seed))
                )
        for method in RANDOM_METHODS:
            budget = BUDGET.get(method, 1)
            seed = derive_seed(config.digest, method, draw.draw_date, budget, 0)
            issued.append(
                ("uniform", method, uniform_portfolio(config.pool, budget, seed))
            )
        for method in HEURISTIC_METHODS:
            issued.append(
                ("heuristic", method, heuristic_lines(method, cache.features(index)))
            )
        for source, method, lines in issued:
            matched = [len(set(line) & set(draw.mains)) for line in lines]
            for line_index, line in enumerate(lines):
                predictions.append(
                    dict(
                        target_date=draw.draw_date.isoformat(),
                        source=source,
                        method=method,
                        line_index=line_index,
                        mains=" ".join(map(str, line)),
                        matched_mains=matched[line_index],
                    )
                )
            mean, variance = null.match_moments(lines)
            outcomes.append(
                dict(
                    target_date=draw.draw_date.isoformat(),
                    year=draw.draw_date.year,
                    source=source,
                    method=method,
                    lines=len(lines),
                    best_match=max(matched),
                    hit_3_plus=max(matched) >= 3,
                    hit_5_plus=max(matched) >= 5,
                    null_probability=null.probability(lines),
                    null_match_mean=mean,
                    null_match_variance=variance,
                )
            )
        outcome = labels(draw)
        for source, marginals in [("uniform", None), *sources.items()]:
            p = uniform if marginals is None else marginals[index]
            brier, loss = brier_and_log_loss(p, outcome)
            calibration.append(dict(source=source, brier=brier, log_loss=loss))
    return dict(predictions=predictions, outcomes=outcomes, calibration=calibration)


def summarise(outcomes, calibration) -> dict:
    groups = defaultdict(list)
    for row in outcomes:
        groups[(row["source"], row["method"])].append(row)
    summary, raw = [], {}
    for (source, method), rows in sorted(groups.items()):
        events = sum(r["hit_3_plus"] for r in rows)
        expected = [r["null_probability"] for r in rows]
        lower, upper = clopper_pearson(events, len(rows))
        key = f"{source}:{method}"
        raw["hit3:" + key] = poisson_binomial_tail(expected, events)
        matches = sum(r["best_match"] for r in rows)
        null_mean = sum(r["null_match_mean"] for r in rows)
        spread = sum(r["null_match_variance"] for r in rows) ** 0.5
        raw["match:" + key] = float(norm.sf((matches - null_mean) / spread))
        summary.append(
            dict(
                source=source,
                method=method,
                lines=rows[0]["lines"],
                draws=len(rows),
                hits_3_plus=events,
                rate=events / len(rows),
                expected_rate=float(np.mean(expected)),
                lift=events / len(rows) / float(np.mean(expected)),
                rate_lower=lower,
                rate_upper=upper,
                hits_5_plus=sum(r["hit_5_plus"] for r in rows),
                p_value=raw["hit3:" + key],
                mean_matches=matches / len(rows),
                expected_matches=null_mean / len(rows),
                match_lift=matches / null_mean,
                match_p_value=raw["match:" + key],
            )
        )
    # One Holm family covers both metrics for every source-method pair.
    adjusted = holm(raw)
    for row in summary:
        key = f"{row['source']}:{row['method']}"
        row["holm_p_value"] = adjusted["hit3:" + key]
        row["match_holm_p_value"] = adjusted["match:" + key]
        row["significant"] = (
            min(row["holm_p_value"], row["match_holm_p_value"]) < SIGNIFICANCE
        )
    yearly = defaultdict(list)
    for row in outcomes:
        yearly[(row["source"], row["method"], row["year"])].append(row)
    by_year = [
        dict(
            source=s,
            method=m,
            year=y,
            draws=len(rows),
            hits_3_plus=sum(r["hit_3_plus"] for r in rows),
            rate=sum(r["hit_3_plus"] for r in rows) / len(rows),
            expected_rate=float(np.mean([r["null_probability"] for r in rows])),
        )
        for (s, m, y), rows in sorted(yearly.items())
    ]
    scores = defaultdict(list)
    for row in calibration:
        scores[row["source"]].append((row["brier"], row["log_loss"]))
    calibrated = [
        dict(
            source=s,
            draws=len(v),
            brier=float(np.mean([b for b, _ in v])),
            log_loss=float(np.mean([loss for _, loss in v])),
        )
        for s, v in sorted(scores.items())
    ]
    return dict(summary=summary, yearly=by_year, calibration=calibrated)


def best(summary) -> dict:
    """Most winning numbers matched relative to chance, then the 3-plus lift."""
    return max(
        summary, key=lambda r: (r["match_lift"], r["lift"], -r["p_value"], r["source"])
    )


def training_description(config) -> str:
    window = (
        "all earlier draws of the regime"
        if config.training_window is None
        else f"the latest {config.training_window} earlier draws of the regime"
    )
    if config.pooled_regimes:
        window += " plus all draws of " + ", ".join(config.pooled_regimes)
    return window


def findings(config, bounds, draws, chosen, results) -> str:
    summary = results["summary"]
    top = best(summary)
    single = Fraction(p_at_least(config.pool, 3))
    winners = [r for r in summary if r["significant"]]
    start, end = draws[bounds["evaluation_start"]], draws[-1]
    lines = [
        "# Phase 7 study findings",
        "",
        f"- Config digest: `{config.digest}`",
        f"- Snapshot digest: `{config.snapshot_digest}`",
        f"- Regime: {config.rule_code} (pool {config.pool})",
        f"- Training data: {training_description(config)}",
        f"- Evaluation window: {start.draw_date} to {end.draw_date} "
        f"({bounds['end'] - bounds['evaluation_start']} draws); tuning used the "
        f"{bounds['evaluation_start'] - bounds['tuning_start']} draws before it.",
        f"- Exact random one-line 3-plus rate: {float(single):.5f} "
        f"(1 in {float(1 / single):.1f}).",
        "",
        "## Verdict",
        "",
    ]
    if winners:
        names = ", ".join(f"{r['source']}/{r['method']}" for r in winners)
        lines.append(
            f"Statistically distinguishable from random after Holm correction "
            f"over {2 * len(summary)} tests: {names}. Treat as a lead for "
            "prospective confirmation, not as proof."
        )
    else:
        lines.append(
            f"No model or method beat random selection after Holm correction over "
            f"{2 * len(summary)} tests (3-plus rate and numbers matched). This is "
            "the finding: no demonstrated advantage."
        )
    lines += [
        "",
        f"Best observed (most numbers matched vs chance): **{top['source']}/"
        f"{top['method']}**, {top['mean_matches']:.3f} numbers per draw vs "
        f"{top['expected_matches']:.3f} by chance (Holm p "
        f"{top['match_holm_p_value']:.3f}); {top['hits_3_plus']} 3-plus hits in "
        f"{top['draws']} draws (rate {top['rate']:.4f} vs random "
        f"{top['expected_rate']:.4f}, Holm p {top['holm_p_value']:.3f}). The best "
        f"of {len(summary)} is expected to look lucky; rely on the Holm values.",
        "",
        "## Tuned settings (chosen on pre-evaluation blocks only)",
        "",
    ]
    lines += [
        f"- {family}: `{value['setting']}`"
        + ("" if value.get("evaluation_converged", True) else " (convergence warning)")
        for family, value in chosen.items()
    ]
    lines += [
        "",
        "## Results by source and method",
        "",
        "| Source | Method | Lines | Draws | Matched | Chance | 3+ hits | Rate "
        "| Random | Holm p (matched / 3+) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r['source']} | {r['method']} | {r['lines']} | {r['draws']} | "
        f"{r['mean_matches']:.3f} | {r['expected_matches']:.3f} | "
        f"{r['hits_3_plus']} | {r['rate']:.4f} | {r['expected_rate']:.4f} | "
        f"{r['match_holm_p_value']:.3f} / {r['holm_p_value']:.3f} |"
        for r in sorted(summary, key=lambda r: (-r["match_lift"], -r["lift"]))
    ]
    lines += [
        "",
        "## Probability calibration (lower is better; uniform is the reference)",
        "",
        "| Source | Brier | Log loss |",
        "|---|---:|---:|",
    ]
    lines += [
        f"| {r['source']} | {r['brier']:.6f} | {r['log_loss']:.6f} |"
        for r in results["calibration"]
    ]
    lines += [
        "",
        "## Reading these results",
        "",
        "- Matched is the mean count of winning main numbers on the best line per "
        "draw; Chance is that mean for the same number of random lines.",
        "- Random is the exact chance rate for the same lines, so portfolios are "
        "compared with their own (higher) chance rate.",
        "- Per-year rates are in `yearly.csv`; every issued line is in "
        "`predictions.csv` and every per-draw outcome in `evaluation.csv`.",
        "- No setting was chosen using evaluation draws; the evaluation window "
        "was fixed by date before tuning ran.",
        "",
    ]
    return "\n".join(lines)


def _csv(rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf8")


def run_study(
    config: StudyConfig,
    draws: list[ResearchDraw],
    output_root: Path,
    pooled: dict[str, list[ResearchDraw]] | None = None,
):
    """Tune, evaluate and write an immutable, content-addressed result folder."""
    if config.pool != draws[0].pool:
        raise ValueError("Configured pool differs from the draws")
    bounds = split(config, draws)
    extra = (
        pooled_rows(config, pooled or {}, draws[0].draw_date)
        if config.pooled_regimes
        else None
    )
    cache = FeatureCache(draws, extra)
    tuning, chosen = tune(config, draws, cache, bounds)
    results = evaluate(config, draws, cache, bounds, chosen)
    reported = summarise(results["outcomes"], results["calibration"])
    files = {
        "config.json": canonical_json(config.model_dump(mode="json")),
        "tuning.csv": _csv(tuning),
        "selected.json": canonical_json(chosen),
        "predictions.csv": _csv(results["predictions"]),
        "evaluation.csv": _csv(results["outcomes"]),
        "summary.csv": _csv(reported["summary"]),
        "yearly.csv": _csv(reported["yearly"]),
        "calibration.csv": _csv(reported["calibration"]),
        "findings.md": findings(config, bounds, draws, chosen, reported).encode(),
    }
    output = Path(output_root) / config.digest
    for name, body in files.items():
        write_once(output / name, body)
    manifest = {name: sha256(body) for name, body in files.items()}
    write_once(output / "manifest.json", canonical_json(manifest))
    return output, reported


def _read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf8"))))


def compare_studies(folders: list[Path]) -> str:
    """One table across studies that share an evaluation window."""
    rows = []
    for folder in map(Path, folders):
        config = StudyConfig.model_validate_json((folder / "config.json").read_text())
        summary = _read_csv(folder / "summary.csv")
        calibration = {
            r["source"]: float(r["log_loss"])
            for r in _read_csv(folder / "calibration.csv")
        }
        models = [r for r in summary if r["source"] in config.families]
        top = max(models, key=lambda r: (float(r["match_lift"]), float(r["lift"])))
        single = max(
            (r for r in models if int(r["lines"]) == 1), key=lambda r: float(r["rate"])
        )
        ten = max(
            (r for r in models if r["method"] == "coverage10"),
            key=lambda r: float(r["rate"]),
        )
        best_loss = min(calibration[f] for f in config.families)
        rows.append(
            f"| {training_description(config)} | {top['source']}/{top['method']} "
            f"{float(top['mean_matches']):.3f} vs {float(top['expected_matches']):.3f} "
            f"(Holm {float(top['match_holm_p_value']):.2f}) | "
            f"{single['source']}/{single['method']} {float(single['rate']):.1%} vs "
            f"{float(single['expected_rate']):.1%} | "
            f"{ten['source']} {float(ten['rate']):.1%} vs "
            f"{float(ten['expected_rate']):.1%} | "
            f"{best_loss - calibration['uniform']:+.5f} | "
            f"{sum(r['significant'] == 'True' for r in summary)} |"
        )
    return "\n".join(
        [
            "| Training data | Best by numbers matched (vs chance) | Best one-line 3+ "
            "(vs chance) | Best 10-line 3+ (vs chance) | Best model log loss minus "
            "uniform | Significant |",
            "|---|---|---|---|---|---:|",
            *rows,
            "",
        ]
    )
