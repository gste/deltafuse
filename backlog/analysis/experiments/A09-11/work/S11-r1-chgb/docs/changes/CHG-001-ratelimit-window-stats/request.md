# Request: Burst-window statistics for Rate Limiter (S11-B)

## Summary

The Rate Limiter service (`security.ratelimit`) needs a way to sample statistics for a key over the current burst window. A new method `get_window_stats(key)` must return a dictionary with fields `accepted`, `rejected`, and `remaining_tokens` for the key. Reading statistics must not consume tokens or change limits. For an unknown key, zero counters and the current remainder per key-initialization rules must be returned.

## Claims

### CR-001 — observation
The service `security.ratelimit` currently has window logic and token replenishment, but no documented method to read per-key statistics for the current window.

### CR-002 — expectation
`get_window_stats(key)` must return a dict with exactly the fields `accepted`, `rejected`, and `remaining_tokens` for the requested key.

### CR-003 — expectation
Window counters (`accepted`, `rejected`) are reset together with the token-replenishment logic of the existing limiter.

### CR-004 — constraint
Calling the statistics method must not consume tokens and must not modify limits.

### CR-005 — expectation
For an unknown key, the method returns zero counters (`accepted: 0`, `rejected: 0`) and the current remainder computed per the key-initialization rules.

### CR-006 — hypothesis
The remainder for an unknown key follows the same key-initialization rules already used by the limiter; the exact rule is not specified in the source and must be confirmed against the existing implementation.

## Unknowns

- Exact key-initialization rule for `remaining_tokens` (CR-006).
- Whether `accepted`/`rejected` are cumulative since last window reset or scoped to the current window only.
- Whether the method must exist on a specific class/interface and its expected signature/return type contract.
