---
id: DEC-0001-vip-quoting-mechanism
title: Mechanism for VIP rate-limit quota exemption
kind: product
status: proposed
owner: implementer
date: 2025-01-01
change: CHG-001-vip-quoting
affects:
  capabilities:
    - ratelimit
  spec_refs:
    - docs/spec/security/ratelimit.md
---

## Context

The request (docs/intake/S04.md) asks that VIP customers no longer suffer under
the general shared quota. The choice of mechanism is explicitly left to the
implementer ("Решите сами, как лучше"). Three candidate mechanisms were
proposed in the change claims:

- CR-003: effectively unlimited quota for VIP users.
- CR-004: a separate, enlarged token pool (~10x normal quota).
- CR-005: out-of-order / priority servicing for VIP users.

## Decisions

1. **Select one mechanism** for VIP quota handling. The three candidates are
   mutually exclusive in implementation; only one should be adopted.
2. **Resolve the VIP identity source**: how a request is classified as VIP is
   unspecified and must be decided (e.g. API key prefix, tenant flag, header).
3. **Bound "unlimited"**: if the unlimited mechanism is chosen, decide whether
   it is a true hard cap or a very large finite number to avoid resource-exhaustion.
4. **Fix the enlarged-pool value** if the ~10x mechanism is chosen; the 10x is
   an example, not a requirement.

## Consequences

- The chosen mechanism determines the ratelimit spec edit, the catalog entry,
  and the implementation/test scope for CHG-001.
- Leaving this unresolved blocks slice analysis because each candidate yields a
  different delta projection.
