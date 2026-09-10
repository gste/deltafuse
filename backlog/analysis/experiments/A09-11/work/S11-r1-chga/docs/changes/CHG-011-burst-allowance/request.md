# Request: Add optional burst_allowance to TokenBucketLimiter

## Summary

Add an optional `burst_allowance` parameter to `TokenBucketLimiter` initialization.
While the key has not exhausted `burst_allowance` extra tokens, a rejected
`consume` call should receive `extra` tokens once and retry the attempt within
the same call. `burst_allowance` defaults to 0 (unchanged behavior).

## Claims

### CR-001 — observation
The source note `docs/intake/S11.md` requests a new optional initialization
parameter `burst_allowance` on `TokenBucketLimiter`. No existing code was read;
the parameter's current absence is inferred from the request, not observed.

### CR-002 — expectation
While a key still has unused `burst_allowance` extra tokens, a rejected
`consume` should be granted `extra` tokens once and retried within the same
`consume` call.

### CR-003 — expectation
`burst_allowance` defaults to `0`, preserving existing behavior when unset.

### CR-004 — hypothesis
The retry grants `extra` tokens exactly once per rejected call; the note does
not specify whether partial `extra` amounts are granted or whether the grant
consumes from `burst_allowance`.

### CR-005 — unknown
The target language, module, and existing `TokenBucketLimiter` API are not
specified in the intake artifact and remain to be confirmed during analysis.
