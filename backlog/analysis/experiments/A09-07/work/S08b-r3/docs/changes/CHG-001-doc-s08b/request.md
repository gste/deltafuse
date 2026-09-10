# Request: Update Rate Limiter (S08b) documentation

## Summary

Update the documentation for the `security.ratelimit` module. The change is
documentation-only: code and tests are not modified and system behavior is
unchanged.

## Claims

### CR-001 — observation
The module `security.ratelimit` is documented in `docs/spec/security/ratelimit.md`.

### CR-002 — expectation
Add a «Usage Examples» section to `docs/spec/security/ratelimit.md` with three
typical scenarios: initialization, `consume` with validation, and handling of
`ValueError`.

### CR-003 — expectation
Add an «Architectural Decisions» section describing the choice of the Token
Bucket algorithm with justification (reference to RFC 2697 and a comparison with
Leaky Bucket).

### CR-004 — expectation
Fix a typo in the description of the `refill_rate` parameter: «скокрость» →
«скорость».

### CR-005 — expectation
Update `CHANGELOG.md` with an entry documenting the documentation change.

### CR-006 — constraint
Code and tests are not modified. System behavior is not changed.

## Unknowns

- Exact location of `CHANGELOG.md` (repository root vs. package directory) is
  not confirmed.
- Whether the «Architectural Decisions» section belongs in `docs/spec/
  security/ratelimit.md` or a separate decisions file is not confirmed.
