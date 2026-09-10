# Agent Instructions

This product repository uses the DeltaFuse framework version pinned in `.deltafuse/lock.yaml`.

## Product sources

- Required behavior: `docs/spec/**`.
- Active Changes and tasks: `docs/changes/**`.
- Questions and rationale: `docs/decisions/**`.
- Raw input: `docs/intake/**`.
- Project configuration: `.deltafuse/config.yaml`.

Load `/run` for through-mode: follow `deltafuse next` in the same session until a Human Gate, a failed gate, or nothing ready. Do not wait for the human to paste `/analyze` … `/verify`. Load a single lifecycle skill (`/intake`, `/analyze`, `/specify`, `/decompose`, `/declare`, `/implement`, `/verify`) only to run that one step.

The Core (`deltafuse next`, `evidence`, `check-gate`, `decide`) selects the step, checks gates, and records a Human Gate click. The Worker (LLM skill or human) writes Change artifacts. Do not pick the next lifecycle step from chat. Do not auto-accept Decisions or merge. When `next` returns `halt.kind` `decision` or `spec`, present `halt.choices` in the host multiple-choice UI and wait; then run the matching `deltafuse decide` command.

Do not edit adapter skills under `.agents/skills/**`, `.cursor/skills/**`, or `.gemini/skills/**` (copied snapshots or links into the pinned checkout). Recreate them with the DeltaFuse installer and validate them against `.deltafuse/lock.yaml`. After a submodule update, linked skills are already live; re-run the installer with `--force` only to refresh the lock.

Repository-specific build, test, security, and style conventions may be added below. They must not redefine the DeltaFuse lifecycle or product behavior.

Never run `git push`, destructive git commands, or commit secrets as an autonomous agent.
