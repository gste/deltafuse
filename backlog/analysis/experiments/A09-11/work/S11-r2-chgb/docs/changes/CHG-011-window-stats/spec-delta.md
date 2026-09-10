# Spec Delta — CHG-011-window-stats

Slice: SLICE-01
Status: accepted

## ADDED

- REQ-RL-05 Window statistics — get_window_stats(key) MUST return a dictionary with integer fields `accepted`, `rejected`, and `remaining_tokens` for the given key, without consuming tokens or changing limits.
- REQ-RL-06 Window counter reset — Window counters tracked for get_window_stats MUST be reset together with the token-replenishment logic of the limiter.
- REQ-RL-07 Unknown-key statistics — For an unknown key, get_window_stats MUST return zero `accepted` and `rejected` counters and a `remaining_tokens` equal to the current remainder per the key-initialization rules.

## MODIFIED

- (none)

## REMOVED

- (none)
