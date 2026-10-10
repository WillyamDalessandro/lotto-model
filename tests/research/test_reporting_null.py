import pytest
from scipy.stats import binom
from test_inference import FROZEN

from lotto_model.research.inference import infer_primary, run_null_replicates
from lotto_model.research.protocol import build_protocol
from lotto_model.research.reporting import CHECK_REPLICATES, exact_null


def _primary(events, trials=230):
    return infer_primary([True] * events + [False] * (trials - events), 47)


def test_exact_null_p_value_and_gate():
    primary = _primary(6)
    p0 = primary["p0"]
    consistent = [5 / 230] * CHECK_REPLICATES
    null = exact_null(primary, dict(count=len(consistent), statistics=consistent))
    assert null["p_value"] == pytest.approx(binom.sf(5, 230, p0))
    assert null["final"] and null["refit_check_passed"]
    few = exact_null(primary, dict(count=10, statistics=consistent[:10]))
    assert not few["final"]


def test_refits_disagreeing_with_p0_are_rejected():
    primary = _primary(6)
    biased = [30 / 230] * CHECK_REPLICATES
    null = exact_null(primary, dict(count=len(biased), statistics=biased))
    assert not null["refit_check_passed"] and not null["final"]


def test_pipeline_refits_agree_with_exact_null(research_draws, tmp_path):
    draws = research_draws(282)
    protocol = build_protocol(draws, "a" * 64)
    nulls = run_null_replicates(FROZEN, protocol, draws, 4, tmp_path, 2)
    start, end = protocol.holdout
    null = exact_null(_primary(1, end - start), nulls)
    assert null["refit_check_passed"]
