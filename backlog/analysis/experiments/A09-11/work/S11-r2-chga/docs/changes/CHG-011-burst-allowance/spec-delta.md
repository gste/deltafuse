---
change: CHG-011-burst-allowance
status: proposed
slices: [SLICE-01]
---

# Spec Delta — CHG-011-burst-allowance

## MODIFIED

- `docs/spec/security/ratelimit.md` REQ-RL-05 — MAY initialize with optional `burst_allowance >= 0` (default 0); when 0, consume/reject behavior is unchanged from REQ-RL-02.
- `docs/spec/security/ratelimit.md` REQ-RL-06 — new requirement: on a rejected `consume`, if the key still has `burst_allowance` tokens remaining, the limiter grants `extra` tokens once and retries the consume attempt within the same invocation; the retry path grants `extra` tokens exactly once per rejected call and MUST NOT repeat the grant on subsequent rejections.

## Added spec_refs

- `docs/spec/security/ratelimit.md` (REQ-RL-05, REQ-RL-06)
