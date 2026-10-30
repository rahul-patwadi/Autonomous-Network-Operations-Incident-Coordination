"""Run the incident graph on one example message.

uv run python -m orchestration.run_graph
"""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from orchestration.graph import build_graph
from orchestration.state import new_state
from schemas import Event, Message, TrustMetadata

EXAMPLE = Message(
    event=Event(
        event_type="network_partition",
        region="us-east-1",
        severity=0.9,
        timestamp=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        correlation_id="partition-4471",
        affected_node_pair="node-3 <-> node-7",
    ),
    trust=TrustMetadata(
        source_agent="netflow-monitor",
        confidence=0.99,
        historical_false_positive_rate=0.0,
        is_directly_observed=True,
        corroborating_source_count=3,
        ttl_seconds=300,
        asset_criticality=0.9,
    ),
)


def prompt_for_verdict() -> str:
    while True:
        answer = input("Approve this fix? [approve/reject]: ").strip().lower()
        if answer in ("approve", "reject"):
            return "approved" if answer == "approve" else "rejected"
        print("Please type 'approve' or 'reject'.")


def main() -> None:
    graph = build_graph()
    config: RunnableConfig = {"configurable": {"thread_id": "incident-partition-4471"}}
    result = graph.invoke(new_state(EXAMPLE), config)

    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        event = EXAMPLE.event
        print("--- Human review required ---")
        print(f"Incident: {event.event_type} in {event.region} (severity {event.severity})")
        print(f"Chosen action: {payload['chosen_action']}")
        print(f"Proposed fix: {payload['proposed_fix']}")
        result = graph.invoke(Command(resume=prompt_for_verdict()), config)

    for line in result["log"]:
        print(line)
    print(f"Approval status: {result['approval_status']}")


if __name__ == "__main__":
    main()
