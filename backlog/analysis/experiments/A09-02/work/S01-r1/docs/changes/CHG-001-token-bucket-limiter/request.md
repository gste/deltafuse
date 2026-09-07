# Request: Token Bucket Rate Limiter

## Summary

Create a Token Bucket Rate Limiter service from scratch in a new product.
The service manages per-key access-token limits with time-based refill and
strict argument validation.

## Claims

### CR-001 (expectation)
A limiter can be initialized for a given key with two parameters:
`capacity` (maximum token capacity) and `refill_rate` (tokens refilled per second).

### CR-002 (expectation)
`consume(key, tokens=1)` behavior:
- If enough tokens are available, deduct the requested amount and return `True`.
- If not enough tokens, leave the balance unchanged and return `False`.

### CR-003 (expectation)
Elapsed time must be accounted for correctly: tokens refill proportionally to the
time elapsed between calls, but never exceed `capacity`.

### CR-004 (constraint)
Strict argument validation: negative or zero `capacity` / `refill_rate`, and a
`consume` call with `tokens <= 0`, must raise `ValueError`.

## Unknowns

- Language, runtime, and public API shape are not specified.
- Concurrency model (thread-safety, per-key locking) is unspecified.
- Time source (wall clock vs. injected clock) is unspecified.
- Persistence and key namespace scope are unspecified.
