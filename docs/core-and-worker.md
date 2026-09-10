# Core and Worker

[**English**](core-and-worker.md) | [Русский](core-and-worker.ru.md)

**Process** is the lifecycle we follow (`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`). It lives in [workflow.md](./workflow.md). Process is not a runtime role.

Two runtime roles sit on that Process. Do not mix them.

| Name | Russian | What it is | What it is not |
|---|---|---|---|
| **Core** | Ядро | The machine that enforces the Process: FSM, gates, evidence, `next`, archive, `board` | An LLM. A person filling Change files. The Process description itself |
| **Worker** | Воркер | LLM **or** human who writes the Change artifacts for the current step | A CI/OS job. The work queue. A Human Gate. The thing that chooses the next step or classifies Red/Green |

The Core is the kernel CLI: `deltafuse next`, `evidence`, `check-gate`, `archive`, `board`. It reads product git. It does not invent claims, spec prose, tasks, or product code. It does not call a model.

The Worker reads what the step allows and writes only that step's files. Same paths for LLM and human. Skills (`process/skills/*/SKILL.md`) bind the Worker to an LLM. `deltafuse next --human` binds the same step to a person. There is no second process for humans.

```text
Worker  --Change files only-->  Product git
Core    --next / evidence / check-gate / archive-->  Product git
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
