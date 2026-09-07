# Spec Delta — CHG-001-ratelimit-consume-history

Slice: SLICE-01
Status: accepted

## MODIFIED

- `docs/spec/security/ratelimit.md` — REQ-RL-02: recording attempt history MUST NOT alter accept/reject result or token accounting (CR-007).
- `docs/spec/security/ratelimit.md` — REQ-RL-05 (ADDED): every `consume(key, tokens)` call MUST record an event (key, timestamp, requested token count, outcome `accepted`/`rejected`); recording MUST NOT change the result or token accounting (CR-002, CR-007).
- `docs/spec/security/ratelimit.md` — REQ-RL-06 (ADDED): `get_history(key, n=10)` MUST return the last `n` recorded events for `key`, newest first; `n` MUST be an integer `>= 1`, otherwise raise; default `n` is `10` (CR-003, CR-004, CR-005).
- `docs/spec/security/ratelimit.md` — REQ-RL-07 (ADDED): history records for different keys MUST be isolated and never mixed (CR-006).

## UNCHANGED

- REQ-RL-01 (capacity and refill), REQ-RL-03 (unknown keys start full), REQ-RL-04 (is_blocked) — preserved; no normative change.
- Capability catalog `_capabilities.yaml` — unchanged (catalog delta: none).
