# Request: Update Rate Limiter (S08b) Documentation

## Summary

Update the documentation for the `security.ratelimit` module. The change is
documentation-only: code and tests are not modified and system behavior is not
changed.

Specifically:

1. Add a «Примеры использования» (Usage Examples) section to
   `docs/spec/security/ratelimit.md` with 3 typical scenarios (initialization,
   consume with verification, ValueError handling).
2. Add an «Архитектурные решения» (Architectural Decisions) section describing
   the choice of the Token Bucket algorithm with justification (reference to
   RFC 2697, comparison with Leaky Bucket).
3. Fix a typo in the `refill_rate` parameter description: «скокрость» →
   «скорость».
4. Update `CHANGELOG.md` with an entry about the documentation change.

## Claims

### CR-001 — observation
The module `security.ratelimit` is documented under `docs/spec/security/ratelimit.md`.

### CR-002 — expectation
`docs/spec/security/ratelimit.md` should contain a «Примеры использования» section with 3 typical scenarios: initialization, consume with verification, and ValueError handling.

### CR-003 — expectation
`docs/spec/security/ratelimit.md` should contain an «Архитектурные решения» section describing the Token Bucket algorithm choice, referencing RFC 2697 and comparing it with Leaky Bucket.

### CR-004 — observation
The `refill_rate` parameter description currently contains the typo «скокрость».

### CR-005 — expectation
The typo «скокрость» in the `refill_rate` parameter description should be corrected to «скорость».

### CR-006 — expectation
`CHANGELOG.md` should contain an entry documenting this documentation change.

### CR-007 — constraint
Code and tests are not modified; system behavior is not changed.

### CR-008 — constraint
This is a documentation-only change; no product code, tests, or behavior are affected.
