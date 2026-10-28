import pytest

from cost_model import estimate_p_real, risk, task_benefit
from schemas import Action
from tests.helpers import make_message


def test_zero_corroboration_gets_no_boost() -> None:
    m = make_message(confidence=0.6, corroborating=0)
    assert estimate_p_real(m) == pytest.approx(0.6)


def test_corroboration_raises_p_real_with_diminishing_returns() -> None:
    p1 = estimate_p_real(make_message(confidence=0.6, corroborating=1))
    p2 = estimate_p_real(make_message(confidence=0.6, corroborating=2))
    p3 = estimate_p_real(make_message(confidence=0.6, corroborating=3))
    assert p1 < p2 < p3
    assert (p3 - p2) < (p2 - p1)


def test_false_positive_history_lowers_p_real() -> None:
    clean = estimate_p_real(make_message(fp_rate=0.0))
    noisy = estimate_p_real(make_message(fp_rate=0.5))
    assert noisy == pytest.approx(clean * 0.5)


def test_p_real_is_clamped_to_unit_interval() -> None:
    assert 0.0 <= estimate_p_real(make_message(confidence=1.0, corroborating=50)) <= 1.0
    assert estimate_p_real(make_message(confidence=0.0)) == 0.0


@pytest.mark.xfail(
    strict=True,
    reason="cost_model does not read ttl_seconds, so stale signals are not discounted",
)
def test_stale_signal_is_discounted() -> None:
    fresh = make_message()
    stale = fresh.model_copy(update={"trust": fresh.trust.model_copy(update={"ttl_seconds": 0})})
    assert estimate_p_real(stale) < estimate_p_real(fresh)


def test_max_severity_zero_confidence_has_no_benefit_or_silence_risk() -> None:
    m = make_message(confidence=0.0, severity=1.0, criticality=1.0)
    assert task_benefit(Action.BROADCAST, m) == 0.0
    assert risk(Action.SUPPRESS, m) == 0.0


def test_max_severity_scales_benefit_and_silence_risk() -> None:
    low = make_message(severity=0.2, criticality=1.0)
    high = make_message(severity=1.0, criticality=1.0)
    assert task_benefit(Action.ESCALATE, high) > task_benefit(Action.ESCALATE, low)
    assert risk(Action.SUPPRESS, high) > risk(Action.SUPPRESS, low)


def test_suppress_carries_nonzero_risk_when_severe() -> None:
    m = make_message(confidence=0.9, severity=0.95, criticality=0.9)
    assert risk(Action.SUPPRESS, m) > 0.0


def test_suppress_risk_grows_with_blast_radius() -> None:
    m = make_message(confidence=0.9, severity=0.9, criticality=0.9)
    assert risk(Action.SUPPRESS, m, blast_radius=5) > risk(Action.SUPPRESS, m, blast_radius=1)


def test_acting_actions_carry_no_silence_risk() -> None:
    m = make_message(confidence=1.0, severity=1.0, criticality=1.0)
    # p_real == 1 -> false-positive risk is zero, so any risk would be silence risk.
    assert risk(Action.ESCALATE, m, blast_radius=10) == 0.0
