# Spec Delta — CHG-008-ops-rate-limiter-migration

Scope: SLICE-01 (ops migration of Rate Limiter deployment config, health check, and runbook).

This Change is a pure operational migration. It updates deployment configuration,
health-check monitoring, and the ops runbook. It does not alter product code,
specifications, or tests, and has no impact on product functionality.

## Unchanged

- `docs/spec/security/ratelimit.md` (REQ-RL-01..04): token-bucket limiter behavior,
  capacity, refill, consume, and is_blocked are unchanged. No ADDED/MODIFIED/REMOVED.
- No capability catalog delta required; `ratelimit` capability remains `active`.
- No accepted Decision affects observable behavior, contract, policy, or invariant.

## Conclusion

No normative specification change. `requirement_delta: none`. The accepted
`spec_refs` proving sufficiency is `docs/spec/security/ratelimit.md`, which
describes the unchanged normative behavior. No spec edits were made.
