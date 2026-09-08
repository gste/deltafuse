# Request: Remove burst_allowance from Rate Limiter

Source: `docs/intake/S11.md` (Evaluator intake CHG-C).

## Summary

Remove `burst_allowance` from the Rate Limiter. Public constructor, specification,
and tests must no longer mention `burst`. Documentation and the capabilities
catalog must remain consistent, with no broken anchors.

## Claims

- CR-001 [observation] The Rate Limiter currently exposes a `burst_allowance`
  concept.
- CR-002 [expectation] `burst_allowance` must be removed from the Rate Limiter.
- CR-003 [expectation] The public constructor must not mention `burst`.
- CR-004 [expectation] The specification must not mention `burst`.
- CR-005 [expectation] Tests must not mention `burst`.
- CR-006 [constraint] Documentation and the capabilities catalog must stay
  consistent, with no broken anchors.
- CR-007 [hypothesis] Removing `burst_allowance` is a refactor that should not
  change observable rate-limiting behavior beyond the removed burst feature.

## Unknowns

- Exact locations of the constructor, specification, tests, docs, and catalog
  entries referencing `burst` are not yet enumerated (product artifacts not
  read during intake).
- Whether any external consumers depend on `burst_allowance` is unverified.
