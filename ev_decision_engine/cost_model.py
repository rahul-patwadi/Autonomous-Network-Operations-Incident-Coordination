"""
cost_model.py

Estimates TaskBenefit, CommunicationCost, and Risk for each candidate action,
given an incoming Message and optional context. These three functions are the
inputs to the EV formula in policy.py:

    EV(action) = TaskBenefit(action) - CommunicationCost(action) - Risk(action)

Design notes (see adr/0001-domain-and-scope.md for the full reasoning):
- Suppression is NOT free. Risk() includes a term for the cost of missing a
  real incident by staying silent, not just the cost of a false positive.
- "High impact" actions (PROPOSE_REMEDIATION on a critical/wide-blast-radius
  incident) route toward REQUEST_APPROVAL because their Risk term is scaled
  up by asset_criticality and blast radius.
"""

from schemas import Action, Message

# ---------------------------------------------------------------------------
# Tunable constants. Each of these is a judgment call, not a derived value.
# Document *why* a specific number was chosen in ADR-0002 once these are
# calibrated against the hand-labeled eval set.
# ---------------------------------------------------------------------------

# Flat communication cost per action (0.0-1.0 scale). Reflects interruption
# cost only, independent of whether the incident turns out to be real.
COMM_COST: dict[Action, float] = {
    Action.SUPPRESS: 0.0,
    Action.VERIFY: 0.05,
    Action.SEND: 0.10,
    Action.ESCALATE: 0.30,
    Action.BROADCAST: 0.60,
    Action.PROPOSE_REMEDIATION: 0.25,
    Action.REQUEST_APPROVAL: 0.35,
}

# Relative "value of catching a real incident" per action, used in
# TaskBenefit. SUPPRESS is 0 by definition -- suppressing does nothing even
# if the incident is real.
CATCH_VALUE: dict[Action, float] = {
    Action.SUPPRESS: 0.0,
    Action.VERIFY: 0.15,
    Action.SEND: 0.35,
    Action.ESCALATE: 0.80,
    Action.BROADCAST: 0.90,
    Action.PROPOSE_REMEDIATION: 0.75,
    Action.REQUEST_APPROVAL: 0.85,
}

# Relative "cost of acting on a false positive" per action, used in Risk.
# Suppress/verify barely disrupt anyone; broadcast disrupts the most people.
DISRUPTION_COST: dict[Action, float] = {
    Action.SUPPRESS: 0.0,
    Action.VERIFY: 0.05,
    Action.SEND: 0.10,
    Action.ESCALATE: 0.30,
    Action.BROADCAST: 0.70,
    Action.PROPOSE_REMEDIATION: 0.50,
    Action.REQUEST_APPROVAL: 0.20,
}

# Only these actions can leave an incident effectively unhandled, so only
# these carry the "cost of staying silent" risk term.
SILENT_ACTIONS = {Action.SUPPRESS, Action.VERIFY}


def estimate_p_real(message: Message) -> float:
    """
    Estimate P(real incident) from trust/provenance signals.

    Starts from the raw confidence score, then adjusts:
    - up, for each additional independent corroborating source
    - down, proportional to the source's historical false-positive rate
    """
    trust = message.trust
    p = trust.confidence

    # Each additional corroborating source beyond the first nudges P(real)
    # up, with diminishing returns.
    if trust.corroborating_source_count > 1:
        corroboration_boost = 1.0 - (0.85 ** (trust.corroborating_source_count - 1))
        p = p + (1.0 - p) * corroboration_boost

    # A source with a history of false positives should be trusted less,
    # even at face-value high confidence.
    p = p * (1.0 - trust.historical_false_positive_rate)

    return max(0.0, min(1.0, p))


def task_benefit(action: Action, message: Message) -> float:
    """Expected benefit of taking this action, given P(real incident)."""
    p_real = estimate_p_real(message)
    severity = message.event.severity
    return p_real * severity * CATCH_VALUE[action]


def communication_cost(action: Action, message: Message) -> float:
    """Cost of taking this action, independent of whether it's a real incident."""
    return COMM_COST[action]


def risk(action: Action, message: Message, blast_radius: int = 1) -> float:
    """
    Expected cost of getting this action wrong -- in either direction.

    false_positive_risk: cost of acting when the incident wasn't real.
    silence_risk: cost of staying silent (suppress/verify) when the incident
    WAS real -- this is the term that makes suppression non-free. Scales
    with severity, asset_criticality, and blast_radius (how many
    correlated events this incident touches), so a wide-reaching real
    incident that gets suppressed costs far more than a narrow one.
    """
    p_real = estimate_p_real(message)
    severity = message.event.severity
    criticality = message.trust.asset_criticality

    false_positive_risk = (1.0 - p_real) * DISRUPTION_COST[action]

    silence_risk = 0.0
    if action in SILENT_ACTIONS:
        cost_of_delayed_detection = severity * criticality * blast_radius
        silence_risk = p_real * cost_of_delayed_detection

    return false_positive_risk + silence_risk