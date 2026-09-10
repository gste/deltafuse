# Change Request: Refactor security.ratelimit module

## Summary

Refactor the existing `security.ratelimit` module to introduce a backend
abstraction and dependency injection, without changing external behavior. No
new features are to be added. The specification `docs/spec/security/ratelimit.md`
is explicitly out of scope and must not be changed.

## Claims

### CR-001 [expectation]
Introduce a common interface `RateLimiterBackend` (abstract class) exposing
methods `init_key`, `consume`, and `get_balance`.

### CR-002 [expectation]
Move the current in-memory implementation into a class `InMemoryBackend`
implementing `RateLimiterBackend`.

### CR-003 [expectation]
The main `RateLimiter` class must accept a backend via dependency injection in
its constructor.

### CR-004 [expectation]
Argument validation currently performed in the backend must be moved into
`RateLimiter` to provide a single validation point.

### CR-005 [constraint]
All existing tests must pass unchanged, except for import paths if they change.

### CR-006 [constraint]
No new functionality is to be added.

### CR-007 [constraint]
The specification `docs/spec/security/ratelimit.md` must not be modified, as the
external contract is preserved.

## Unknowns

- Exact current file path of the `security.ratelimit` module is not confirmed
  (not read per intake gate).
- Exact current location and import paths of existing tests are not confirmed.
- Whether `InMemoryBackend` is the only backend or a template for future backends
  is not specified.
