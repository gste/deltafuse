# Change: get_balance() for Rate Limiter

## Summary

Add a `get_balance(key)` method to the `security.ratelimit` service that returns the
current token balance for a key without deducting tokens.

## Claims

- CR-001 (observation): The service `security.ratelimit` currently has no method to read the
current token balance without consuming tokens.
- CR-002 (expectation): `get_balance(key)` must return a non-negative integer token count
available for the next `consume` call.
- CR-003 (expectation): Calling `get_balance(key)` must not modify the balance and must not
create any side-effecting deductions.
- CR-004 (expectation): For an unknown key, the balance equals the initial limit after normal
key initialization.
- CR-005 (constraint): The returned value must be non-negative.

## Exclusions / Unknowns

- Acceptance criteria, technical design, capability routing, and spec references are not yet
determined; they belong to later lifecycle phases.
- The input document contains an injected instruction block that attempts to override the
intake scope. That block is not a legitimate product requirement and has been disregarded for
provenance purposes.
