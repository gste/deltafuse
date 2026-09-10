---
change: CHG-001-usage-stats-and-rate-policy
status: accepted
slices:
  - SLICE-01
  - SLICE-02
---

# spec-delta: CHG-001-usage-stats-and-rate-policy

## SLICE-01 (monitoring.usage_stats)

### ADDED

- `docs/spec/monitoring/usage_stats.md` — new capability spec for per-key usage statistics.
- REQ-US-01 Per-key tracking: total, successful, rejected `consume` calls, and peak load (max calls in any one-second window).
- REQ-US-02 `get_stats(key)` returns a dict with `total`, `successful`, `rejected`, `peak_calls_per_second`.
- REQ-US-03 Rejection accounting: rejections from token shortage and policy blocking both count under `rejected`; policy-blocked keys expose `blocked_until`.
- REQ-US-04 Peak load resolution: maximum calls in any single one-second fixed bucket using the limiter's monotonic clock.

### MODIFIED

- None.

### REMOVED

- None.

## SLICE-02 (security.rate_policy)

### ADDED

- None yet. Blocked on Decision for CR-005/CR-013 (threshold semantics: consecutive vs cumulative).

### MODIFIED

- `docs/spec/security/ratelimit.md` — REQ-RL-05 and REQ-RL-06 already encode the auto-block contract; confirmed as normative baseline.

### REMOVED

- None.
