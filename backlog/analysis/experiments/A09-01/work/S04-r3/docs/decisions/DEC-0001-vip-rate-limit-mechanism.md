---
id: DEC-0001
title: VIP rate-limit exemption mechanism
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

## Context

CHG-001 requires that VIP users be exempt from the general rate-limit quotas
(CR-002). The request explicitly leaves the mechanism to the implementer and
lists three mutually exclusive approaches (CR-003). This Decision must select
exactly one; the others are not compatible with each other.

## Open Fork

The following options are mutually exclusive and require a human Decision:

1. **Infinite quota** — VIP keys receive an effectively unlimited token pool,
   so `consume()` always succeeds. Simplest, but removes all throttling for VIP.
2. **Enlarged token pool** — VIP keys draw from a separate, larger bucket
   (e.g. ~10x the normal capacity). Preserves some throttling while raising the
   ceiling.
3. **Out-of-order priority service** — VIP requests are serviced ahead of
   standard ones, changing ordering/precedence semantics, not just quota size.

## Consequences

- Each option changes the observable behavior of `security.ratelimit` and would
  require a corresponding normative edit to `docs/spec/security/ratelimit.md`.
- CR-005 (definition of "VIP") and CR-006 (current quota model) remain unresolved
  and must be handled alongside this choice during specification.

## Recommendation

A human must choose one option. Do not implement until this Decision is accepted.
