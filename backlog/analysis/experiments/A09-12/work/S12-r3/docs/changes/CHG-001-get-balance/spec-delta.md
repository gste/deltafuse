---
change: CHG-001-get-balance
status: accepted
slices:
  - SLICE-01
added:
  - REQ-RL-05 get_balance — read-only balance accessor under security.ratelimit
  - REQ-RL-06 get_balance unknown keys — unknown-key balance equals initial capacity
modified:
  - docs/spec/security/ratelimit.md
removed: []
---

# Specification Delta — CHG-001-get-balance

## Added

- REQ-RL-05 get_balance — read-only balance accessor under security.ratelimit
- REQ-RL-06 get_balance unknown keys — unknown-key balance equals initial capacity

## Modified

- docs/spec/security/ratelimit.md — added REQ-RL-05 and REQ-RL-06 describing get_balance(key) behavior

## Removed

- (none)

## Notes

- get_balance(key) returns the current non-negative integer token count available for the next consume call without deducting tokens or creating any side-effecting deduction. For an unknown key it returns the initial capacity after normal key initialization. These requirements satisfy CR-001 through CR-005; no further normative behavior remains only in the request.
