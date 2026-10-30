"""Shared state for the incident-handling graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from schemas import Decision, Message


class IncidentState(TypedDict):
    message: Message
    decision: Decision | None
    proposed_fix: str | None
    proposed_tool: str | None
    proposed_tool_args: dict[str, Any] | None
    approval_status: str | None  # "pending" | "approved" | "rejected"
    execution_result: str | None
    log: Annotated[list[str], operator.add]


def new_state(message: Message) -> IncidentState:
    """Initial state for a message. TypedDict has no field defaults, so they live here."""
    return IncidentState(
        message=message,
        decision=None,
        proposed_fix=None,
        proposed_tool=None,
        proposed_tool_args=None,
        approval_status=None,
        execution_result=None,
        log=[],
    )
