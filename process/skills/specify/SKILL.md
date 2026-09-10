---
name: specify
description: Apply one analyzed DeltaFuse slice to the normative product specification, or prove the accepted specification is unchanged. Use after analysis and Decision convergence, before task decomposition.
---

# Specify

Establish the normative state from which tasks may be derived.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Context

Read one analyzed slice, its typed delta, exact affected spec modules, accepted related Decisions/catalog delta, and only necessary neighboring requirements. Do not read the whole codebase or unrelated Changes.

## Procedure

1. If `requirement_delta` changes requirements, write a bounded `spec-delta.md` using `ADDED`, `MODIFIED`, and `REMOVED` with stable requirement/scenario IDs.
2. Edit only declared specification files and requirements. Keep the live spec imperative and free of change-log prose.
3. Apply an accepted capability catalog delta when required.
4. Mirror every accepted Decision that affects observable behavior, a contract, policy, or required invariant into `docs/spec/**`.
5. If `requirement_delta: none`, do not edit spec; record exact accepted `spec_refs` proving sufficiency.
6. Update coverage and slice/Change status. Present normative edits for the human specification gate.

Do not accept Decisions, invent behavior, or implement code. A newly discovered material question returns the Change to `/analyze`.

## Gate

The specification change is accepted, or unchanged status is proven by exact references. No normative behavior remains only in a request, Decision, design, or task.

Recommend `/decompose <change-id> [slice-id]`.

Do not write deploy YAML or `docs/ops/**`; those belong to `route: ops` Implement.

Write requirements with RFC 2119 `MUST` / `SHALL` (or `ДОЛЖЕН`). Prefer EARS: WHEN [condition] THE SYSTEM SHALL [observable behavior]. EARS is style, not a new artifact and not a substitute for live `docs/spec/**`.
