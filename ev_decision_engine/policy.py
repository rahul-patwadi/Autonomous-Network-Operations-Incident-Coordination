"""
policy.py

The decision policy: computes EV(action) = TaskBenefit - CommunicationCost - Risk
for every candidate action, and picks the highest-scoring one. Falls back to
SUPPRESS if the best EV is still below a floor threshold (i.e. nothing is
clearly worth doing).

High-impact routing: PROPOSE_REMEDIATION is excluded as a candidate when its
Risk crosses HIGH_IMPACT_RISK_THRESHOLD -- in that case REQUEST_APPROVAL takes
over as the only path to remediation, regardless of confidence.
"""

from cost_model import communication_cost, estimate_p_real, risk, task_benefit
from schemas import Action, Decision, Message

# Below this EV, no action is considered worth taking -- default to SUPPRESS.
EV_FLOOR = 0.05

# Above this Risk, PROPOSE_REMEDIATION is not offered as a candidate;
# REQUEST_APPROVAL is used instead, regardless of how confident we are.
HIGH_IMPACT_RISK_THRESHOLD = 0.4

CANDIDATE_ACTIONS = [
    Action.SUPPRESS,
    Action.VERIFY,
    Action.SEND,
    Action.ESCALATE,
    Action.BROADCAST,
    Action.PROPOSE_REMEDIATION,
    Action.REQUEST_APPROVAL,
]


def decide(message: Message, blast_radius: int = 1) -> Decision:
    """Score every candidate action and return the highest-EV decision."""
    scores: dict[Action, float] = {}

    for action in CANDIDATE_ACTIONS:
        action_risk = risk(action, message, blast_radius=blast_radius)

        # High-impact remediation gets routed to approval instead of being
        # scored directly -- don't even let PROPOSE_REMEDIATION win if it
        # crosses the risk threshold.
        if action is Action.PROPOSE_REMEDIATION and action_risk > HIGH_IMPACT_RISK_THRESHOLD:
            scores[action] = float("-inf")
            continue

        ev = (
            task_benefit(action, message)
            - communication_cost(action, message)
            - action_risk
        )
        scores[action] = ev

    best_action = max(scores, key=lambda a: scores[a])
    best_ev = scores[best_action]

    if best_ev < EV_FLOOR:
        best_action = Action.SUPPRESS

    chosen_ev = scores[best_action]
    p_real = estimate_p_real(message)

    explanation = (
        f"Selected {best_action.value} with EV={chosen_ev:.3f} "
        f"(P(real)~{p_real:.2f}, "
        f"severity={message.event.severity:.2f})"
    )

    return Decision(
        chosen_action=best_action,
        action_scores=scores,
        explanation=explanation,
    )