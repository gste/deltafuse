---
name: analyze-change
description: Route a normalized DeltaFuse Change through product capabilities, compare bounded slices with accepted specification and Decisions, and compute typed deltas. Use iteratively until blocking Decisions converge.
---

# Analyze Change

Turn claims into bounded, evidence-backed deltas. This is the lifecycle's iterative Decision-convergence step.

Resolve artifact roots and context limits from `.deltafuse/config.yaml`; paths shown below are defaults.

## Context

Start with `request.md`, `docs/spec/_capabilities.yaml`, compact global policy summaries, and the configured context budget. Route before loading detailed specification.

After routing, read only selected spec modules, related Decision records, and explicitly requested diagnostic evidence. Do not load the whole spec, codebase, tests, or unrelated Changes/tasks by default.

## Procedure

1. Assign every `CR-*` claim one owning capability plus optional related capabilities and policies in `routing.yaml`.
2. Split the Change into analytical slices with one primary capability and independently verifiable outcome.
3. For each slice record in/out of scope, dependencies, exact spec references, unchanged behavior, risks, and context budget.
4. Classify independently: `intent`, `delta_kind`, `requirement_delta`, `design_impact`, `risk`, and `size`.
5. Compute an explicit delta projection for specification, catalog, Decisions, tasks, tests, implementation, and evidence; use `operation: none` where considered but unchanged.
6. Create proposed Decision records for material product, architecture, integration, policy, or operational choices. Do not accept them.
7. Re-run only affected slices after human clarification or a terminal Decision.
8. Perform global reconciliation over slice summaries, dependency graph, claim coverage, policies, and Decision statuses.

If context exceeds budget, split by connected capability components and outcomes; add integration slices instead of truncating context.

## Gate

Exit only when all claims are routed, every slice has a typed delta, blocking Decisions are terminal, accepted choices are represented in deltas, and reconciliation creates no new blocking question.

Write `analysis.md`, `routing.yaml`, `slices/**`, `coverage.yaml`, Decision/catalog proposals, and updated `change.yaml`. Recommend `/specify-change <change-id> [slice-id]`.

Read `.deltafuse/lock.yaml` `workflow.call_width` (`narrow` | `medium` | `wide`, default `wide`). Always write `routing.yaml` first. `narrow` writes one of routing, slices, or coverage per invocation; `medium` writes routing, then slices and coverage together; `wide` may finish Analyze in one invocation. Leave status `analyzing` until routing, slices, and coverage are on disk — call width does not close the gate. Do not skip Specify. Do not auto-accept Decisions.

Set `route` on `change.yaml` and `routing.yaml` to `code` (default), `docs`, or `ops`. `docs`/`ops` do not skip Specify.
