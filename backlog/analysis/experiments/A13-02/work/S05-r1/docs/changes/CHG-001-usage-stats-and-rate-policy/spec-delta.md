---
change: CHG-001-usage-stats-and-rate-policy
status: proposed
slices:
  - SLICE-01
added:
  - docs/spec/security/ratelimit.md
modified:
  - docs/spec/security/ratelimit.md
removed: []
---

# Spec Delta — CHG-001-usage-stats-and-rate-policy

## ADDED

### docs/spec/security/ratelimit.md

- REQ-RL-05 WHEN a key has been rejected by the rate policy THE limiter SHALL return `False` from `consume(key, tokens)` without deducting tokens, and `get_stats(key)` SHALL report `blocked_until` as an ISO-8601 UTC timestamp or `None` when not blocked.
- REQ-RL-06 WHEN the number of consecutive rejected consumes for a key reaches the rejection threshold THE rate policy SHALL set `blocked_until` to `now + block_duration_seconds` for that key.
- REQ-RL-07 WHEN `get_stats(key)` is called THE limiter SHALL return a dict with keys `total` (int), `successful` (int), `rejected` (int), `peak_load` (float, max calls per second), and `blocked_until` (ISO-8601 UTC string or `None`).
- REQ-RL-08 WHEN a consume is rejected due to token shortage OR policy blocking THE `rejected` counter in `get_stats(key)` SHALL increment by one.

## MODIFIED

### docs/spec/security/ratelimit.md

- REQ-RL-02 MODIFIED: consume(key, tokens) SHALL return `False` without deduction when the key is blocked by the rate policy, in addition to the existing token-shortage case; the policy-block case is governed by REQ-RL-05.
- REQ-RL-04 MODIFIED: is_blocked(key) SHALL return `True` while a key is within its policy block window (now < blocked_until) and `False` otherwise; the baseline no-penalty-lock behavior no longer applies once the policy is active.

## REMOVED

- None.
