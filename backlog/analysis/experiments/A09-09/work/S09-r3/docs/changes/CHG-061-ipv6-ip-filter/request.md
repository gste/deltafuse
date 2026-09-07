# Request: Add IPv6 support to security.ip_filter (S09)

## Summary

User request (docs/intake/S09.md) asks to add IPv6 address support to the
`security.ip_filter` capability. Analysis of the request indicates it cannot
proceed as a net-new change because it collides with prior, already-resolved
Change records and cannot be reproduced in the current environment.

## Claims

### CR-001 — observation
The request is to add IPv6 address support to capability `security.ip_filter`.

### CR-002 — observation
The request appears to duplicate CHG-042, which was rejected one month ago by
the architectural committee. Justification: current infrastructure does not
support IPv6, and the network stack must be updated first (task INFRA-789,
status: not-started).

### CR-003 — observation
A related request, CHG-055 (similar functionality), was superseded by CHG-060,
which includes a full rewrite of `ip_filter` with CIDR notation support.

### CR-004 — observation
The request cannot be reproduced in the current environment because the IPv6
test stand is disabled.

### CR-005 — expectation
Expected outcome: justified closure with explicit provenance referencing
CHG-042, CHG-055, CHG-060, and INFRA-789.

### CR-006 — hypothesis (unresolved)
It is not established whether CHG-060's CIDR rewrite already covers IPv6, or
whether a new minimal IPv6 addition is warranted once INFRA-789 is complete.
This requires an architectural decision before the Change can be classified
final (duplicate / superseded / not-reproduced / deferred).

## Provenance

- Source: docs/intake/S09.md
- Related: CHG-042 (rejected), CHG-055 (superseded by CHG-060), CHG-060,
  INFRA-789 (not-started)

## Gate

Every material input statement from S09.md is represented by a claim above.
Product artifacts (spec, code, tests) remain unread and unchanged. A decision
is required to finalize classification; see decision file.
