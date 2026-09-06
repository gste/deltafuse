---
id: TASK-001
change: CHG-001-ratelimit-cooldown
slice: SLICE-01
kind: feature
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md#REQ-RL-05
  - docs/spec/security/ratelimit.md#REQ-RL-06
  - docs/spec/security/ratelimit.md#REQ-RL-04
design_ref: null
allowed_paths:
  - src/ratelimit/limiter.py
  - docs/spec/security/ratelimit.md
forbidden_paths:
  - docs/spec/auth/**
---

## Outcome

Confirm the existing `TokenBucketLimiter` implementation and record the confirmed
language, per-key state storage, and clock source (monotonic vs wall-clock).
No production code is modified.

## Steps

- Read `src/ratelimit/limiter.py` and confirm the language, the data structure
  used to store per-key state, and the clock source used for time.
- Confirm how `consume(key, tokens)` currently returns and deducts tokens
  (REQ-RL-02) and how unknown keys start full (REQ-RL-03).
- Confirm the current `is_blocked(key)` baseline returns `False` (REQ-RL-04).
- Note whether the clock is monotonic or wall-clock, since REQ-RL-05 timing
  depends on it.

## Test oracle

A short note in the task body stating the language, the per-key state storage
mechanism, and the clock source. This is a read-only task; no test runs.

## Unchanged behavior

- REQ-RL-01 (capacity > 0, refill_rate >= 0), REQ-RL-02, REQ-RL-03, and the
  baseline `is_blocked` (REQ-RL-04) behavior are preserved.

## Verification

- `cat src/ratelimit/limiter.py` confirms the above; no build or test required.

---

## Scope

- In scope: reading `src/ratelimit/limiter.py` and `docs/spec/security/ratelimit.md`.
- Out of scope: any code change, and any change outside `security.ratelimit`.
