# Start here — J03 implementation handoff

**Current request: planning only.** This directory now contains a future
implementation plan, not an implemented/qualified benchmark.
Target: **DeltaFuse 3.0.0**, never the old FuseMap 2.4.0 checkout.

## Read in this order

1. [PLAN.md](PLAN.md) — queue, dependencies and package exit gates.
2. [EXECUTOR.md](EXECUTOR.md) — rules for the smaller implementation LLM.
3. Only the next ready [task card](cards/J03-000.md) and its named inputs.
4. The relevant sections of [INSTRUCTION.md](INSTRUCTION.md), the source intent.
5. Relevant sections of [CONTRACTS.md](CONTRACTS.md),
   [SCORING-PLAN.md](SCORING-PLAN.md), and [DECISIONS.md](DECISIONS.md).

Do not load every card or the entire source tree into one model context.
[queue.json](queue.json) is the machine-readable dependency graph.
[COVERAGE.md](COVERAGE.md) maps acceptance criteria to tasks.
[MUTATION-PLAN.md](MUTATION-PLAN.md) names 28 required calibration candidates.
[THREAT-MODEL-PLAN.md](THREAT-MODEL-PLAN.md) maps attack surfaces to controls.
[RUNBOOK.md](RUNBOOK.md) gives future verification commands and evidence rules.
[RESULT-TEMPLATE.md](RESULT-TEMPLATE.md) defines the package handoff record.

## First future implementation task

**J03-000: capture qualified framework baseline.** Wave 3/QF-025 and a clean
3.0.0 revision are implementation prerequisites, not prerequisites to planning.
If those are still unfinished, record J03-000 as blocked. Do not repair Wave 3,
consume its dirty files, or start benchmark implementation on an old snapshot.

The next implementation session must remeasure repository status. This plan
was authored while unrelated asset qualification edits were active.
No pending qualification modification belongs to a benchmark card.

## Planning observations (2026-09-13)

- Observed target HEAD: db15ca24cc6af128920165fb7c57d6a18c382978.
- Docker daemon verified outside the restricted sandbox: Engine 29.7.2,
  Docker Desktop 4.90.0, linux/amd64. Sandbox pipe access alone was denied.
  This establishes daemon availability, not a qualified Java/Kafka stack.
- Installed little-coder package.json reports 1.19.0, a pi-based external
  agent. The local README documents RPC mode and extension discovery.
  Reinspect exact transitive versions and hooks before implementing.
- Java 21, pinned dependencies, model endpoint and qualification evidence
  still need future preflight. No agent/model run was made during planning.

## Copy-paste prompt for a smaller implementation LLM

> Work in the DeltaFuse 3.0.0 framework repository. Read
> backlog/product/v3/document-flow-benchmark/EXECUTOR.md and PLAN.md.
> Use queue.json to select the first planned card whose dependencies are
> verified complete; start with J03-000 if none are complete.
> Execute exactly one bounded card, respecting its allowed files and
> INSTRUCTION.md. Preserve unrelated changes. Record evidence and handoff.
> Do not implement the target product Change in the public seed.
> Do not run the external benchmark Worker before calibration passes.
> Do not claim completion from unit tests alone. Stop after this card and
> report the next ready card or exact blocker.
