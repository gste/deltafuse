# Request: Token Bucket Rate Limiter

## Summary

Create a Token Bucket Rate Limiter service from scratch in a new product.
The service must support per-key initialization with capacity and refill_rate,
a consume method with token-balance semantics, time-based refill accounting,
and strict argument validation.

## Claims

### CR-001 (expectation)
A limiter can be initialized for a given key with two parameters:
`capacity` (maximum token capacity) and `refill_rate` (refill rate in tokens per second).

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

### CR-005 (hypothesis)
Implementation route is code (new service), executed against the current product
root. Exact language/framework and file layout are not specified here and remain
open for the next phase.

## Unknowns

- Target language/framework and project layout are not specified.
- Whether the limiter is global or strictly per-key with independent state is not
  fully specified beyond per-key initialization.
- Persistence and process-scope of state are not specified.
