"""
nan_loss_walkthrough.py

Walks through a single NAN_LOSS training-job incident as it evolves from one
low-confidence signal to a corroborated one, and shows how policy.decide()'s
output changes in response.

Run with:
    uv run python examples/nan_loss_walkthrough.py
"""

from datetime import UTC, datetime

from cost_model import estimate_p_real
from policy import decide
from schemas import Event, Message, TrustMetadata

EVENT = Event(
    event_type="NAN_LOSS",
    region="us-east-1",
    severity=0.75,
    timestamp=datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC),
    correlation_id="train-job-4471",
)

# v1: a single low-confidence signal, not yet corroborated.
TRUST_V1 = TrustMetadata(
    source_agent="loss-monitor-1",
    confidence=0.6,
    historical_false_positive_rate=0.1,
    is_directly_observed=True,
    corroborating_source_count=1,
    ttl_seconds=300,
    asset_criticality=0.6,
)

# v2: the same event, after correlation brought in a second independent
# source confirming the same incident.
TRUST_V2 = TRUST_V1.model_copy(update={"corroborating_source_count": 2})

MESSAGE_V1 = Message(event=EVENT, trust=TRUST_V1)
MESSAGE_V2 = Message(event=EVENT, trust=TRUST_V2)


def show(label: str, message: Message) -> None:
    p_real = estimate_p_real(message)
    decision = decide(message)

    print(f"--- {label} ---")
    print(f"corroborating_source_count = {message.trust.corroborating_source_count}")
    print(f"P(real incident) ~= {p_real:.3f}")
    print("EV per candidate action:")
    for action, score in decision.action_scores.items():
        print(f"  {action.value:<20} {score:.3f}")
    print(f"Chosen action: {decision.chosen_action.value}")
    print(f"Explanation: {decision.explanation}")
    print()


if __name__ == "__main__":
    show("v1: single low-confidence signal", MESSAGE_V1)
    show("v2: after correlation (2 corroborating sources)", MESSAGE_V2)
