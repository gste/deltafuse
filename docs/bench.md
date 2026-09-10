# Worker bench (agent-agnostic)

[**English**](bench.md) | [Русский](bench.ru.md)

Score a DeltaFuse Change **from files on disk**. The Core does not call a model. Cursor, Claude, Gemini, a human, or a future sandboxed agent all fill the same product tree.

## Case

`M01-cooldown` — add `penalty_seconds` to an existing `security.ratelimit` limiter. One capability, full lifecycle, hidden acceptance tests kept out of the product.

Oracle and `hidden_suite` stay in `process/bench/cases/M01-cooldown/`. Init does not copy them.

## Commands

```text
deltafuse bench init M01-cooldown C:\work\m01-opus
```

Work in that directory as the Worker: `deltafuse next`, pinned skills, `check-gate`. After each step (or at the end):

```text
deltafuse bench score C:\work\m01-opus --json --label opus-5 --out-file opus.json
deltafuse bench init M01-cooldown C:\work\m01-flash
deltafuse bench score C:\work\m01-flash --json --label gemini-flash --out-file flash.json
deltafuse bench compare opus.json flash.json
```

`--stage specify` scores one step. Exit `0` only when every requested stage passes.

## Stage checks (deterministic)

| Stage | Artifacts | Oracle |
|---|---|---|
| Intake | `check-gate intake`, ≥3 claim ids in `request.md` | no `penalty_seconds` in live spec yet |
| Analyze | `analyzed`, routing+slice `security.ratelimit`, `coverage.yaml` | no blocking DEC on this case |
| Specify | live spec contains `penalty_seconds`, `spec-delta.md`, F-010 | seed `limiter.py` unchanged |
| Decompose | ≥1 `TASK-*` | — |
| Declare | `targeting`, `evidence/red` | no private `_` Red paths |
| Implement | `implemented` | hidden pytest in a temp copy of `src/` |
| Verify | `converged` | — |

Do not copy hidden tests into the product `tests/` (the scorer flags that leak).

Human Gates stay human. This case should not need a Decision.

This is not `deltafuse eval --provider mock` (one-shot package dump) and not the A09 ornith `files[]` harness.
