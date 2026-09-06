---
id: DEC-0001
title: VIP rate-limit mechanism choice
kind: architecture
status: proposed
owner: pending-human
date: 2025-01-01
change: CHG-001-vip-quoting
affects:
  capabilities:
    - security.ratelimit
  spec_refs:
    - docs/spec/security/ratelimit.md
supersedes: null
superseded_by: null
---

# VIP rate-limit mechanism choice

## Context

CHG-001-vip-quoting requires that VIP users receive special treatment in the
Rate Limiter so they are not subject to the general limits (CR-002). The
requester explicitly deferred the mechanism selection to the team (CR-004),
and the request lists three mutually exclusive candidate mechanisms (CR-003):

1. An effectively infinite quota for VIP users.
2. A separate, enlarged token pool (e.g. 10x the normal amount).
3. Out-of-order servicing with priority for VIP users.

## Forks (open — no choice made)

- **Fork A — infinite quota.** VIP keys bypass capacity entirely. Simplest,
  but risks resource exhaustion / DoS via fabricated VIP keys.
- **Fork B — enlarged token pool.** VIP keys get a larger `capacity` (e.g.
  10x). Requires a defined baseline "normal" quota value (CR-005 unknown).
- **Fork C — priority servicing.** VIP keys are serviced out-of-order. Requires
  a priority queue / reordering mechanism in the limiter.

## Related unknowns

- How VIP users are identified (account flag, tier, API key class) — CR-005.
- The baseline "normal" quota value the 10x factor would apply to — CR-005.

## Decision

PENDING HUMAN DECISION. Do not implement any fork until one is accepted.
