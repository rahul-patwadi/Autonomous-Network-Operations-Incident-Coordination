"""LangGraph wiring: telemetry -> correlation -> decision -> (response -> human_gate)."""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orchestration.nodes import (
    correlation_node,
    decision_node,
    human_gate_node,
    response_node,
    telemetry_node,
)
from orchestration.state import IncidentState
from schemas import Action

REMEDIATION_ACTIONS = {Action.PROPOSE_REMEDIATION, Action.REQUEST_APPROVAL}

# Checkpointed state holds our schema types; allow-list them so msgpack can restore them.
CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("schemas", "Action"),
        ("schemas", "Decision"),
        ("schemas", "Event"),
        ("schemas", "Message"),
        ("schemas", "TrustMetadata"),
    ]
)


def route_after_decision(state: IncidentState) -> Literal["response", "end"]:
    decision = state["decision"]
    if decision is not None and decision.chosen_action in REMEDIATION_ACTIONS:
        return "response"
    return "end"


def build_graph() -> CompiledStateGraph[IncidentState, None, IncidentState, IncidentState]:
    builder = StateGraph(IncidentState)
    builder.add_node("telemetry", telemetry_node)
    builder.add_node("correlation", correlation_node)
    builder.add_node("decision", decision_node)
    builder.add_node("response", response_node)
    builder.add_node("human_gate", human_gate_node)

    builder.add_edge(START, "telemetry")
    builder.add_edge("telemetry", "correlation")
    builder.add_edge("correlation", "decision")
    builder.add_conditional_edges(
        "decision", route_after_decision, {"response": "response", "end": END}
    )
    builder.add_edge("response", "human_gate")
    builder.add_edge("human_gate", END)

    return builder.compile(checkpointer=MemorySaver(serde=CHECKPOINT_SERDE))
