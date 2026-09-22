---
name: intake
description: Normalize a raw feature, bug, document, log, or review note into an immutable DeltaFuse Change request without consulting product specification or code. Use only for the first lifecycle step.
---

# Intake

Create the immutable Change request. Provenance is a heading in `request.md`, not a `provenance:` key in `change.yaml`.

Resolve artifact roots from `.deltafuse/config.yaml`; paths shown below are defaults.

## Worker (LLM)

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, and `check-gate`.

1. If the caller asked to continue existing work without an id, run `deltafuse next` and follow that step instead of creating another Change. Use this skill only to start a new Change.
2. Write only this step's artifacts (see Procedure). Do not write `src/**`.
3. Close with `deltafuse check-gate <change-dir> --gate intake`. Halt if it exits non-zero. Then run `deltafuse advance <change-dir> --gate intake` so the Core stamps the transition; halt if that exits non-zero.
4. Then run `deltafuse next`. Do not choose the next slash command yourself. If it names a ready step, load that skill and execute it in this same session. If it exits non-zero with halt.kind `decision` or `spec`, present `halt.choices` in the host multiple-choice UI, wait, run only `choice.command`, and continue. If `check-gate` failed or they chose inspect, stop.
5. Do not auto-accept Decisions or merge.

## Context

Read only:

- the user's current raw request and explicitly named files under configured `paths.intake`;
- `.deltafuse/config.yaml` and `.deltafuse/lock.yaml` for paths and pinned versions;
- the Change/request schemas or templates bundled with this skill installation.

Do not read `docs/spec/**`, Decisions, other Changes/tasks, tests, or product code.

## Procedure

1. Allocate a stable `CHG-NNN-<slug>` identifier without reusing archived IDs.
2. Scaffold the Change with the Core: `deltafuse new . <change-id> --title "<short title>"` (add `--route docs` or `--route ops` when the request is not code). It writes `change.yaml` and a `request.md` stub; do not write `change.yaml` yourself.
3. Write the prose of `request.md` below its frontmatter (keep the frontmatter as scaffolded): a concise summary, a Provenance section, and claim IDs `CR-001`, `CR-002`, … (three digits, not `CR-01`). `O1` / `E1` labels are allowed if that is how the claim was named.
4. Label each claim as observation, expectation, constraint, or hypothesis. Preserve unknowns explicitly. If a label was used as the ID (`O1`, `E1`), keep that ID; do not rewrite `request.md` after Intake.
5. Do not invent acceptance criteria, technical design, capability routing, or spec references.
6. If the source is a repository file, name its path in the request.md Provenance section and record it with `deltafuse artifact write --kind change --change <change-dir>` (`{"target": "change.yaml", "fields": {"source/intake_refs": ["docs/intake/<file>.md"]}}`). Move it to `docs/archive/intake/` only after the immutable request is complete.

Later clarification is appended as a revision or superseding claim. Never silently rewrite an earlier claim.

## Gate

Every material input statement is represented by a claim or explicitly excluded. Product artifacts remain unread and unchanged. Do not write `src/**`.
