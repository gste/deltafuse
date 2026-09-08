---
change: CHG-011-remove-burst
status: accepted
slices:
  - SLICE-01
removed:
  - REQ-RL-05
---

# Spec Delta — CHG-011-remove-burst

Scope: SLICE-01 (Remove burst_allowance from Rate Limiter)

## REMOVED

- REQ-RL-05 Burst retry — removed from `docs/spec/security/ratelimit.md`. The
  Rate Limiter no longer exposes `burst_allowance`; burst retry is out of scope.

## UNCHANGED

- REQ-RL-01 Capacity and refill — unchanged.
- REQ-RL-02 Consume — unchanged.
- REQ-RL-03 Unknown keys — unchanged.
- REQ-RL-04 is_blocked — unchanged.

## Notes

- No requirements added or modified. The removal of REQ-RL-05 is a deletion of
  a stale clause; observable rate-limiting behavior beyond burst is unchanged.
- Public constructor, tests, docs, and capabilities catalog updates are handled
  in later phases; this delta governs the normative specification only.
