"""LangGraph node functions. Each returns a partial state update."""

from __future__ import annotations

from typing import Any

from orchestration.state import IncidentState
from policy import decide


def telemetry_node(state: IncidentState) -> dict[str, Any]:
    event = state["message"].event
    return {"log": [f"telemetry: received {event.event_type} in {event.region}"]}


def correlation_node(state: IncidentState) -> dict[str, Any]:
    count = state["message"].trust.corroborating_source_count
    return {"log": [f"correlation: corroborating_source_count={count}"]}


def decision_node(state: IncidentState) -> dict[str, Any]:
    decision = decide(state["message"])
    return {
        "decision": decision,
        "log": [f"decision: chosen action {decision.chosen_action.value}"],
    }


def response_node(state: IncidentState) -> dict[str, Any]:
    # Stub: an LLM-generated fix is added later.
    fix = f"placeholder remediation for {state['message'].event.event_type}"
    return {"proposed_fix": fix, "log": [f"response: proposed fix '{fix}'"]}


def human_gate_node(state: IncidentState) -> dict[str, Any]:
    # Skeleton: auto-approves until a real human-in-the-loop interrupt is added.
    return {"approval_status": "approved", "log": ["human_gate: approval_status=approved"]}
