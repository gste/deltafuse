# Spec Delta — CHG-001-ratelimit-history (SLICE-01)

Status: proposed

## ADDED

- REQ-RL-05 Consume event record — every `consume(key, tokens)` call records an event with key, timestamp, requested token count, and outcome (`accepted`/`rejected`).
- REQ-RL-06 get_history — `get_history(key, n=10)` returns the last `n` recorded events for the key, newest first.
- REQ-RL-07 n validation — `n` MUST be an integer >= 1; an exception MUST be raised otherwise.
- REQ-RL-08 n default — default value of `n` in `get_history` MUST be 10.
- REQ-RL-09 Per-key isolation — events for different keys MUST NOT be mixed; `get_history(key)` returns only that key's events.
- REQ-RL-10 Semantic invariance — enabling history MUST NOT change `consume` semantics.

## MODIFIED

- None.

## REMOVED

- None.

## Notes

- Catalog delta: none.
- Decisions: none blocking (backend/retention are CR-008 open, non-blocking).
- Existing REQ-RL-01 through REQ-RL-04 unchanged.
