# CHG-001: Add optional burst_allowance to TokenBucketLimiter

## Summary

Add an optional `burst_allowance` parameter to `TokenBucketLimiter` initialization. While the key has not exhausted `burst_allowance` additional tokens, a rejected consume call must receive extra tokens once and retry the attempt within the same call. `burst_allowance` defaults to 0, preserving unchanged behavior.

## Claims

### CR-001 [observation]
The source request `docs/intake/S11.md` describes a feature to add optional `burst_allowance` to `TokenBucketLimiter`.

### CR-002 [expectation]
When a key has not yet exhausted `burst_allowance` additional tokens, a rejected consume call must receive extra tokens once and retry the attempt within the same call.

### CR-003 [expectation]
`burst_allowance` defaults to 0, which preserves unchanged behavior.

### CR-004 [hypothesis]
The exact signature and location of the `burst_allowance` parameter on `TokenBucketLimiter` initialization is not specified in the source and must be determined during analysis.

### CR-005 [hypothesis]
The precise semantics of "exhausting burst_allowance" and how extra tokens are granted are not fully specified and must be clarified during analysis.
