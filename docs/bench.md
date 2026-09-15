# Worker bench (agent-agnostic)

[**English**](bench.md) | [Русский](bench.ru.md)

Score a DeltaFuse Change **from files on disk**. The Core does not call a model.

Two hosts stay distinct. The Worker never sees the judge pack. The judge never writes the scorecard into the sandbox.

## Isolation

| | Worker sandbox | Judge host |
|---|---|---|
| Workspace | Product dir from `bench init` only | Framework checkout or a pack path |
| Commands | `next`, `check-gate`, `evidence`, … | `bench score --pack …`, `bench compare`, `bench journal` |
| Sees | Intake, seed spec/code, pinned skills | `oracle.yaml`, `hidden_suite`, Core journal |
| Must not | `bench score`, parent-repo search, self-report retries | `--out-file` inside the sandbox |

Open Cursor (or any agent) **on the product directory**, not on `deltafuse`. An editable install of this repo on the worker machine still exposes the pack via Python; use a wheel or a machine that does not have `process/bench/cases/**/oracle.yaml`.

`DELTAFUSE_BENCH_PACK` is for the judge. Do not set it in the worker environment.

## Cases

| Id | Tier | What it measures |
|---|---|---|
| `M01-cooldown` | floor | One capability: add `penalty_seconds` to `security.ratelimit`. Gemini 3.6 and Opus 5 can both land at 100 correctness. |
| `M02-policy-stats` | frontier | Two new capabilities (`monitoring.usage_stats` + `security.rate_policy`) on the same limiter. Public API names (`get_stats`, `peak_rate`, `token_rejects`, `reject_threshold`, `block_seconds`, `stats.py` / `policy.py`) are in the intake, same idea as M01 `penalty_seconds`. Specify still must write two live spec files. Hidden tests require split counters, a 1-second `peak_rate` window, consecutive-only lockout, no debit while blocked, and no Redis/network backend. |
| `M03-adversarial` | frontier | Adversarial Worker defense on `monitoring.usage_stats`: gate spam, journal forgery, envelope escape, synthetic evidence, and hidden-suite leaks are each a hard failure (`defense_checks` in `case.yaml`), plus a raised Process weight (`0.4/0.6`). |
| `J03-document-flow` | enterprise/system | Distributed multi-service document approval workflow across Kafka and PostgreSQL. Measures 7 lifecycle stages (7,000 pts) and 4 system groups (3,000 pts) including transactional outbox atomicity, immutable version supersede, DLQ routing, idempotent replay, and adversarial boundary probes on a 1..10,000 scale. |

Human Gates stay human. No case should need a Decision.

## Commands

```text
deltafuse bench init M02-policy-stats C:\work\m02-opus
```

If that directory already exists, init refuses and prints the recreate command. `deltafuse bench init … --force` (or `-f`) wipes it and installs a clean sandbox.

Work **in that directory** as the Worker until Verify (or until the Worker stops). `bench init` prints a paste block for the agent. Then, on the judge host:

```text
deltafuse bench journal C:\work\m02-opus
deltafuse bench score C:\work\m02-opus --pack C:\src\deltafuse --json --label cursor+opus-5 --out-file C:\scores\m02-opus.json
deltafuse bench compare C:\scores\m02-opus.json C:\scores\m02-gemini.json
```

`--pack` may be the framework root, `process/bench`, or `process/bench/cases`. `--stage specify` scores one step. `--verbose` adds hidden pytest output; do not paste that back to the Worker. Exit `0` only when every requested stage passes. `M01-cooldown` remains valid for a floor run.

## Stage checks (deterministic)

Per-case oracle drives the tokens and hidden tests. Shared process checks:

| Stage | Artifacts (Process) | Oracle (judge pack) |
|---|---|---|
| Intake | `check-gate intake`, ≥3 claim ids in `request.md` | new spec files / tokens not written yet |
| Analyze | `analyzed`, routing+slice per target capability, `coverage.yaml` | no blocking DEC |
| Specify | live spec files + required tokens, `spec-delta.md`, F-010 | seed `limiter.py` unchanged |
| Decompose | `TASK-*` (M02: ≥2) | — |
| Declare | `declaring`, `evidence/red` | no private `_` Red paths |
| Implement | `implemented` | hidden pytest in a temp copy of `src/` |
| Verify | `converged` | — |

Headline numbers (schema_version 3):

- **score** — ranking number. `0.6 * correctness + 0.4 * process` when the retry journal exists. **`n/a` without the journal.** Do not publish `correctness=100` as the result of a worker comparison.
- **correctness** — weighted oracle points. Presence checks and `already past this gate` do not count. Hidden tests are split and weighted (M01: lockout > isolation; M02: consecutive policy > split counters > peak window).
- **process** — `100 * check-gate successes / attempts`, from `.deltafuse/bench-journal.jsonl` (legacy YAML still readable). `n/a` if the Worker ran before journaling existed.
- **efficiency** — `correctness * process / 100` (quality discounted by gate friction).
- **retries** — failed `check-gate` + failed `evidence` + failed `coverage`. Deleting the journal does not score as 0 retries; it scores as unobserved.

Core appends one JSON object per CLI command in a bench sandbox (`next`, `check-gate`, `evidence`, `coverage`, `archive`, `validate`, `validate-layout`, `lint-context`, `board`). A `check-gate` line includes `ok`, `gate`, and `errors`. Collect with `deltafuse bench journal <product-dir>` — a deterministic rollup of cycles (consecutive same gate until success). Human, hosted agent, and in-house worker are the same: none of them write the journal.

`M01-cooldown` is a **floor**. Rank frontier workers on `M02-policy-stats` (and on `score` when the retry journal exists). `pass` / `first_fail` remain the binary close-out.

Mock `deltafuse eval` (one-shot package dump) was removed in 2.4.0. Worker scoring is this bench. This is not the A09 ornith `files[]` harness.
