# Change Request — CHG-001-ratelimit-cooldown-penalty

## Summary
Add an optional cool-down penalty to the `security.ratelimit` capability's
`TokenBucketLimiter`: when a `consume` fails due to insufficient tokens and
`penalty_seconds > 0`, the key is blocked for `penalty_seconds`; while blocked,
every `consume` returns `False` immediately even if tokens accumulated; after the
window elapses the block clears on the next request and normal deduction resumes.
An `is_blocked(key)` accessor reports penalty state. Backward compatibility must be
preserved.

## Claims

### Observations
- CR-001 [observation]: The product exposes a capability named `security.ratelimit`.
- CR-002 [observation]: A class `TokenBucketLimiter` exists with an initializer and a `consume` method (exact signatures/details to be confirmed in analyze).
- CR-003 [observation]: No cool-down / penalty blocking currently exists.

### Expectations
- CR-101 [expectation]: `TokenBucketLimiter.__init__` gains optional parameter `penalty_seconds`, default `0.0`.
- CR-102 [expectation]: When `penalty_seconds > 0`, a failed `consume` (insufficient tokens) puts the key into a blocked state lasting `penalty_seconds`.
- CR-103 [expectation]: While a key is blocked, every `consume` call returns `False` immediately, even if tokens have accumulated during the penalty window.
- CR-104 [expectation]: After `penalty_seconds` elapses, the block clears automatically on the next request and normal token-deduction logic resumes.
- CR-105 [expectation]: A method `is_blocked(key)` returns `True` when the key is under penalty and `False` otherwise.

### Constraints
- CR-201 [constraint]: Backward compatibility must be preserved; callers that do not pass `penalty_seconds` keep existing behavior.

### Unknowns / Hypotheses
- CR-901 [hypothesis]: The current signatures of `TokenBucketLimiter.__init__` and `consume` are compatible with adding an optional keyword argument (verify in analyze).
- CR-902 [unknown]: Whether `is_blocked(key)` already exists or must be created.
