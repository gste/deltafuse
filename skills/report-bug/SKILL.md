---
name: report-bug
description: Triages raw bug reports, review comments, error dumps, or log traces into a structured bug file under docs/todo/<story>/bug/. Clarifies ambiguities with the user, verifies against docs/spec/, and allocates NN without writing product code.
disable-model-invocation: true
---

# Report bug

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Auditor / Bug Triage).
2. Read `docs/process/prompts/07-report-bug.md` and follow it as the procedure for this job.
3. Verify the observation against `docs/spec/**`. Clarify any ambiguities with the human.
4. Output a structured bug task file to `docs/todo/<story>/bug/NN-<slug>.md` and register it in `docs/todo/README.md`.

Do not write or edit product code or tests in this job.