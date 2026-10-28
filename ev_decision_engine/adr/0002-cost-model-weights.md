# ADR-0002: Cost model weights

## Status

Accepted (calibrated against the 36-scenario eval set)

## Context

The EV formula in ADR-0001 depends on three per-action weight tables in `cost_model.py`:

- `COMM_COST`: flat interruption cost of taking the action.
- `CATCH_VALUE`: relative value of the action when the incident is real.
- `DISRUPTION_COST`: relative cost of the action when the incident is a false positive.

All values are on a 0.0-1.0 relative scale. There is no historical incident data from
which to derive them, so they cannot yet be fit empirically.

## Decision

Treat the current values as hand-picked, reasoned estimates. They encode an ordering and
rough magnitudes, not measured quantities. They will be calibrated against the
hand-labeled evaluation set, and this ADR will be superseded or amended with the
calibrated values and the method used.

Current values:

| Action                | COMM_COST | CATCH_VALUE | DISRUPTION_COST |
| --------------------- | --------- | ----------- | --------------- |
| `SUPPRESS`            | 0.00      | 0.00        | 0.00            |
| `VERIFY`              | 0.05      | 0.15        | 0.05            |
| `SEND`                | 0.10      | 0.35        | 0.10            |
| `ESCALATE`            | 0.30      | 0.80        | 0.30            |
| `BROADCAST`           | 0.60      | 0.90        | 0.70            |
| `PROPOSE_REMEDIATION` | 0.25      | 0.75        | 0.50            |
| `REQUEST_APPROVAL`    | 0.35      | 0.85        | 0.20            |

## Calibration status

The weight tables are hand-picked estimates, to be calibrated against the 36-scenario
labeled evaluation set (`eval/scenarios.json`, run with `eval/run_eval.py`).

- **Baseline (measured):** with the initial values above, `EV_FLOOR = 0.05`,
  `HIGH_IMPACT_RISK_THRESHOLD = 0.4` and an unscaled false-positive term, decision
  agreement was **14/36 = 38.9% (~39%)**. Dominant failures: `VERIFY -> SUPPRESS` (8),
  `ESCALATE -> REQUEST_APPROVAL` (7), `SEND -> SUPPRESS` (2).
- **Calibration applied:** `EV_FLOOR` lowered to `0.0`, `HIGH_IMPACT_RISK_THRESHOLD`
  raised to `0.55`, and the false-positive risk term scaled by
  `impact_scale = 1 + asset_criticality * blast_radius` **only for system-changing
  actions** (`PROPOSE_REMEDIATION`, `REQUEST_APPROVAL`). Communication actions (`SEND`,
  `ESCALATE`, `BROADCAST`) keep `impact_scale = 1`. A first attempt that applied the
  scaling to every action scored 12/36 = 33.3%, because it penalized communication on
  critical assets and pushed decisions toward `REQUEST_APPROVAL`.
- **After calibration (measured):** **21/36 = 58.3% (~58%)**, up from the 38.9% baseline
  (+19.4 points). The change that drove the gain was restricting the criticality /
  blast-radius scaling to system-changing actions. Remaining errors: `VERIFY -> SUPPRESS`
  (7), `BROADCAST -> ESCALATE` (4), `SEND -> SUPPRESS` (2), `ESCALATE -> SUPPRESS` (1),
  `VERIFY -> SEND` (1).

## Rationale

Relative scale reasoning:

- **Audience size drives communication and disruption cost.** `BROADCAST` interrupts the
  most people, so it has the highest `COMM_COST` (0.60) and `DISRUPTION_COST` (0.70).
  `ESCALATE` targets a specific responder or tier (0.30 each), `SEND` is a routine
  notification (0.10), and `VERIFY` is an automated probe that interrupts no one (0.05).
- **Catch value rises with reach and urgency, with diminishing returns.** `BROADCAST`
  (0.90) catches only slightly more than `ESCALATE` (0.80), because most of the value is
  already realized once the right responder is engaged. The extra audience mostly adds
  disruption. This keeps `BROADCAST` reserved for cases where `P(real)`, severity, and
  criticality are all high.
- **`SUPPRESS` is zero on all three tables.** It does nothing, so it has no catch value
  and no communication or disruption cost. Its cost comes from the silence-risk term
  (ADR-0001), not from these tables.
- **`VERIFY` has small but nonzero catch value (0.15).** It gathers information and can
  lead to action, but does not itself resolve anything.
- **`PROPOSE_REMEDIATION` has high disruption (0.50) relative to its communication cost
  (0.25).** The message is modest, but acting on a false positive means a change is
  applied to a live system.
- **`REQUEST_APPROVAL` has lower disruption (0.20) than `PROPOSE_REMEDIATION` (0.50).**
  A human gate means a false positive is caught before it changes anything. It has a
  higher `COMM_COST` (0.35) because it blocks on a person's attention.

## Consequences

- Decision boundaries (when `SEND` gives way to `ESCALATE`, when `BROADCAST` becomes
  viable) are sensitive to these numbers. Until calibration, behavior should be treated
  as a reasonable default, not a validated one.
- The ordering constraints above should be preserved during calibration. Changes that
  invert them (e.g. `BROADCAST` cheaper than `ESCALATE`) need an explicit justification.
- Calibration requires the labeled evaluation set; the synthetic generator in
  `eval/generate_events.py` produces unlabeled inputs and does not substitute for it.
- Weights are global, not per incident type. If calibration shows type-specific
  differences, that needs a new decision.

## Known limitations / future work

- **`VERIFY` is never selected.** The cost model rewards catching incidents but does not
  model the information value of reducing uncertainty before acting, so `VERIFY` always
  scores below `SUPPRESS` or an acting option. Modeling the value of that information is
  future work. It accounts for most remaining eval errors (`VERIFY -> SUPPRESS`: 7).
- **`ttl_seconds` is unused in scoring.** It is captured in `TrustMetadata`, so a stale
  signal is scored the same as a fresh one. Staleness decay of `P(real)` is future work
  (`tests/test_cost_model.py::test_stale_signal_is_discounted` is an `xfail` marking this).
- When `PROPOSE_REMEDIATION` is excluded and every remaining EV is negative, the policy
  falls back to `SUPPRESS` even if `SUPPRESS` has the worst EV.
- `BROADCAST` is also never selected on the eval set (4 expected).
