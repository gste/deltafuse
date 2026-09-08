# Change Request: CHG-011-burst-allowance

## Summary

Add an optional `burst_allowance` parameter to `TokenBucketLimiter` initialization.
While the key has not exhausted `burst_allowance` additional tokens, a rejected
`consume` call must, once, receive `extra` tokens and retry the attempt within the
same call. `burst_allowance` defaults to 0 (unchanged behavior).

## Claims

- CR-001 (observation): `TokenBucketLimiter` currently exists and exposes a
  `consume` method that can reject a request when the key has no tokens.
- CR-002 (expectation): `TokenBucketLimiter` initialization accepts an optional
  `burst_allowance` parameter.
- CR-003 (expectation): When a `consume` is rejected and the key still has
  `burst_allowance` tokens remaining, the call receives `extra` tokens once and
  retries within the same `consume` invocation.
- CR-004 (constraint): `burst_allowance` defaults to 0, preserving existing
  behavior when not specified.
- CR-005 (hypothesis): The retry path grants `extra` tokens exactly once per
  rejected call (not repeatedly).

## Unknowns

- Exact signature/location of `TokenBucketLimiter` and the meaning of `extra`
  tokens is not yet confirmed against the codebase.
- Whether `burst_allowance` is per-key or global is not specified.
