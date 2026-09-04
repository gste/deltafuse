---
name: implement-task
description: Implements any atomic task from docs/todo/<story>/NN-<slug>.md strictly against docs/spec/. Follows TDD (writes failing test first, then minimal code to pass), commits steps, cleans up the task file, and updates CHANGELOG.
disable-model-invocation: true
---

# Implement task

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Implementer).
2. Read `docs/process/prompts/04-implement-task.md` and follow it as the procedure for this job.
3. Read the task file in `docs/todo/<story>/NN-<slug>.md` and linked spec sections.
4. If Spec delta is present, update spec anchors and commit spec first.
5. Write failing test (TDD Red), implement minimal code (TDD Green), commit changes.
6. Delete the task file, update `docs/todo/README.md`, and append an Unreleased item in `CHANGELOG.md`.