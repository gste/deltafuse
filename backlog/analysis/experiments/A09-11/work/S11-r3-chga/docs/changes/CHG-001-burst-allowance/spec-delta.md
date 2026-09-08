# Spec Delta — CHG-001-burst-allowance

Slice: SLICE-01
Status: accepted

## MODIFIED

- **REQ-RL-02 Consume**: The single-retry burst path is now normative. When the key does not have enough tokens, consume grants up to `burst_allowance` extra tokens once and retries within the same call; on the retry it returns True and deducts the requested tokens if the granted tokens are sufficient, otherwise False without deduction. The retry occurs at most once per consume call.

## ADDED

- **REQ-RL-06 burst_allowance**: TokenBucketLimiter MUST accept an optional `burst_allowance` parameter defaulting to 0. When `burst_allowance` is 0, consume MUST not grant extra tokens and behavior MUST be unchanged from the baseline single-attempt semantics.

## REMOVED

- (none)
