---
id: TASK-003
change: CHG-001-doc-s08b
slice: SLICE-01
kind: documentation
status: targeting
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/security/ratelimit.md
allowed_paths:
  - docs/spec/security/ratelimit.md
forbidden_paths:
  - src/ratelimit
  - tests
  - docs/spec/_capabilities.yaml
---

# TASK-003 — Add «Архитектурные решения» section

## Outcome

`docs/spec/security/ratelimit.md` contains an «Архитектурные решения» section that describes the Token Bucket choice, cites RFC 2697, and compares Token Bucket with Leaky Bucket.

## Context

- Change: CHG-001-doc-s08b; Slice: SLICE-01
- Claims: CR-003 (expectation)
- Spec refs: `docs/spec/security/ratelimit.md`

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Ensure an `## Архитектурные решения` heading exists (add if missing), placed after the «Примеры использования» section.
3. Add a `### Выбор алгоритма: Token Bucket` subsection that:
   - States Token Bucket (RFC 2697) was chosen.
   - Justifies the choice (allows bursts via accumulated tokens, variable `refill_rate`, O(1) `consume`).
   - Compares with Leaky Bucket (Leaky Bucket smooths/rejects bursts; Token Bucket permits them; Token Bucket preferred for pulsing workloads).
   - Cites RFC 2697.

## Test oracle

- `grep -n «## Архитектурные решения» docs/spec/security/ratelimit.md` returns one match.
- `grep -n «RFC 2697» docs/spec/security/ratelimit.md` returns at least one match.
- `grep -n «Leaky Bucket» docs/spec/security/ratelimit.md` returns at least one match.

## Unchanged behavior

- REQ-RL-* normative text is untouched; only additive prose.
- No other file is modified.

## Verification

```bash
grep -n «## Архитектурные решения» docs/spec/security/ratelimit.md
grep -n «RFC 2697» docs/spec/security/ratelimit.md
grep -n «Leaky Bucket» docs/spec/security/ratelimit.md
```
