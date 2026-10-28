# Autonomous Network Operations Incident Coordination

An expected-value (EV) decision engine that decides how a network-operations agent
system should react to incoming incident signals on a simulated multi-region network:
stay silent, verify, notify, escalate, broadcast, propose a fix, or ask for approval.

The project lives in [`ev_decision_engine/`](ev_decision_engine/).

## Incident types

`network_partition`, `gradient_sync_latency`, `service_discovery_failure`, `packet_loss`,
`bandwidth_saturation`, `load_balancer_failure`, `connection_timeout`,
`cross_region_latency_spike`.

## The EV formula

Every candidate action is scored and the highest score wins:

```
EV(action) = TaskBenefit(action) - CommunicationCost(action) - Risk(action)
```

- `TaskBenefit = P(real) * severity * CATCH_VALUE[action]`
- `CommunicationCost = COMM_COST[action]`
- `Risk = (1 - P(real)) * DISRUPTION_COST[action] * impact_scale + silence_risk`, where
  `impact_scale = 1 + criticality * blast_radius` for system-changing actions
  (`PROPOSE_REMEDIATION`, `REQUEST_APPROVAL`) and `1` otherwise, where `silence_risk`
  applies only to `SUPPRESS` and `VERIFY` and scales with severity, asset criticality
  and blast radius. Suppression is therefore not free.

`P(real)` is derived from confidence, corroborating sources and the source's historical
false-positive rate. If the best EV is below `EV_FLOOR`, the engine falls back to
`SUPPRESS`. `PROPOSE_REMEDIATION` is excluded when its risk exceeds
`HIGH_IMPACT_RISK_THRESHOLD`. Details: `adr/0001-domain-and-ev-formula.md`,
`adr/0002-cost-model-weights.md`.

## Agents

The decision engine serves five kinds of source agents, which appear as `source_agent` in
the trust metadata: `netflow-monitor`, `synthetic-prober`, `bgp-watcher`,
`lb-health-agent`, `dns-checker`. This repo implements the decision layer they report to,
not the agents themselves.

## Architecture

| File | Role |
| --- | --- |
| `schemas.py` | Pydantic models: `Event`, `TrustMetadata`, `Message`, `Decision`, `Action` |
| `cost_model.py` | `estimate_p_real`, `task_benefit`, `communication_cost`, `risk` |
| `policy.py` | `decide()`: scores all actions, applies `EV_FLOOR` and the high-impact rule |
| `api.py` | FastAPI: `POST /decide`, `GET /health` |
| `storage.py` | SQLite (SQLAlchemy) log of each message and decision |
| `eval/` | Event generator, labeled scenarios, eval runner |
| `tests/` | pytest suite |
| `adr/` | Architecture decision records |

## Running

```sh
cd ev_decision_engine
uv sync
uv run uvicorn api:app --reload          # serve the API
uv run python -m examples.network_partition_walkthrough
uv run python eval/run_eval.py eval/scenarios.json
uv run pytest && uv run ruff check . && uv run mypy .
```

`POST /decide` takes a `Message` (`event` + `trust`) and an optional `blast_radius` query
parameter, and returns a `Decision`. Candidates excluded by the high-impact rule have a
score of `-inf`, which is returned as `null`. Each decision is logged to
`incident_history.db`.

## Eval result

Decision agreement on the 36 labeled scenarios (`eval/run_eval.py`):

| Stage | Agreement |
| --- | --- |
| Baseline (`EV_FLOOR=0.05`, threshold `0.4`, no impact scaling) | 14/36 = **39%** |
| Calibrated (`EV_FLOOR=0.0`, threshold `0.55`, criticality/blast scaling on system-changing actions only) | 21/36 = **58%** |

The gain came from restricting the criticality/blast-radius scaling to system-changing
actions (remediation, approval) instead of applying it to communication actions. See
ADR-0002.

## Known limitations / future work

- **`VERIFY` is never selected.** The cost model rewards catching incidents but does not
  model the information value of reducing uncertainty before acting. Modeling that is
  future work.
- **`ttl_seconds` is unused in scoring**, so stale signals are not discounted (tracked by
  an `xfail` test).
