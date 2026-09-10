# Spec Delta — CHG-011-window-stats

Change: CHG-011-window-stats
Status: accepted
Slice: SLICE-01

## ADDED

- `docs/spec/security/ratelimit.md` REQ-RL-05 — WHEN statistics are sampled for a key via `get_window_stats(key)` THE SYSTEM SHALL return a dict with fields `accepted`, `rejected`, and `remaining_tokens` for that key.
- `docs/spec/security/ratelimit.md` REQ-RL-06 — WHEN the token-refill logic resets the window THE SYSTEM SHALL reset the `accepted` and `rejected` counters for the same window.
- `docs/spec/security/ratelimit.md` REQ-RL-07 — WHEN `get_window_stats(key)` is called THE SYSTEM SHALL NOT deduct tokens or change any limits.
- `docs/spec/security/ratelimit.md` REQ-RL-08 — WHEN `get_window_stats(key)` is called for an unknown key THE SYSTEM SHALL return zero `accepted` and `rejected` counters and a `remaining_tokens` equal to full capacity.

## MODIFIED

- None.

## REMOVED

- None.
