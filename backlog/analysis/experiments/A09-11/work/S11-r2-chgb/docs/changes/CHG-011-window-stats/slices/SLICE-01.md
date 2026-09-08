---
id: SLICE-01
change: CHG-011-window-stats
title: Burst-window statistics for security.ratelimit
status: specified
primary_capability: security.ratelimit
related_capabilities: []
policies: []
spec_refs:
  - docs/spec/security/ratelimit.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
  - CR-007
depends_on: []
context_budget:
  max_tokens: 4000
  max_files: 6
---

## Slice: get_window_stats(key)

### In scope
- Add `get_window_stats(key)` to `security.ratelimit` returning `{accepted, rejected, remaining_tokens}`.
- Reset window counters alongside existing token-replenishment logic (CR-003).
- No token consumption or limit change on call (CR-004).
- Unknown-key behavior: zero counters + current remainder per key-initialization rules (CR-005, CR-007).

### Out of scope
- Any change to `consume`, `is_blocked`, capacity, or refill_rate semantics.
- New persistence or cross-service contracts.

### Dependencies
- Existing token-bucket implementation at `src/ratelimit` (CR-006): must already track per-key accepted/rejected counters and a current remainder.

### Spec references
- `docs/spec/security/ratelimit.md` REQ-RL-05, REQ-RL-06, REQ-RL-07 (newly added normative behavior).

### Unchanged behavior
- `consume(key, tokens)` (REQ-RL-02), `is_blocked` (REQ-RL-04), unknown-key full-capacity start (REQ-RL-03).

### Risks
- CR-007: exact `remaining_tokens` semantics for unknown keys must be resolved from existing implementation; low confidence, non-blocking for this slice.
- CR-006: verify counters already exist; if not, add minimal tracking without altering consume semantics.

### Context budget
- 4000 tokens / 6 files: read `src/ratelimit` implementation, `docs/spec/security/ratelimit.md`, and related tests only.

### Typed delta
- intent: feature; delta_kind: additive; requirement_delta: new REQ for `get_window_stats`; design_impact: minor (expose existing counters); risk: low; size: small.
