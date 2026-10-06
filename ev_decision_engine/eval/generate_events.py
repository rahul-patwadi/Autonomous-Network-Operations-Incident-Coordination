"""Synthetic network-incident event generator for eval scenarios and test fixtures.

Usage:
    uv run python -m eval.generate_events -n 200 -o eval/events.json --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from schemas import Event, Message, TrustMetadata

INCIDENT_TYPES: tuple[str, ...] = (
    "network_partition",
    "gradient_sync_latency",
    "service_discovery_failure",
    "packet_loss",
    "bandwidth_saturation",
    "load_balancer_failure",
    "connection_timeout",
    "cross_region_latency_spike",
)

REGIONS: tuple[str, ...] = ("us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-south-1")

SOURCE_AGENTS: tuple[str, ...] = (
    "netflow-monitor",
    "synthetic-prober",
    "bgp-watcher",
    "lb-health-agent",
    "dns-checker",
)

# (low, high) latency_ms for types where latency is relevant; None -> no latency reading.
LATENCY_RANGES: dict[str, tuple[float, float] | None] = {
    "network_partition": None,
    "gradient_sync_latency": (400.0, 5000.0),
    "service_discovery_failure": None,
    "packet_loss": (30.0, 400.0),
    "bandwidth_saturation": (50.0, 600.0),
    "load_balancer_failure": None,
    "connection_timeout": (1000.0, 30000.0),
    "cross_region_latency_spike": (250.0, 2500.0),
}

# Scenario profiles: ranges for each randomized field. "scale" stretches latency toward the
# high end of the type's range for clear incidents and the low end for noise.
PROFILES: dict[str, dict[str, object]] = {
    "suppress": {
        "severity": (0.05, 0.30),
        "confidence": (0.20, 0.55),
        "fp_rate": (0.45, 0.90),
        "corroborating": (0, 1),
        "ttl": (30, 300),
        "criticality": (0.05, 0.40),
        "directly_observed": 0.2,
        "latency_scale": (0.0, 0.25),
    },
    "escalate": {
        "severity": (0.75, 1.00),
        "confidence": (0.80, 0.99),
        "fp_rate": (0.01, 0.12),
        "corroborating": (3, 8),
        "ttl": (600, 3600),
        "criticality": (0.70, 1.00),
        "directly_observed": 0.9,
        "latency_scale": (0.7, 1.0),
    },
    "ambiguous": {
        "severity": (0.35, 0.75),
        "confidence": (0.45, 0.80),
        "fp_rate": (0.12, 0.45),
        "corroborating": (1, 3),
        "ttl": (120, 900),
        "criticality": (0.35, 0.80),
        "directly_observed": 0.5,
        "latency_scale": (0.25, 0.7),
    },
}

# Roughly 25% suppress, 30% escalate, 45% ambiguous.
CATEGORY_WEIGHTS: dict[str, float] = {"suppress": 0.25, "escalate": 0.30, "ambiguous": 0.45}


def _node_pair(rng: random.Random, event_type: str) -> str | None:
    if event_type == "service_discovery_failure" and rng.random() < 0.3:
        return None  # registry-level failure, not tied to a specific pair
    a, b = rng.sample(range(1, 21), 2)
    return f"node-{a} <-> node-{b}"


def _latency(rng: random.Random, event_type: str, scale: tuple[float, float]) -> float | None:
    bounds = LATENCY_RANGES[event_type]
    if bounds is None:
        return None
    low, high = bounds
    frac = rng.uniform(*scale)
    return round(low + (high - low) * frac, 1)


def generate_message(
    rng: random.Random,
    category: str | None = None,
    event_type: str | None = None,
    now: datetime | None = None,
) -> Message:
    """Generate one Message. Category and event_type are randomized when not given."""
    category = category or rng.choices(
        list(CATEGORY_WEIGHTS), weights=list(CATEGORY_WEIGHTS.values())
    )[0]
    event_type = event_type or rng.choice(INCIDENT_TYPES)
    p = PROFILES[category]
    now = now or datetime.now(UTC)

    corr_lo, corr_hi = p["corroborating"]  # type: ignore[misc]
    ttl_lo, ttl_hi = p["ttl"]  # type: ignore[misc]

    event = Event(
        event_type=event_type,
        region=rng.choice(REGIONS),
        severity=round(rng.uniform(*p["severity"]), 3),  # type: ignore[misc]
        timestamp=now - timedelta(seconds=rng.randint(0, 3600)),
        correlation_id=str(uuid.UUID(int=rng.getrandbits(128), version=4)),
        affected_node_pair=_node_pair(rng, event_type),  # type: ignore[call-arg]
        latency_ms=_latency(rng, event_type, p["latency_scale"]),  # type: ignore[arg-type,call-arg]
    )
    trust = TrustMetadata(
        source_agent=rng.choice(SOURCE_AGENTS),
        confidence=round(rng.uniform(*p["confidence"]), 3),  # type: ignore[misc]
        historical_false_positive_rate=round(rng.uniform(*p["fp_rate"]), 3),  # type: ignore[misc]
        is_directly_observed=rng.random() < p["directly_observed"],  # type: ignore[operator]
        corroborating_source_count=rng.randint(corr_lo, corr_hi),
        ttl_seconds=rng.randint(ttl_lo, ttl_hi),
        asset_criticality=round(rng.uniform(*p["criticality"]), 3),  # type: ignore[misc]
    )
    return Message(event=event, trust=trust)


def generate_events(n: int, seed: int | None = None) -> list[Message]:
    """Generate n messages, cycling through incident types so all 8 are well represented."""
    rng = random.Random(seed)
    now = datetime.now(UTC)
    return [
        generate_message(rng, event_type=INCIDENT_TYPES[i % len(INCIDENT_TYPES)], now=now)
        for i in range(n)
    ]


def write_events(messages: list[Message], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [m.model_dump(mode="json") for m in messages]
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic network incident events.")
    parser.add_argument("-n", "--count", type=int, default=100, help="number of events")
    parser.add_argument("-o", "--output", type=Path, default=Path("eval/events.json"))
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    args = parser.parse_args()

    messages = generate_events(args.count, seed=args.seed)
    write_events(messages, args.output)
    print(f"Wrote {len(messages)} events to {args.output}")


if __name__ == "__main__":
    main()
