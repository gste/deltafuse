# Change Request — CHG-107-ratelimit-cooldown-penalty

## Summary
Small change to the `security.ratelimit` capability (`TokenBucketLimiter`) to add an optional cooldown penalty: when a key exceeds its rate limit it can be temporarily blocked for `penalty_seconds`, during which all `consume` calls return `False` immediately. Backward compatibility must be preserved.

## Claims
Source: docs/intake/S02.md (raw user request)

- CR-1 [observation]: The source identifies the Rate Limiter service as capability `security.ratelimit`, exposing a class `TokenBucketLimiter` with an initializer and a `consume(key)` method.
- CR-2 [expectation]: Add an optional initialization parameter `penalty_seconds` to `TokenBucketLimiter`, defaulting to `0.0`.
- CR-3 [expectation]: When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) places the key into a blocked state lasting `penalty_seconds`.
- CR-4 [constraint]: While within its penalty period, any `consume` call for the blocked key MUST return `False` immediately, even if tokens have accumulated during that window.
- CR-5 [expectation]: After `penalty_seconds` elapses, the block is cleared automatically on the next request and normal token-deduction logic resumes.
- CR-6 [constraint]: A method `is_blocked(key)` MUST return `True` when a key is under penalty and `False` otherwise.
- CR-7 [constraint]: Backward compatibility must be preserved — existing callers that do not pass `penalty_seconds` must behave per the original rules.

## Unknowns (explicitly excluded from this request)
- Exact signature/return type of `consume` beyond yielding a truthy/falsy result.
- Internal representation of the blocked state and how it interacts with token accounting.
- Whether the penalty applies only on failure or also affects subsequent successful consumes.
- Language, test framework, and file locations for the implementation (to be resolved during analysis).
