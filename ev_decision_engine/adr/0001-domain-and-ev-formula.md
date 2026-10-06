# ADR-0001: Domain and EV formula

## Status

Accepted

## Context

The system decides how to handle incoming incident signals on a simulated multi-region
Kubernetes platform: whether to stay silent, ask for verification, notify, escalate,
broadcast, propose a fix, or request approval for a fix. Signals arrive from automated
monitors with uneven reliability, so each one carries trust metadata (confidence,
historical false-positive rate, corroboration, TTL, asset criticality) alongside the event.

The domain is network operations incident coordination only. The system handles eight
incident types, carried as string values of `Event.event_type`:

| Type                         | Description                                                |
| ---------------------------- | ---------------------------------------------------------- |
| `network_partition`          | Nodes or zones cannot reach each other                     |
| `gradient_sync_latency`      | Elevated latency on distributed synchronization traffic    |
| `service_discovery_failure`  | Service registry/DNS lookups failing or stale              |
| `packet_loss`                | Sustained packet drop on a link or path                    |
| `bandwidth_saturation`       | Link or egress capacity exhausted                          |
| `load_balancer_failure`      | Load balancer unhealthy or misrouting                      |
| `connection_timeout`         | Connections failing to establish or completing too slowly  |
| `cross_region_latency_spike` | Inter-region round-trip time well above baseline           |

Some events also carry `affected_node_pair` and `latency_ms`, which apply only to types
where they are meaningful.

A fixed rule table (e.g. "severity > 0.8 means escalate") cannot trade off notification
cost against the cost of missing an incident, and gives no principled way to discount
unreliable sources.

## Decision

Score every candidate action with an expected-value formula and pick the highest:

```
EV(action) = TaskBenefit(action) - CommunicationCost(action) - Risk(action)
```

- **TaskBenefit** = `P(real) * severity * CATCH_VALUE[action]`. The value of the action
  if the incident is real.
- **CommunicationCost** = `COMM_COST[action]`. A flat interruption cost, independent of
  whether the incident is real.
- **Risk** = `false_positive_risk + silence_risk`.
  - `false_positive_risk = (1 - P(real)) * DISRUPTION_COST[action]`
  - `silence_risk = P(real) * severity * asset_criticality * blast_radius`, applied only
    to actions that leave a real incident unhandled (`SUPPRESS`, `VERIFY`).

`P(real)` is estimated from the trust metadata: confidence, raised by corroborating
sources with diminishing returns, lowered by the source's historical false-positive rate.

**Suppression carries a risk term.** `SUPPRESS` is not free. Its cost is the expected
cost of a real incident going undetected, which scales with severity, asset criticality,
and blast radius.

## Rationale

- One scalar per action makes trade-offs explicit and comparable. Escalating a
  low-confidence alert and ignoring a high-confidence one are scored on the same scale.
- If suppression scored zero, it would win whenever the other actions have any
  communication cost, so the engine would be biased toward silence. The silence-risk term
  makes the cost of a missed incident visible and lets criticality and blast radius
  push toward action.
- Scaling silence risk by criticality and blast radius means a suppressed incident on a
  critical asset touching many correlated events is penalized far more than a narrow one
  on a low-value asset.
- `VERIFY` also carries silence risk because it defers handling. It is cheap but not a
  substitute for acting on a likely-real, severe incident.
- Separating the three terms keeps each one independently testable and tunable.

## Consequences

- Every action's score depends on `P(real)`, so the quality of the trust heuristics
  directly affects decisions.
- Decisions are explainable per action as three numbers, which supports the explanation
  field on `Decision`.
- The formula is generic over incident type. Incident-type differences enter only through
  event fields (severity, criticality), not per-type branches.
- Weight tables are estimates; see ADR-0002.
- `blast_radius` is a caller-supplied input (default 1). Under-reporting it understates
  silence risk.
- High-risk remediation is routed to approval by a threshold in the policy layer rather
  than by the EV formula alone.
