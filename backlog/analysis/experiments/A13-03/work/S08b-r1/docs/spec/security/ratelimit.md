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

`TokenBucketLimiter` MUST initialize with `capacity > 0` and `refill_rate >= 0`
(REQ-RL-01). Passing `capacity <= 0` MUST raise `ValueError`.

### Consume with validation

```python
assert limiter.consume("user:42", 3) is True  # 3 tokens deducted
assert limiter.consume("user:42", 100) is False  # insufficient, no deduction
```

`consume(key, tokens)` MUST return `True` and deduct `tokens` when the key has
enough tokens, otherwise return `False` without deduction (REQ-RL-02).

### Handling `ValueError`

```python
try:
    limiter = TokenBucketLimiter(capacity=0, refill_rate=1)
except ValueError as exc:
    log.warning("invalid limiter config: %s", exc)
```

A non-positive `capacity` MUST raise `ValueError`, which callers SHOULD catch and
log rather than propagate, so a misconfigured limiter fails closed without
terminating the process.

## Architectural Decisions

### Token Bucket vs Leaky Bucket

The rate limiter uses the **Token Bucket** algorithm (reference: RFC 2697,
"The Token Bucket Algorithm") rather than the Leaky Bucket algorithm.

Justification:

- **Burst tolerance.** Token Bucket permits short bursts up to `capacity` while
  still enforcing the long-term average refill rate, matching API rate-limit
  semantics where occasional bursts are acceptable.
- **Simple capacity model.** `capacity` and `refill_rate` map directly to the
  burst size and steady-state rate, matching REQ-RL-01.
- **Leaky Bucket trade-off.** Leaky Bucket emits requests at a strictly constant
  rate and does not permit bursts, which is less suitable for bursty API traffic.

The choice is observable through `consume` burst behavior (REQ-RL-02) and the
`capacity`/`refill_rate` initialization contract (REQ-RL-01).
