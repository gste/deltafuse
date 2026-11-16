# Core and Worker

[**English**](core-and-worker.md) | [Русский](core-and-worker.ru.md)

**Process** is the lifecycle we follow (`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`). It lives in [workflow.md](./workflow.md). Process is not a runtime role.

Two runtime roles sit on that Process. Do not mix them.

| Name | Russian | What it is | What it is not |
|---|---|---|---|
| **Core** | Ядро | The machine that enforces the Process: FSM, gates, evidence, `next`, archive, `board` | An LLM. A person filling Change files. The Process description itself |
| **Worker** | Воркер | LLM **or** human who writes the Change artifacts for the current step | A CI/OS job. The work queue. A Human Gate. The thing that chooses the next step or classifies Red/Green |

The Core is the kernel CLI: `deltafuse next`, `evidence`, `advance` (gate check + transition; `check-gate` is its read-only preview), `state`, `decide`, `archive`, `board`, and `artifact write`. It reads product git and provides a typed Artifact Writer serialization service for atomic file updates. It does not invent claims, spec prose, tasks, or product code. It does not call a model.

The Worker reads what the step allows and writes only that step's files. Same paths for LLM and human. Skills (`process/skills/*/SKILL.md`) bind the Worker to an LLM. `deltafuse next --human` binds the same step to a person. There is no second process for humans.

```text
Worker  --Change files only-->  Product git
Core    --next / evidence / advance / archive-->  Product git
Core    --halt if gate fails-->  Worker
```

## Why "Worker" and not a CI worker

In this repository **Worker** always means the step executor (`llm | human`). It is not:

- a GitHub Actions / queue job;
- an OS worker process;
- the derived work queue (`deltafuse next --list`) — that list is Core;
- a **Human Gate**.

If a sentence is about jobs, queues, or merge, do not say Worker.

## Human Gate is not a Worker

A **Human Gate** (DEC / spec accept / merge) is a stop in the Process. Only a human may pass it. Filling `/analyze` or `/declare` as a person is Worker work. Accepting `DEC-*` is Gate work. Same human, different hat. The Core must not auto-accept Gates. The Worker must not pretend a Gate is a step.

What the Core can verify: a verdict was written by `deltafuse decide`, which records a receipt bound to the bytes answered, and nothing changed it since. It cannot tell who ran `decide`. Without a Human Gate password (`deltafuse gate-password set`) a Worker that runs `decide` itself passes the Gate, and its receipt reads `human_check: none` like the human's. With one, `decide` reads the password only from an interactive console (`human_check: password`); the password file is still a file in the working tree, so a Worker that moves it aside answers with `human_check: none` again. Read `human_check` in the gate journal; against a Worker that edits files on purpose, isolate it on the host.

## What the Core does not stop

The Core is built against a Worker that errs, not one that attacks it. It refuses what a model reaches by mistake or while trying to get to green: a partial test run, a test file run directly, a weakened test, a relaxed leash, widened task paths, a `--no-verify` commit, a junk or hand-written record, a hand-edited `coverage.yaml`. A Worker with the same shell as the human can still forge on purpose, and the Core does not claim otherwise:

- Receipts in `.deltafuse/` (transitions, gate journal, Artifact Writer receipts) are not keyed: a crafted one has the Core's shape. Moving the gate-password file aside answers a Gate with `human_check: none`.
- The isolated Red oracle run drops `-p`, `-o addopts`, unfrozen `-c` files and `PYTEST_ADDOPTS`/`PYTEST_PLUGINS`; a plugin installed as a package entry point still loads.
- A clean `git merge` runs no `pre-commit` hook; removing the lock in a `--no-verify` commit makes the branch one without DeltaFuse.
- Environment failures of a Red are recognised from pytest's report only; on the JVM a missing resource or `NoClassDefFoundError` reads as a behavioural failure.
- Only a bare interpreter (`python <file>.py`, `python -c`) is refused as a report-less runner; `tox`, `npm test` and the like still run without a report. Without `workflow.test_commands`, "the whole suite" is judged heuristically.
- Maven reports are read at the root and one module level deep.
- A product installed from the wheel pins the digest of the bundled assets (`assets/manifest.json`), not of the Core's code; a source checkout pins both.

The backstop for all of these is outside the Worker's reach: the CI leash job, the human's review of the diff, and host isolation of the Worker.

## Through-mode

Default LLM Worker entry is `/run`. The Worker calls `deltafuse next`, loads the named skill, and continues in the same session. The human does not paste each slash command.

The loop stops only when:

1. `halt.kind` is `decision` — present `halt.choices`, wait, then `deltafuse decide --decision …`.
2. `halt.kind` is `spec` — present `halt.choices`, wait, then `deltafuse decide --spec …`.
3. A gate fails, a task is blocked, or the human chose inspect — stop so they can look, then restart `/run` or the named step.

The host button list is the [halt contract](./contracts/halt.md). `deltafuse decide` records the click; it is not auto-accept. Core does not draw UI. Merge and `git push` stay Human Gates; through-mode must not push. The write allow-list is [envelope](./contracts/leash.md): the host MUST restrict write-tools to `envelope.write`. If it cannot, `/run` still calls `deltafuse leash` before leaving the step (not a substitute for the git hook). Fuse-map UI and Cursor buttons live outside `src/deltafuse/**` and read [board-snapshot](./contracts/board-snapshot.md).

Single-step slash commands remain for restarting one step after a problem.
