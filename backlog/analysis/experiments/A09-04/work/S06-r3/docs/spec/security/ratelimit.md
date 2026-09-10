# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Audit log of consume events
The rate limiter MUST record every `consume` event to an append-only structured
audit log under `monitoring.audit_log`. Each record MUST contain at least:

- `key` — the limiter key
- `tokens` — tokens requested in the consume call
- `result` — the boolean outcome of the consume call
- `timestamp` — the event time in ISO-8601 UTC

Irrelevant log lines (`DEBUG internal_gc`, `WARN network`) MUST NOT influence the
audit log or alerting logic.

## REQ-RL-06 Audit log rotation
The audit log MUST be append-only and support size-based rotation with a maximum
of 10 MB per file. When a log file reaches the size limit, it MUST be rotated to
a new file; existing records MUST NOT be modified or deleted.
