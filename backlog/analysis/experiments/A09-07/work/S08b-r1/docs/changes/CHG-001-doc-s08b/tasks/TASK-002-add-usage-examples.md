---
id: TASK-002
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

# TASK-002 — Add «Примеры использования» section

## Outcome

`docs/spec/security/ratelimit.md` contains a «Примеры использования» section with exactly three scenarios: initialization, consume with verification, and ValueError handling, each with a runnable Python code block.

## Context

- Change: CHG-001-doc-s08b; Slice: SLICE-01
- Claims: CR-002 (expectation)
- Spec refs: `docs/spec/security/ratelimit.md`

## Steps

1. Open `docs/spec/security/ratelimit.md`.
2. Ensure a `## Примеры использования` heading exists (add if missing), placed after the REQ-RL-* block.
3. Add three subsections:
   - `### Инициализация` — construct `TokenBucketLimiter(capacity=10, refill_rate=1)`.
   - `### Потребление с проверкой` — `if limiter.consume("user:42", tokens=3):` with proceed/reject branches.
   - `### Обработка ValueError` — `consume` with negative tokens wrapped in `try/except ValueError`.
4. Each scenario uses a fenced ```python code block.

## Test oracle

- `grep -c «### Инициализация» docs/spec/security/ratelimit.md` == 1
- `grep -c «### Потребление с проверкой» docs/spec/security/ratelimit.md` == 1
- `grep -c «### Обработка ValueError» docs/spec/security/ratelimit.md` == 1
- All three code blocks are valid Python syntax (parse with `python -m py_compile` on extracted snippets).

## Unchanged behavior

- REQ-RL-* normative text is untouched; only additive prose.
- No other file is modified.

## Verification

```bash
grep -n «## Примеры использования» docs/spec/security/ratelimit.md
grep -n «### Инициализация» docs/spec/security/ratelimit.md
grep -n «### Потребление с проверкой» docs/spec/security/ratelimit.md
grep -n «### Обработка ValueError» docs/spec/security/ratelimit.md
```
