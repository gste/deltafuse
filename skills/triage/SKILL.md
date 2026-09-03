---
name: triage
description: Universal intake and triage engine. Takes raw input from chat or docs/inbox/ (PRDs, user stories, review comments, error traces), clarifies ambiguities with the user, evaluates against docs/spec/, compiles spec or ADR drafts or atomic tasks in docs/todo/, and archives processed files.
disable-model-invocation: true
---

# Triage

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Auditor / Intake Triage).
2. Read `docs/process/prompts/01-triage.md` and follow it as the procedure for this job.
3. Ingest raw input from chat or `docs/inbox/**`. Clarify any ambiguities with the human.
4. Evaluate against `docs/spec/**`. Compile spec pack (bootstrap), draft ADRs, or create atomic tasks under `docs/todo/<story>/NN-<slug>.md`.
5. Move processed files from `docs/inbox/` to `docs/archive/inbox/`.
6. Output the next recommended command: `/implement-task docs/todo/<story>/NN-<slug>.md`.

Do not write product code or tests in this job.