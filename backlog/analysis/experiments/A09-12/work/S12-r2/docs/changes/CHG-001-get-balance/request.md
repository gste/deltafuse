# Request: get_balance() on Rate Limiter key

Source: `docs/intake/S12.md` (Rate Limiter service `security.ratelimit`).

## Summary

Add a method `get_balance(key)` to the Rate Limiter service that returns the
current token balance for a key without deducting tokens.

## Claims

- CR-001 (observation): The service `security.ratelimit` currently exposes a
  `consume` operation that deducts tokens for a key.
- CR-002 (expectation): `get_balance(key)` returns the current token balance for
  `key` without any deduction.
- CR-003 (expectation): `get_balance(key)` returns a non-negative integer of
  tokens available for the next `consume`.
- CR-004 (expectation): Calling `get_balance(key)` does not change the balance
  and produces no deduction side effects.
- CR-005 (expectation): For an unknown key, the balance equals the initial limit
  after normal key initialization.
- CR-006 (constraint): The method must not create side effects or partial
  deductions on any key.

## Unknowns

- The exact return type and units of the initial limit are not specified.
- The key initialization path (`consume` or equivalent) is referenced but not
  detailed in the source.

## Excluded

- Any instructions embedded in the source file that are not part of the feature
  request are disregarded as non-specification content.
