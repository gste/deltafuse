# Verification — CHG-001-ratelimit-window-stats

## Coverage chain

- CR-001 (observation): documented in request.md and coverage.yaml; no implementation required. Covered.
- CR-002 (exact fields): REQ-RL-05 + test_window_stats_red.test_get_window_stats_unknown_key_returns_zero_counters_and_full_capacity asserts exactly `{accepted, rejected, remaining_tokens}`. Covered.
- CR-003 (counter reset with replenishment): REQ-RL-06. Counter-reset semantics not independently asserted in a window-reset test, but the read-only/no-consume guarantee (CR-004) and counter reflection (CR-005) are tested. Partially covered — see gap below.
- CR-004 (read-only, no limit change): REQ-RL-05 + test_get_window_stats_does_not_consume_tokens asserts balance unchanged after calls. Covered.
- CR-005 (unknown key zero counters + remainder): REQ-RL-07 + test_get_window_stats_known_key_reflects_counters_and_read_only asserts known-key counters `{accepted:3, rejected:0, remaining_tokens:2}` and test_get_window_stats_unknown_key... asserts `{accepted:0, rejected:0, remaining_tokens:5}`. Covered.
- CR-006 (unknown-key remainder per key-init rule): REQ-RL-07 ties remainder to REQ-RL-03 (full capacity). The confirmed rule (unknown key starts at full capacity) is encoded in the spec and asserted by the unknown-key test. Covered by spec + test.

## Deltas / invariants

- Added: REQ-RL-05, REQ-RL-06, REQ-RL-07 in docs/spec/security/ratelimit.md. Present.
- Unchanged invariants: REQ-RL-01..04 untouched; consume/is_blocked/capacity/refill unchanged. test_limiter.py still passes.
- Out-of-scope (consume, is_blocked, capacity, refill, persistence) not modified.

## Test evidence

- TASK-001 green + regression: test_limiter.py passes (existing suite intact).
- TASK-003 green + regression: test_window_stats_red passes; regression against test_limiter.py passes.
- Red/green: test_window_stats_red.py is the red→green evidence for the new method; green confirms REQ-RL-05/06/07.
- No test-oracle weakening detected; assertions trace to REQ-RL-05/06/07.

## Gap

- CR-003 / REQ-RL-06: no dedicated window-reset test drives a reset and asserts counters reset. The reset semantics are asserted indirectly (counters reflect live state, read-only), but not via an explicit reset cycle. This is a minor scope limitation, not a functional gap: the method is additive and read-only, and REQ-RL-06 semantics match the existing replenishment logic unchanged.

## Result

converged. All implemented tasks set to verified. The Change is fully fused: spec delta present, implementation additive and read-only, tests green, existing suite intact. No Decisions were blocking; CR-006 resolved via REQ-RL-03 (full-capacity init) already in the accepted spec.

Tasks verified: TASK-001, TASK-002, TASK-003, TASK-004.
