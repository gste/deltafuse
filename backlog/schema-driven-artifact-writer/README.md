# Schema-driven Artifact Writer

Status: **implementation requires remediation; acceptance open**.
Source intent: [INTENTION.md](INTENTION.md), preserved from the user's proposal.
Analysis: [ANALYSIS.md](ANALYSIS.md). Plan: [PLAN.md](PLAN.md).
Contracts: [CONTRACT.md](CONTRACT.md). Test/evaluation: [VALIDATION.md](VALIDATION.md).
Next task: [AW-37](cards/AW-37.md). Machine queue: [queue.json](queue.json).
Current review: [REVIEW-5.md](REVIEW-5.md). AW-37/AW-40/AW-41/AW-42/AW-20 are reopened; AW-38/AW-39 fixes remain verified.
AW-20 closure is reopened; earlier completion reports are historical claims.

## Recommendation

Adopt a deterministic writer **inside the Core implementation**, exposed through
a small typed operation API and CLI. It is a serialization/persistence service,
not a third runtime actor. Workers own content; Core remains the only owner of
authorization, state transitions, Human Gates and authentic execution evidence.

Start with task/slice/spec-delta frontmatter, routing, and controlled Change
metadata updates; use the same persistence service beneath Core evidence,
status, scaffolding and coverage commands. Do not give a Worker a generic
status/evidence-stamp setter.

Target repository: the canonical sibling selected in this conversation.
Observed VERSION **3.1.0**, HEAD **17786cb040d1ed3cd5636dd4a6b97453c1b77627**,
2026-09-18. This is a planning snapshot, not a qualification claim.
The earlier 3.0.0 benchmark plan is not a prerequisite to this independent
framework feature. Re-read current HEAD and contracts when implementing.

## Contents and handoff

- [ANALYSIS.md](ANALYSIS.md): current-code findings, benefits, limits, tradeoffs.
- [CONTRACT.md](CONTRACT.md): supported kinds, ownership, patches, authorization,
  concurrency, receipts and compatibility.
- [PLAN.md](PLAN.md): bounded implementation cards and dependency order.
- [VALIDATION.md](VALIDATION.md): acceptance matrix, negative tests, Windows/POSIX
  checks and paired small-model experiment.
- [EXECUTOR.md](EXECUTOR.md): one-card implementation prompt and result protocol.
- [evidence/probe.py](evidence/probe.py) and
  [evidence/probe-result.json](evidence/probe-result.json): read-only characterization.
- [PLAN-REVIEW.md](PLAN-REVIEW.md): structural plan checks, not implementation tests.

The original planning snapshot above predates implementation. The 2026-09-19
review found mandatory implementation and qualification gaps. Follow REVIEW-2.md
and queue.json for current work; no external-model benefit is established by
the existing fixed-input evaluation report.

Execution requires [EXECUTOR.md](EXECUTOR.md) and the
[RESULT-TEMPLATE.md](RESULT-TEMPLATE.md) acceptance matrix. No mandatory
unavailable evidence may be marked complete.
