---
id: SLICE-01
change: CHG-001-fractional-token-refill
title: Fractional token refill accumulation and consume debit
status: analyzing
primary_capability: ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
depends_on: []
---

## Slice analysis

- **intent**: Fix fractional token accrual loss in `TokenBucketLimiter` refill and ensure `consume` debits integer/fractional tokens correctly.
- **delta_kind**: implementation
- **requirement_delta**: none. `docs/spec/security/ratelimit.md` (REQ-RL-01 proportional refill preserving fractional balances; REQ-RL-02 consume debit) already governs behavior and is unchanged.
- **design_impact**: `refill` must accumulate accrued tokens as float across calls instead of `int(elapsed * refill_rate)`; `consume` must debit fractional counts and return True/False per REQ-RL-02.
- **risk**: low-medium. Pure bugfix within existing ratelimit capability; no new API or spec change.
- **size**: small.

### In scope
- Inspect `src/ratelimit` `TokenBucketLimiter.refill`/`consume`.
- Convert refill accrual to float accumulation; fix consume debit.
- Add failing (Red) test at Target reproducing fractional accrual at small intervals (CR-006).

### Out of scope
- Any edit to `docs/spec/security/ratelimit.md` (CR-005).
- Exposing fractional tokens to callers (open unknown; internal tracking only).

### Dependencies
- None. Single capability slice.

### Context budget
- max_tokens: 4000, max_files: 8.