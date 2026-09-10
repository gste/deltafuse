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
`consume(key, tokens=1)`:
- If enough tokens are available, deduct the requested amount and return `True`.
- If not enough tokens are available, leave the balance unchanged and return `False`.

### CR-003 (expectation)
Elapsed time must be accounted for correctly: tokens are restored proportionally
to the elapsed time between calls, but never exceed `capacity`.

### CR-004 (constraint)
Strict argument validation: negative or zero `capacity` / `refill_rate`, and a
`consume` call with `tokens <= 0`, must raise `ValueError`.

## Unknowns

- Language, runtime, and public API conventions are not specified.
- Persistence, concurrency, and thread-safety requirements are not specified.
- No acceptance criteria or test expectations were provided in the source.
