"""Run the incident graph on one example message.

uv run python -m orchestration.run_graph
"""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

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


def main() -> None:
    graph = build_graph()
    config: RunnableConfig = {"configurable": {"thread_id": "incident-partition-4471"}}
    state = graph.invoke(new_state(EXAMPLE), config)

    for line in state["log"]:
        print(line)
    print(f"Proposed fix: {state['proposed_fix']}")
    decision = state["decision"]
    if decision is not None:
        print(f"Final chosen action: {decision.chosen_action.value}")


if __name__ == "__main__":
    main()
