"""LangGraph node functions. Each returns a partial state update."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.types import interrupt

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


SYSTEM_PROMPT = (
    "You are a network operations remediation assistant. Given an incident, propose ONE "
    "concrete remediation action and a one-sentence rationale. Be specific and concise. "
    "Do not invent details that aren't given."
)


def _incident_prompt(state: IncidentState) -> str:
    message = state["message"]
    event, trust = message.event, message.trust
    return (
        f"event_type: {event.event_type}\n"
        f"region: {event.region}\n"
        f"severity: {event.severity}\n"
        f"affected_node_pair: {event.affected_node_pair}\n"
        f"corroborating_source_count: {trust.corroborating_source_count}\n"
        f"asset_criticality: {trust.asset_criticality}"
    )


def response_node(state: IncidentState) -> dict[str, Any]:
    try:
        llm = ChatOllama(model="llama3.2")
        reply = llm.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(_incident_prompt(state))])
        fix = str(reply.content).strip()
        return {"proposed_fix": fix, "log": ["response: LLM proposed a fix"]}
    except Exception as exc:  # Ollama unreachable, model missing, etc. Never crash the graph.
        fix = f"placeholder remediation for {state['message'].event.event_type}"
        return {
            "proposed_fix": fix,
            "log": [f"response: LLM unavailable ({type(exc).__name__}); used placeholder"],
        }


def human_gate_node(state: IncidentState) -> dict[str, Any]:
    decision = state["decision"]
    action = decision.chosen_action.value if decision is not None else None
    # Pauses the graph; on resume, interrupt() returns the value passed to Command(resume=...).
    verdict = interrupt({"proposed_fix": state["proposed_fix"], "chosen_action": action})
    status = "approved" if verdict == "approved" else "rejected"
    outcome = "fix approved" if status == "approved" else "fix was rejected"
    return {"approval_status": status, "log": [f"human_gate: {outcome} (approval_status={status})"]}
