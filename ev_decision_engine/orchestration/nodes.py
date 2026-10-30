"""LangGraph node functions. Each returns a partial state update."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.types import interrupt

from orchestration.state import IncidentState
from orchestration.tools import REMEDIATION_TOOLS, TOOLS_BY_NAME
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
    "You are a network operations remediation assistant. Given an incident, select the single "
    "most appropriate remediation tool by calling it with arguments taken from the incident. "
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
    """Select (but do not execute) a remediation tool."""
    try:
        llm = ChatOllama(model="llama3.2").bind_tools(REMEDIATION_TOOLS)
        reply = llm.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(_incident_prompt(state))])
        if not reply.tool_calls:
            raise ValueError("LLM returned no tool call")
        call = reply.tool_calls[0]
        if call["name"] not in TOOLS_BY_NAME:
            raise ValueError(f"LLM selected unknown tool {call['name']!r}")
        args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
        return {
            "proposed_tool": call["name"],
            "proposed_tool_args": call["args"],
            "proposed_fix": f"{call['name']}({args})",
            "log": [f"response: LLM selected tool {call['name']}"],
        }
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


def execute_node(state: IncidentState) -> dict[str, Any]:
    if state["approval_status"] != "approved":
        return {"log": ["execute: fix not approved; no action taken"]}
    tool_name = state["proposed_tool"]
    if tool_name is None:
        return {"log": ["execute: approved but no tool was selected; no action taken"]}
    result = str(TOOLS_BY_NAME[tool_name].invoke(state["proposed_tool_args"] or {}))
    return {"execution_result": result, "log": [f"execute: {result}"]}
