# Worker bench (agent-agnostic)

[**English**](bench.md) | [Русский](bench.ru.md)

Score a DeltaFuse Change **from files on disk**. The Core does not call a model.

Two hosts stay distinct. The Worker never sees the judge pack. The judge never writes the scorecard into the sandbox.

## Isolation

| | Worker sandbox | Judge host |
|---|---|---|
| Workspace | Product dir from `bench init` only | Framework checkout or a pack path |
| Commands | `next`, `check-gate`, `evidence` | `bench score --pack …`, `bench compare` |
| Sees | Intake, seed spec/code, pinned skills | `oracle.yaml`, `hidden_suite` |
| Must not | `bench score`, parent-repo search | `--out-file` inside the sandbox |

Open Cursor (or any agent) **on the product directory**, not on `delta-fuse`. An editable install of this repo on the worker machine still exposes the pack via Python; use a wheel or a machine that does not have `process/bench/cases/**/oracle.yaml`.

`DELTAFUSE_BENCH_PACK` is for the judge. Do not set it in the worker environment.

## Case

`M01-cooldown` — add `penalty_seconds` to an existing `security.ratelimit` limiter. One capability, full lifecycle.

## Commands

```text
deltafuse bench init M01-cooldown C:\work\m01-opus
```

Work **in that directory** as the Worker until Verify (or until the Worker stops). Then, on the judge host:

```text
deltafuse bench score C:\work\m01-opus --pack C:\src\delta-fuse --json --label cursor+opus-5 --out-file C:\scores\opus.json
deltafuse bench compare C:\scores\opus.json C:\scores\flash.json
```

`--pack` may be the framework root, `process/bench`, or `process/bench/cases`. `--stage specify` scores one step. `--verbose` adds hidden pytest output; do not paste that back to the Worker. Exit `0` only when every requested stage passes.

## Stage checks (deterministic)

| Stage | Artifacts (Process) | Oracle (judge pack) |
|---|---|---|
| Intake | `check-gate intake`, ≥3 claim ids in `request.md` | no `penalty_seconds` in live spec yet |
| Analyze | `analyzed`, routing+slice `security.ratelimit`, `coverage.yaml` | no blocking DEC on this case |
| Specify | live spec contains `penalty_seconds`, `spec-delta.md`, F-010 | seed `limiter.py` unchanged |
| Decompose | ≥1 `TASK-*` | — |
| Declare | `targeting`, `evidence/red` | no private `_` Red paths |
| Implement | `implemented` | hidden pytest in a temp copy of `src/` |
| Verify | `converged` | — |

Headline metric: vector of seven stage bits + `first_fail`. Do not fold that into one float as the primary score.

Human Gates stay human. This case should not need a Decision.

This is not `deltafuse eval --provider mock` (one-shot package dump) and not the A09 ornith `files[]` harness.
