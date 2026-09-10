---
change: CHG-001-ratelimit-refactor
status: accepted
slices:
  - SLICE-01
---

# Specification Delta — CHG-001-ratelimit-refactor

## Summary

`requirement_delta: none`. The refactor is behavior-preserving; the external
token-bucket contract is unchanged. No normative spec text is added, modified,
or removed.

## Evidence of sufficiency

The existing accepted specification fully covers the observable contract the
refactor must preserve:

- `docs/spec/security/ratelimit.md` REQ-RL-01 (capacity/refill), REQ-RL-02
  (consume), REQ-RL-03 (unknown keys), REQ-RL-04 (is_blocked) remain the
  normative external contract. Internal module layout (`RateLimiter`,
  `RateLimiterBackend`, `InMemoryBackend`, validation location) is not part of
  the external contract and is therefore out of scope for the spec.

No behavioral, contract, policy, or invariant change is introduced by
SLICE-01; the spec requires no edit.
