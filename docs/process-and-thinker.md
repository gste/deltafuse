# Process and Thinker

[**English**](process-and-thinker.md) | [Русский](process-and-thinker.ru.md)

DeltaFuse is two things. Do not mix them.

| Name | Russian | What it is | What it is not |
|---|---|---|---|
| **Process** | Процесс | The lifecycle machine: seven steps, FSM, gates, evidence, `next`, archive | An LLM. A person filling Change files. A second workflow for humans |
| **Thinker** | Мыслитель | LLM **or** human who writes the Change artifacts for the current step | The thing that chooses the next step, classifies Red/Green, or accepts Decisions |

The executable Process is the **kernel** CLI: `deltafuse next`, `evidence`, `check-gate`, `archive`, `board`. It reads product git. It does not invent claims, spec prose, tasks, or product code. It does not call a model.

The Thinker reads what the step allows and writes only that step's files. Same paths for LLM and human. Skills (`process/skills/*/SKILL.md`) bind the Thinker to an LLM. `deltafuse next --human` binds the same step to a person. There is no second lifecycle.

```text
Thinker  --Change files only-->  Product git
Process  --next / evidence / check-gate / archive-->  Product git
Process  --halt if gate fails-->  Thinker
```

## Human Gate is not a Thinker

A **Human Gate** (DEC / spec accept / merge) is a Process stop. Only a human may pass it. Filling `/analyze` or `/declare` as a person is Thinker work. Accepting `DEC-*` is Gate work. Same human, different hat. The Process must not auto-accept Gates. The Thinker must not pretend a Gate is a step.

## Do not say

| Avoid | Use |
|---|---|
| Worker / воркер as the top-level role | Thinker |
| Orchestrator inside the model | Process (`deltafuse next`) |
| LLM adapter as the name of the role | Thinker (LLM) — the skill is a binding |
| A people-only workflow | Same Process, human Thinker |
| Human Gate = Thinker | Human Gate = Process halt |
