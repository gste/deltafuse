# Rate Limiter (security.ratelimit)

## Overview

The `security.ratelimit` module provides a token-bucket rate limiter used to
throttle per-client request throughput. It exposes `TokenBucketLimiter` with
`capacity`, `refill_rate`, `consume()`, and `is_blocked()`.

## Requirements

### REQ-RL-01 Capacity and refill

The limiter accepts a `capacity` (maximum tokens) and a `refill_rate` (tokens
per second, «скорость пополнения»). Both must be non-negative; `capacity` must
be strictly positive.

### REQ-RL-02 Consume semantics

`consume(key, tokens)` refills the bucket based on elapsed time, then deducts
`tokens`. It returns `True` if the deduction succeeded and `False` otherwise.

### REQ-RL-03 Blocking state

`is_blocked(key)` reports whether the bucket currently has insufficient tokens.

### REQ-RL-04 Invalid parameters

Constructing a limiter with `capacity <= 0` or `refill_rate < 0` raises
`ValueError`.

## Usage Examples

### Initialization

```python
from ratelimit.limiter import TokenBucketLimiter

limiter = TokenBucketLimiter(capacity=10, refill_rate=1)
```

This creates a bucket with a maximum of 10 tokens refilling at 1 token per
second, satisfying REQ-RL-01.

### Consume with validation

```python
if limiter.consume('client-1', 3):
    # allowed
else:
    # rate limited
```

`consume` returns `True` when tokens are available and `False` otherwise,
as specified by REQ-RL-02.

### ValueError handling

```python
try:
    limiter = TokenBucketLimiter(capacity=0, refill_rate=1)
except ValueError as exc:
    print('invalid parameters:', exc)
```

Invalid parameters raise `ValueError` as required by REQ-RL-04.

## Architectural Decisions

### Token Bucket algorithm

The Token Bucket algorithm was selected for rate limiting because it allows
bounded bursts while enforcing a long-term average rate. Burst tolerance is
controlled by `capacity` (the maximum bucket size) and the long-term rate by
`refill_rate`. This design aligns with RFC 2697 (HTTP Rate Limiting), which
describes token-bucket-based throttling for HTTP resources.

### Comparison with Leaky Bucket

Leaky Bucket enforces a constant output rate by draining a queue at a fixed
rate, which rejects bursts even when the client is otherwise under quota.
Token Bucket instead models explicit bursts: excess capacity accumulates up to
`capacity` and can be spent immediately, making it better suited to workloads
with intermittent spikes while still protecting the long-term average rate.
