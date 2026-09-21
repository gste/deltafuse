---
name: specify
description: Apply one analyzed DeltaFuse slice to the normative product specification, or prove the accepted specification is unchanged. Use after analysis and Decision convergence, before task decomposition.
---

# Specify

Establish the normative state from which tasks may be derived.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, `coverage`, `check-gate`, and `decide`.

1. If no Change was named, run `deltafuse next --step specify` at the product root and use `path` plus `specify_pass`. Halt if it exits non-zero.
2. Write only the named pass.
   - `slice`: live `docs/spec/**` files listed in `spec_refs` (and `_capabilities.yaml` only for an accepted catalog delta). Append that slice to `spec-delta.md`. Record the Core-owned slice state: `deltafuse state <change-dir> --slice <slice-id> --status specified`. Do not load other spec modules.
   - `close`: record the Core-owned Change in-flight status `deltafuse state <change-dir> --change --status specification-proposed`. If the Core refuses, fix the listed errors and run it again. Never set `specified` or any other status by hand. Do not invent new requirements.
3. If `specify_pass` is `close`, close with `deltafuse check-gate <change-dir> --gate specified`. Halt if it exits non-zero. Then run `deltafuse advance <change-dir> --gate specified` so the Core stamps the transition; halt if that exits non-zero. For `slice`, do not call `check-gate --gate specified`.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read the named slice, its typed delta, `spec_refs` from `next`, accepted related Decisions/catalog delta, and only those specification files. Do not read the whole spec, codebase, or unrelated Changes.

## Procedure

1. If `requirement_delta` changes requirements, write a bounded `spec-delta.md`. Its frontmatter is required in exactly this shape - lowercase keys, every list present even when empty, each entry a spec path with the requirement anchor; no other keys:

   ```yaml
   ---
   change: CHG-001-example
   status: proposed
   slices: [SLICE-01]
   added: [docs/spec/<domain>/<capability>.md#REQ-ID]
   modified: []
   removed: []
   ---
   ```

   The body may repeat them under `## ADDED`, `## MODIFIED`, `## REMOVED` for the human. Use stable requirement/scenario IDs. Added/modified paths must stay inside this slice's `spec_refs`.
2. Edit only declared specification files and requirements. Keep the live spec imperative and free of change-log prose.
3. Apply an accepted capability catalog delta when required.
4. Mirror every accepted Decision that affects observable behavior, a contract, policy, or required invariant into the named spec files.
5. If `requirement_delta: none`, do not edit spec; record exact accepted `spec_refs` proving sufficiency.
6. Update this slice status to `specified`. Present normative edits for the human specification gate after all slices are specified. `deltafuse decide --spec` records the click; do not write `accepted` on `spec-delta.md`.

Do not accept Decisions, invent behavior, or implement code. A newly discovered material question: stop; do not continue Specify.

## Gate

The specification change is accepted via `deltafuse decide --spec`, or unchanged status is proven by exact references. No normative behavior remains only in a request, Decision, design, or task. `spec-delta` added/modified files must belong to slice `spec_refs`. EARS phrasing does not replace live `docs/spec/**` (F-010).

Do not write deploy YAML or `docs/ops/**`; those belong to `route: ops` Implement.

Write requirements with RFC 2119 `MUST` / `SHALL` (or `ДОЛЖЕН`). Prefer EARS: WHEN [condition] THE SYSTEM SHALL [observable behavior]. EARS is style, not a new artifact and not a substitute for live `docs/spec/**`.
