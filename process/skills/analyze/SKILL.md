---
name: analyze
description: Route a normalized DeltaFuse Change through product capabilities, compare bounded slices with accepted specification and Decisions, and compute typed deltas. Use iteratively until blocking Decisions converge.
---

# Analyze

Turn claims into bounded, evidence-backed deltas. This is the lifecycle's iterative Decision-convergence step.

Resolve artifact roots and context limits from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, `coverage`, and `check-gate`.

1. If no Change was named, run `deltafuse next --step analyze` at the product root and use `path` plus `analyze_pass`. Halt if it exits non-zero.
2. Write only the named pass. Do not write routing, all slices, and coverage in one invocation.
   - `routing`: `routing.yaml` from `request.md` and `docs/spec/_capabilities.yaml`. Do not load spec module bodies.
   - `slice`: one `slices/<slice_id>.md` for `capability`. Read only `spec_refs` from `next`. Do not collapse two capabilities into one file.
   - `coverage`: run `deltafuse coverage <change-dir>`. Do not hand-write `coverage.yaml`.
3. If `analyze_pass` is `coverage`, run `deltafuse coverage <change-dir>` if needed, then close with `deltafuse check-gate <change-dir> --gate analyzed`. Halt if it exits non-zero. For `routing` or `slice`, do not call `check-gate --gate analyzed`.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run the matching `deltafuse decide` command, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Start with what `next` lists in `allowed_read`. Route before loading detailed specification.

After routing, read only the spec modules in `spec_refs` for the named capability, related Decision records, and explicitly requested diagnostic evidence. Do not load the whole spec, codebase, tests, or unrelated Changes/tasks.

## Procedure

1. Assign every `CR-001`-style claim (three digits, not `CR-01`) one `primary_capability` plus optional related capabilities and policies in `routing.yaml`. `claims` is a map, not a list. The field name is `primary_capability`, not `capability` or `primary`.
2. Split the Change into analytical slices with one primary capability and independently verifiable outcome. Write one `slices/SLICE-NN.md` per primary capability (`SLICE-01`, `SLICE-02`, …). Do not collapse a multi-capability Change into a single `SLICE-01`. The Core names the next capability; write that file only. Slice frontmatter uses only slice schema keys (`id`, `change`, `title`, `status: draft`, `primary_capability`, `claims`, …). Put `intent` / `risk` / `size` in the markdown body. In `change.yaml`, `slices` is a list of `{id, status, file}` objects, not strings.
3. For each slice record in/out of scope, dependencies, exact spec references, unchanged behavior, risks, and context budget.
4. Classify independently in the slice markdown body, not as extra frontmatter keys: `intent`, `delta_kind`, `requirement_delta`, `design_impact`, `risk`, and `size`.
5. Compute an explicit delta projection for specification, catalog, Decisions, tasks, tests, implementation, and evidence; use `operation: none` where considered but unchanged.
6. Create proposed Decision records for material product, architecture, integration, policy, or operational choices. Do not accept them.
7. Re-run only affected slices after human clarification or a terminal Decision.
8. Do not invent `coverage.yaml`. The Core writes it from routing and slice frontmatter (`deltafuse coverage`).

If context exceeds budget, split by connected capability components and outcomes; add integration slices instead of truncating context.

## Gate

Exit only when all claims are routed, every routing primary capability has a slice, every slice has a typed delta, blocking Decisions are terminal, accepted choices are represented in deltas, and reconciliation creates no new blocking question.

Write `routing.yaml`, `slices/**`, Decision/catalog proposals, and updated `change.yaml`. The Core writes `coverage.yaml`. `analysis.md` is optional.

`deltafuse next` always selects one Analyze pass (`routing` | one `slice` | `coverage`), including when lock `workflow.call_width` is `wide`. Leave status `analyzing` until routing, slices, and coverage are on disk — call width does not close the gate. Do not skip Specify. Do not auto-accept Decisions.

Set `route` on `change.yaml` and `routing.yaml` to `code` (default), `docs`, or `ops`. `docs`/`ops` do not skip Specify.

Unknown top-level keys on `routing.yaml` and `coverage.yaml` (including `schema_version`) do not fail `analyzed`. `routing.yaml` itself remains required. Two slice files do not satisfy Specify without live `docs/spec/**`.

`analysis.md` is optional. `analyzed` is routing, slices (one per routing primary capability), and coverage; `change.yaml` `analysis.summary` may be null.
