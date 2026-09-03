---
name: audit-spec
description: Validates the specification pack and audits ADRs. Verifies completeness, mirrors accepted ADRs into spec law, generates proposed ADRs for ambiguities, and checks readiness for implementation.
disable-model-invocation: true
---

# Audit spec & ADRs

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt.
2. Read `docs/process/prompts/03-audit-spec.md` and follow it as the procedure for this job.
3. Inspect `docs/init/**`, `docs/decisions/**`, and `docs/spec/**`.

Check ADR completeness, mirror accepted ADRs to spec imperatives, draft proposed ADRs for open forks, and report readiness to the human.
