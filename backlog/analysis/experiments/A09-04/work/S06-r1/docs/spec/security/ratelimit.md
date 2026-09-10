# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0.

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## REQ-RL-05 Audit log event recording
Every `consume` event MUST be recorded by `monitoring.audit_log` with fields
`key`, `tokens`, `result` (`ok` or `rejected`), and `timestamp` into an
append-only structured log. Only events carrying a valid `consume` result are
recorded; `DEBUG internal_gc` and `WARN network` lines MUST NOT be recorded or
influence logic.

## REQ-RL-06 Audit log rotation
The audit log MUST be append-only and rotate by size, producing at most one
log file of 10 MB before starting a new file.
