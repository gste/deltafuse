# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0 (скорость пополнения).

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## Usage Examples

### Initialization

```python
limiter = TokenBucketLimiter(capacity=10, refill_rate=1)
```

The limiter MUST reject `capacity <= 0` at construction.

### Consume with validation

```python
assert limiter.consume("user:42", 3) is True   # enough tokens → deducted
assert limiter.consume("user:42", 100) is False  # insufficient → no deduction
```

`consume` MUST reject negative token counts with `ValueError`.

### Handling of ValueError

```python
try:
    limiter.consume("user:42", -1)
except ValueError as exc:
    log.warning("invalid consume", exc=exc)
```

A `ValueError` MUST NOT modify the token balance for the key.

## Architectural Decisions

### Token Bucket algorithm

The rate limiter uses the Token Bucket algorithm (RFC 2697) because it
natively supports short bursts up to `capacity` while enforcing the long-term
average `refill_rate`, which matches the product's need to absorb client
retries without permanently blocking them.

#### Comparison with Leaky Bucket

Leaky Bucket enforces a strictly constant output rate and queues overflow,
which drops bursts that Token Bucket permits. For a client-facing API that
must tolerate retries and transient spikes, Token Bucket provides the
required burst tolerance; Leaky Bucket would over-restrict legitimate traffic.
