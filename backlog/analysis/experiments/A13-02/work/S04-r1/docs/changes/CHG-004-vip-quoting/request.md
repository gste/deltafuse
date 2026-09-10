# Change CHG-004: VIP-quoting for Rate Limiter

## Summary
The user requests that VIP customers receive special treatment in the Rate Limiter so they do not suffer under the general limits. Concrete options are offered as possibilities, not requirements: (a) an effectively infinite quota, (b) a separate enlarged token pool (e.g. 10x the normal amount), or (c) out-of-service priority handling. The user explicitly defers the choice of mechanism and the concrete parameters to the implementation side and asks to "decide yourself how is best and implement."

## Claims

- CR-001 [observation] The source artifact is `docs/intake/S04.md`, a user request in Russian.
- CR-002 [expectation] VIP customers should not suffer from the general rate limits.
- CR-003 [expectation] At least one of the following mechanisms should apply to VIP customers: infinite quota, a separate enlarged token pool, or out-of-service priority.
- CR-004 [expectation] The enlarged pool example given is "10x the normal amount"; this is an illustrative example, not a fixed requirement.
- CR-005 [constraint] The choice of mechanism and the concrete parameter values are left to the implementation to decide; no specific value is mandated.
- CR-006 [hypothesis] Existing non-VIP behavior of the Rate Limiter should remain unchanged for users who are not VIP.

## Unknowns
- The definition of "VIP" (how a user is classified as VIP) is not specified.
- The current Rate Limiter implementation, configuration, and where VIP status is stored are not read and not known.
- Whether an infinite quota is acceptable operationally or whether a large finite pool is preferred is undecided.
