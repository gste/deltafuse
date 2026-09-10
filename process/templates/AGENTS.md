# Agent Instructions

This product repository uses the DeltaFuse framework version pinned in `.deltafuse/lock.yaml`.

## Product sources

- Required behavior: `docs/spec/**`.
- Active Changes and tasks: `docs/changes/**`.
- Questions and rationale: `docs/decisions/**`.
- Raw input: `docs/intake/**`.
- Project configuration: `.deltafuse/config.yaml`.

Load the pinned/generated DeltaFuse skill for the requested lifecycle operation (`/intake`, `/analyze`, `/specify`, `/decompose`, `/declare`, `/implement`, `/verify`). Do not implement directly from chat, raw intake, a Decision, a diff, or an unaccepted specification change.

The Process (kernel CLI: `deltafuse next`, `evidence`, `check-gate`) selects the step and checks gates. The Thinker (LLM skill or human) writes Change artifacts. Do not pick the next lifecycle step from chat. Do not auto-accept Decisions or merge.

Do not edit generated skill snapshots under `.agents/skills/**`, `.cursor/skills/**`, or `.gemini/skills/**`. Regenerate them through the DeltaFuse installer/update command and validate them against `.deltafuse/lock.yaml`.

Repository-specific build, test, security, and style conventions may be added below. They must not redefine the DeltaFuse lifecycle or product behavior.

Never run `git push`, destructive git commands, or commit secrets as an autonomous agent.
