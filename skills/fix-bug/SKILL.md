---
name: fix-bug
description: Diagnoses and fixes a bug. If the bug is a regression/deviation from docs/spec/, writes reproducing tests and fixes code. If spec was wrong or missing, updates docs/spec/ first as spec-patch, then fixes code. Use when a bug file under docs/todo/<story>/bug/ is provided or when asked to fix a bug.
disable-model-invocation: true
---

# Fix bug

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt.
2. Read `docs/process/prompts/07-fix-bug.md` and follow it as the procedure for this job.
3. If an inbox bug file was provided in `docs/todo/<story>/bug/`, read it. Otherwise classify the reported symptom against `docs/spec/`.

If spec must change, commit spec first as `spec-patch` with Spec delta, then write reproducing tests, then fix code. Close the slice (delete bug file, append Closed in docs/todo/README.md, add one Unreleased bullet to CHANGELOG.md, remove empty story dir).
