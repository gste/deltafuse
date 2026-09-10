# Request: Add IPv6 support to security.ip_filter (CHG-061)

## Summary

The user requests adding IPv6 address support to the `security.ip_filter` capability. Analysis indicates this request duplicates CHG-042 (rejected a month ago by the architectural committee on the grounds that current infrastructure does not support IPv6 and the network stack must first be updated — task INFRA-789, status: not-started). An alternative request CHG-055 (similar functionality) was superseded by CHG-060, which includes a full overhaul of ip_filter with CIDR notation support. The request cannot be reproduced in the current environment because the IPv6 test stand is disabled.

## Claims

### CR-001 — Observation
The user request (docs/intake/S09.md) asks to add IPv6 address support to capability `security.ip_filter`.

### CR-002 — Observation
The request is a duplicate of CHG-042, which was rejected a month ago by the architectural committee. Justification: current infrastructure does not support IPv6; the network stack must first be updated (task INFRA-789, status: not-started).

### CR-003 — Observation
An alternative request CHG-055 (similar functionality) was superseded by CHG-060, which includes a full overhaul of ip_filter with CIDR notation support.

### CR-004 — Observation
The request cannot be reproduced in the current environment because the IPv6 test stand is disabled.

### CR-005 — Expectation
Expected outcome: justified closure with provenance (references to CHG-042, CHG-055, CHG-060, INFRA-789).

### CR-006 — Constraint
Do not implement IPv6 support in `security.ip_filter` until the network stack is updated (INFRA-789) or the work is otherwise explicitly authorized.

### CR-007 — Hypothesis
The desired IPv6 functionality may be covered by CHG-060 (full ip_filter overhaul with CIDR notation); this requires verification against CHG-060's scope before closure.

### Unknowns
- Whether CHG-060's CIDR overhaul explicitly includes IPv6 addresses (not confirmed from this intake).
- Whether INFRA-789 has progressed since its not-started status was recorded.
