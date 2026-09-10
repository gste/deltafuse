# CHG-001-burst-allowance

## Summary

Add an optional `burst_allowance` parameter to `TokenBucketLimiter` initialization.
While the key has not exhausted `burst_allowance` extra tokens, a rejected consume
must, once per call, receive the extra tokens and retry the attempt within the same
call. `burst_allowance` defaults to 0, preserving unchanged behavior.

## Claims

- CR-001 (observation): A `TokenBucketLimiter` class exists and is initialized with
  parameters; the source does not currently expose a `burst_allowance` parameter.
- CR-002 (expectation): Initialization accepts an optional `burst_allowance` argument.
- CR-003 (expectation): When a consume is rejected but the key still has unused
  `burst_allowance` tokens, the consume receives the extra tokens once and retries
  within the same call.
- CR-004 (constraint): `burst_allowance` defaults to 0, so existing behavior is
  unchanged when it is not specified.
- CR-005 (constraint): The extra-token retry applies at most once per consume call.

## Unknowns

- Exact signature/location of `TokenBucketLimiter` and its consume method is not
  confirmed from product code (unread during intake).
- Whether `burst_allowance` is per-key or global is not specified.
