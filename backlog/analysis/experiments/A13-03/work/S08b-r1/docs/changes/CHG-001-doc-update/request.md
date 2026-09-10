# Request: Update Rate Limiter Documentation (security.ratelimit)

## Summary

Update the documentation for the `security.ratelimit` module. Code and tests are
not changed; system behavior is not changed. The work is documentation-only:

- Add a "Usage Examples" section to `docs/spec/security/ratelimit.md` with 3
  typical scenarios (initialization, consume with validation, handling
  `ValueError`).
- Add a "Architectural Decisions" section describing the choice of the Token
  Bucket algorithm with justification (reference to RFC 2697, comparison with
  Leaky Bucket).
- Fix a typo in the description of the `refill_rate` parameter: «скокрость» →
  «скорость».
- Update `CHANGELOG.md` with an entry about the documentation change.

## Claims

- CR-001 (expectation): `docs/spec/security/ratelimit.md` should contain a
  "Usage Examples" section with 3 typical scenarios: initialization, consume
  with validation, and handling `ValueError`.
- CR-002 (expectation): `docs/spec/security/ratelimit.md` should contain an
  "Architectural Decisions" section describing the Token Bucket algorithm
  choice, referencing RFC 2697 and comparing it with Leaky Bucket.
- CR-003 (constraint): Fix the typo «скокрость» → «скорость» in the
  `refill_rate` parameter description.
- CR-004 (expectation): `CHANGELOG.md` should include an entry about the
  documentation change.
- CR-005 (constraint): Code and tests are not modified; system behavior is not
  modified.
