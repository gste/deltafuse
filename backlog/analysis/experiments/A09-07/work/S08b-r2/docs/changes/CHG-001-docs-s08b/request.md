# Request: Update Rate Limiter (S08b) Documentation

## Summary

Update the documentation for the `security.ratelimit` module. The change is
documentation-only: code and tests are not modified and system behavior is not
changed.

Specifically:

1. Add a "Usage Examples" section to `docs/spec/security/ratelimit.md` with 3
   typical scenarios (initialization, consume with validation, ValueError
   handling).
2. Add an "Architectural Decisions" section describing the choice of the Token
   Bucket algorithm with justification (reference to RFC 2697, comparison with
   Leaky Bucket).
3. Fix a typo in the `refill_rate` parameter description: «скокрость» →
   «скорость».
4. Update `CHANGELOG.md` with an entry about the documentation change.

## Claims

### CR-001 — observation
The module `security.ratelimit` currently has documentation at
`docs/spec/security/ratelimit.md` that lacks a usage examples section and an
architectural decisions section. (Source: S08b.md)

### CR-002 — expectation
`docs/spec/security/ratelimit.md` should contain a "Usage Examples" section with
3 typical scenarios: initialization, consume with validation, and ValueError
handling.

### CR-003 — expectation
`docs/spec/security/ratelimit.md` should contain an "Architectural Decisions"
section describing the Token Bucket algorithm choice, referencing RFC 2697 and
comparing it with Leaky Bucket.

### CR-004 — observation
The `refill_rate` parameter description in the current docs contains the typo
«скокрость» instead of «скорость».

### CR-005 — expectation
The typo «скокрость» in the `refill_rate` parameter description should be fixed
to «скорость».

### CR-006 — expectation
`CHANGELOG.md` should receive an entry documenting the documentation change.

### CR-007 — constraint
Code and tests must not be modified; system behavior must not change.

### CR-008 — constraint
This is a documentation-only change; no acceptance criteria, technical design,
or capability routing are defined at this stage.
