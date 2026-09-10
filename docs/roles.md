# Roles and Permissions

[**English**](roles.md) | [Русский](roles.ru.md)

DeltaFuse separates **Process** from **Thinker**. See [process-and-thinker.md](./process-and-thinker.md).

The Process is the lifecycle machine (kernel CLI). The Thinker is an LLM or a human who writes the same Change files. Human Gates are Process stops, not Thinker steps. No role may conflate "inventing a requirement" and "writing code for it" into a single unconstrained step.

---

## Fundamental Principles

1. **Specification is Primary**: AI only implements what is explicitly mandated by the accepted specification (`docs/spec/**`). Direct code implementation based on chat discussions, tickets, or correspondence is forbidden.
2. **Humans Approve Trade-offs**: All significant trade-offs (architectural, product, domain boundaries) must be documented in Decision Records and approved by a human.
3. **Strict TDD Gate**: Code implementation is blocked until an executable test target fails on unchanged code with recorded Red evidence.
4. **Immutability of Boundaries**: If unknowns or contradictions arise during implementation, the task returns to analysis; an agent is not allowed to implicitly invent a contract.

---

## AI Authority Limits (AI Must NOT)

The AI is **strictly forbidden** from:

- **Executing `git push`** to a remote repository.
- Executing destructive git commands (`git push --force`, `git reset --hard`, `git clean -f`, branch deletion).
- Merging changes into the default branch (`main` / `master`).
- Autonomously setting status to `accepted` or `rejected` in decision records (`docs/decisions/**`).
- Autonomously altering capability boundaries in `docs/spec/_capabilities.yaml` bypassing Human Gates.
- Making modifications to `docs/spec/**` without an authorized Change and approved Spec delta.
- Inventing product behaviors, contracts, or validations missing from the accepted specification.
- Relaxing assertions in tests merely to pass a test target.
- Modifying product code before recording verified Red evidence.
- Committing secrets, real tokens, passwords, or local absolute file paths.

---

## Human Gates

A Human Gate is a Process halt. Passing it is not Thinker work. Humans remain the final arbiters at five key gates:

| Human Gate | Description of Human Responsibility | Artifact |
|---|---|---|
| **Capability Boundary** | Approval of the initial capability map or capability catalog changes (`catalog delta`). | `docs/spec/_capabilities.yaml` |
| **Decision** | Acceptance or rejection of architectural, product, integration, or infrastructure decisions. | `docs/decisions/DEC-NNNN-*.md` (`status: accepted`) |
| **Specification** | Acceptance of baseline specification or updates to existing requirements (`spec delta`). | `docs/spec/**` (PR / merge) |
| **Scope Expansion** | Authorizing significant scope expansion or splitting a Change into multiple independent units. | `change.yaml`, `routing.yaml` |
| **Final Integration** | Final code review, merge conflict resolution, merging into `main`, and performing `git push`. | Git commit / PR merge / push |

---

## Process Participant Roles

Analyst, Spec Editor, Planner, Implementer, and Verifier are **Thinker** hats (LLM or human). Maintainer is **Human Gate** work.

| Role | Performer | Primary Responsibilities |
|---|---|---|
| **Intake Author / Auditor** | AI agent or human | Receive raw input, structure `CR-*` claims, validate artifacts without consulting spec. |
| **Analyst** | AI agent | Route claims to capabilities, compute typed deltas, draft decision proposals (`DEC-*`). |
| **Spec Editor** | AI drafts, **human approves** | Update `docs/spec/**`, mirror accepted Decisions into imperative requirement text. |
| **Task Planner** | AI agent | Decompose accepted specification into dependency-ordered atomic tasks with an explicit Test Oracle. |
| **Implementer** | AI agent | Author the declared Red oracle (Declare) and minimal product code (Implement / Green). |
| **Verifier** | AI agent | Verify end-to-end traceability, cross-layer convergence, and archive completed package. |
| **Maintainer** | **Human only** | Baseline approval, specification and code merge, release management and publishing. |

---

## Responsibility Matrix (RACI)

| Stage / Activity | AI Analyst / Planner | AI Implementer | AI Verifier | Human (Maintainer) |
|---|:---:|:---:|:---:|:---:|
| Raw intake normalization (`intake`) | **R** | — | — | **A** |
| Routing and deltas (`/analyze`) | **R** | — | — | **A** |
| Decision drafting (`DEC-NNNN proposed`) | **R** | — | — | C |
| **Decision acceptance (`status: accepted`)** | ❌ Forbidden | ❌ Forbidden | ❌ Forbidden | **Human only (A)** |
| Spec drafting (`/specify`) | **R** | — | — | C |
| **Specification acceptance (`docs/spec/`)** | ❌ Forbidden | ❌ Forbidden | ❌ Forbidden | **Human only (A)** |
| Task decomposition (`/decompose`) | **R** | C | — | **A** |
| Declare Red oracle (`/declare`) | — | **R** | — | C |
| Code writing & Green evidence (`/implement`) | — | **R** | — | C |
| Convergence check & archive (`/verify`) | — | — | **R** | **A** |
| **Code Review and Merge into main** | ❌ Forbidden | ❌ Forbidden | ❌ Forbidden | **Human only (A)** |
| **Git Push to remote repository** | ❌ Forbidden | ❌ Forbidden | ❌ Forbidden | **Human only (A)** |

*Legend: **R** (Responsible) — does work; **A** (Accountable) — approves / is accountable; **C** (Consulted) — provides input; **—** — not involved.*

---

## Orchestration Levels

The DeltaFuse lifecycle is built upon 7 canonical skill primitives (`process/skills/*`):
- `intake` — normalize raw request into `CHG-NNN`;
- `analyze` — route claims to capabilities and compute deltas;
- `specify` — apply deltas to normative specification;
- `decompose` — decompose into atomic implementation tasks;
- `declare` — declare what must become true (Red oracle) before Implement;
- `implement` — implement code and record Green/Regression evidence;
- `verify` — verify artifact convergence and archive package.

Those files bind the Thinker to an LLM. They are not the Process. The Process (`deltafuse next`, `evidence`, `check-gate`) selects the step and checks gates. Skills do not choose the next step.

### Execution Profiles

High-level operational workflows are orchestrated by invoking these canonical primitives in sequence:

1. **Standard Change (Feature / Specification Change)**:
   `intake` → `analyze` → *(Human Gate: Decisions)* → `specify` → *(Human Gate: Spec)* → `decompose` → task loop (`declare` → `implement`) → `verify` → *(Human Gate: Merge)*.
2. **Implementation Bug**:
   `intake` → `analyze` *(delta specification.operation: none)* → `specify` *(proof of unchanged spec in spec-delta.md)* → `decompose` *(bugfix task)* → `declare` *(Red evidence)* → `implement` *(Green evidence)* → `verify` → *(Human Gate: Merge)*.
3. **Bootstrap Profile**:
   Draft initial capability catalog `docs/spec/_capabilities.yaml`, resolve baseline architecture decisions (`docs/decisions/DEC-*` with `change: null`), and transition `project.baseline: accepted` in `.deltafuse/config.yaml` before running the first Change.

Any external automation or end-to-end agent orchestration (composite orchestration) must:
- Use strictly the 7 canonical framework primitives;
- Produce complete sets of normative artifacts at every step;
- Unconditionally halt at Human Gates. Automation must never blur role responsibilities or bypass human oversight.
