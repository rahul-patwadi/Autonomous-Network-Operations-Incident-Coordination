import policy
from cost_model import communication_cost, risk, task_benefit
from policy import decide
from schemas import Action
from tests.helpers import make_message


def test_chosen_action_is_argmax_of_scores() -> None:
    m = make_message(confidence=0.9, severity=0.9, criticality=0.8, corroborating=3)
    d = decide(m)
    best = max(d.action_scores, key=lambda a: d.action_scores[a])
    assert d.chosen_action is best


def test_scores_match_ev_formula() -> None:
    m = make_message(confidence=0.7, severity=0.6)
    d = decide(m)
    a = Action.SEND
    expected = task_benefit(a, m) - communication_cost(a, m) - risk(a, m)
    assert d.action_scores[a] == expected


def test_ev_floor_falls_back_to_suppress() -> None:
    m = make_message(confidence=0.1, severity=0.1, criticality=0.1)
    d = decide(m)
    assert max(d.action_scores.values()) < policy.EV_FLOOR
    assert d.chosen_action is Action.SUPPRESS


def test_remediation_wins_when_below_risk_threshold() -> None:
    m = make_message(confidence=0.95, severity=0.8, criticality=0.2, corroborating=4)
    d = decide(m)
    assert risk(Action.PROPOSE_REMEDIATION, m) <= policy.HIGH_IMPACT_RISK_THRESHOLD
    assert d.chosen_action is Action.PROPOSE_REMEDIATION


def test_remediation_risk_scales_with_criticality_and_blast_radius() -> None:
    m = make_message(confidence=0.9, criticality=0.8)
    base = risk(Action.PROPOSE_REMEDIATION, m, blast_radius=1)
    assert risk(Action.PROPOSE_REMEDIATION, m, blast_radius=5) > base
    low_crit = make_message(confidence=0.9, criticality=0.1)
    assert risk(Action.PROPOSE_REMEDIATION, low_crit, blast_radius=1) < base


def test_high_impact_remediation_is_excluded_above_threshold() -> None:
    m = make_message(confidence=0.9, severity=1.0, criticality=1.0, corroborating=2)
    d = decide(m, blast_radius=12)
    assert risk(Action.PROPOSE_REMEDIATION, m, blast_radius=12) > policy.HIGH_IMPACT_RISK_THRESHOLD
    assert d.action_scores[Action.PROPOSE_REMEDIATION] == float("-inf")
    # Remediation is excluded; approval stays a finite candidate. Communication actions are
    # unscaled, so ESCALATE can still outscore it.
    assert d.chosen_action is not Action.PROPOSE_REMEDIATION
    assert d.action_scores[Action.REQUEST_APPROVAL] > float("-inf")


def test_same_incident_with_narrow_blast_radius_is_not_excluded() -> None:
    m = make_message(confidence=0.9, severity=1.0, criticality=1.0, corroborating=2)
    d = decide(m, blast_radius=1)
    assert d.action_scores[Action.PROPOSE_REMEDIATION] > float("-inf")
