---
name: audit-spec
description: Audits specification consistency and ADR coverage. Mirrors accepted ADRs (accepted: true) into imperative spec chapters, flags hidden forks as ADR drafts, and updates the coverage matrix.
disable-model-invocation: true
---

# Audit spec

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Auditor).
2. Read `docs/process/prompts/02-audit-spec.md` and follow it as the procedure for this job.
3. Audit `docs/spec/**` and `docs/decisions/**` from the entry point `docs/spec/README.md`.
4. Mirror accepted ADRs into `docs/spec/` and update coverage matrices.

Do not write product code or create tasks in this job.