# Change Request: Refactor security.ratelimit module

## Summary

Refactor the existing `security.ratelimit` module to introduce a backend
abstraction and dependency injection, without changing external behavior. No
new features are to be added. The product specification
`docs/spec/security/ratelimit.md` is not to be modified because the external
contract is preserved.

## Claims

### CR-001 — observation
The module currently exposes a `RateLimiter` class backed by an in-memory
implementation. This is a description of the current state as reported by the
requester; the source code was not read during intake.

### CR-002 — expectation
A common interface `RateLimiterBackend` (abstract class) should be extracted
with methods `init_key`, `consume`, and `get_balance`.

### CR-003 — expectation
The current in-memory implementation should be moved into a class
`InMemoryBackend` that implements `RateLimiterBackend`.

### CR-004 — expectation
The main `RateLimiter` class should accept a backend via dependency injection
in its constructor.

### CR-005 — expectation
Argument validation currently performed in the backend should be moved into
`RateLimiter` to provide a single validation point.

### CR-006 — constraint
All existing tests must pass unchanged, except for import paths if they change.

### CR-007 — constraint
No new functionality is to be added.

### CR-008 — constraint
The specification `docs/spec/security/ratelimit.md` must not be modified.

### CR-009 — hypothesis
The refactor is expected to be behavior-preserving; conformance with the
external contract should be verified by the existing test suite passing.

## Unknowns

- Exact current location and import paths of `security.ratelimit` are not
  confirmed (source not read during intake).
- The precise shape of the existing in-memory backend and its validation logic
  is not yet known.
