from datetime import UTC, datetime

from schemas import Event, Message, TrustMetadata


def make_message(
    *,
    confidence: float = 0.8,
    severity: float = 0.5,
    criticality: float = 0.5,
    corroborating: int = 1,
    fp_rate: float = 0.0,
    event_type: str = "network_partition",
) -> Message:
    return Message(
        event=Event(
            event_type=event_type,
            region="us-east-1",
            severity=severity,
            timestamp=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
            correlation_id="test-1",
        ),
        trust=TrustMetadata(
            source_agent="netflow-monitor",
            confidence=confidence,
            historical_false_positive_rate=fp_rate,
            is_directly_observed=True,
            corroborating_source_count=corroborating,
            ttl_seconds=300,
            asset_criticality=criticality,
        ),
    )
