---
name: analyze
description: Route a normalized DeltaFuse Change through product capabilities, compare bounded slices with accepted specification and Decisions, and compute typed deltas. Use iteratively until blocking Decisions converge.
---

# Analyze

Turn claims into bounded, evidence-backed deltas. This is the lifecycle's iterative Decision-convergence step.

Resolve artifact roots and context limits from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If no Change was named, run `deltafuse next --step analyze` at the product root and use `path` plus `analyze_pass`. Halt if it exits non-zero.
2. Write only the named pass. Do not write routing, all slices, and coverage in one invocation.
   - `routing`: `routing.yaml` from `request.md` and `docs/spec/_capabilities.yaml`. Do not load spec module bodies.
   - `slice`: one `slices/<slice_id>.md` for `capability`. Read only `spec_refs` from `next`. Do not collapse two capabilities into one file.
   - `coverage`: `coverage.yaml` from routing and slice frontmatter. Do not reload spec bodies.
3. If `analyze_pass` is `coverage`, close with `deltafuse check-gate <change-dir> --gate analyzed`. Halt if it exits non-zero. For `routing` or `slice`, do not call `check-gate --gate analyzed`.
4. Then run `deltafuse next`. Do not choose the next slash command yourself.
5. Do not auto-accept Decisions or merge.

## Context

Start with what `next` lists in `allowed_read`. Route before loading detailed specification.

After routing, read only the spec modules in `spec_refs` for the named capability, related Decision records, and explicitly requested diagnostic evidence. Do not load the whole spec, codebase, tests, or unrelated Changes/tasks.

## Procedure

1. Assign every `CR-*` claim one owning capability plus optional related capabilities and policies in `routing.yaml`.
2. Split the Change into analytical slices with one primary capability and independently verifiable outcome. Write one `slices/SLICE-NN.md` per primary capability (`SLICE-01`, `SLICE-02`, …). Do not collapse a multi-capability Change into a single `SLICE-01`. The Core names the next capability; write that file only.
3. For each slice record in/out of scope, dependencies, exact spec references, unchanged behavior, risks, and context budget.
4. Classify independently: `intent`, `delta_kind`, `requirement_delta`, `design_impact`, `risk`, and `size`.
5. Compute an explicit delta projection for specification, catalog, Decisions, tasks, tests, implementation, and evidence; use `operation: none` where considered but unchanged.
6. Create proposed Decision records for material product, architecture, integration, policy, or operational choices. Do not accept them.
7. Re-run only affected slices after human clarification or a terminal Decision.
8. Perform global reconciliation in the coverage pass over slice summaries, dependency graph, claim coverage, policies, and Decision statuses.

If context exceeds budget, split by connected capability components and outcomes; add integration slices instead of truncating context.

## Gate

Exit only when all claims are routed, every routing primary capability has a slice, every slice has a typed delta, blocking Decisions are terminal, accepted choices are represented in deltas, and reconciliation creates no new blocking question.

Write `routing.yaml`, `slices/**`, `coverage.yaml`, Decision/catalog proposals, and updated `change.yaml`. `analysis.md` is optional.

`deltafuse next` always selects one Analyze pass (`routing` | one `slice` | `coverage`), including when lock `workflow.call_width` is `wide`. Leave status `analyzing` until routing, slices, and coverage are on disk — call width does not close the gate. Do not skip Specify. Do not auto-accept Decisions.

Set `route` on `change.yaml` and `routing.yaml` to `code` (default), `docs`, or `ops`. `docs`/`ops` do not skip Specify.

Unknown top-level keys on `routing.yaml` (including `schema_version`) do not fail `analyzed`. `routing.yaml` itself remains required. Two slice files do not satisfy Specify without live `docs/spec/**`.

`analysis.md` is optional. `analyzed` is routing, slices (one per routing primary capability), and coverage; `change.yaml` `analysis.summary` may be null.
