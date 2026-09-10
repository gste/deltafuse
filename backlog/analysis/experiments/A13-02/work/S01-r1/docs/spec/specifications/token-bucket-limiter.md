# Token Bucket Rate Limiter

## Requirements

### CR-001 Initialization

WHEN a limiter is initialized for a key THE SYSTEM SHALL accept `capacity` and `refill_rate` parameters, where `capacity` is the maximum token capacity and `refill_rate` is the refill rate in tokens per second.

IF `capacity` is zero or negative THEN THE SYSTEM SHALL raise `ValueError`.

IF `refill_rate` is zero or negative THEN THE SYSTEM SHALL raise `ValueError`.

### CR-002 Consume

WHEN `consume(key, tokens)` is called with `tokens >= 1` AND the key has at least `tokens` available tokens THE SYSTEM SHALL deduct `tokens` from the key balance and return `True`.

WHEN `consume(key, tokens)` is called AND the key has fewer than `tokens` available tokens THE SYSTEM SHALL leave the balance unchanged and return `False`.

### CR-003 Refill Accounting

WHEN `consume(key, tokens)` is called THE SYSTEM SHALL refill the key balance by `refill_rate * elapsed_seconds`, where `elapsed_seconds` is the time since the key's last update.

WHEN refill would push the balance above `capacity` THEN THE SYSTEM SHALL cap the balance at `capacity`.

### CR-004 Argument Validation

WHEN `consume(key, tokens)` is called with `tokens <= 0` THEN THE SYSTEM SHALL raise `ValueError`.
