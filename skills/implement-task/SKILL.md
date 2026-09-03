---
name: implement-task
description: Implements a single atomic task from docs/todo/<story>/task/ under TDD against docs/spec/. Use when an explicit task file is provided or requested. For bug files under docs/todo/<story>/bug/, use /fix-bug instead.
disable-model-invocation: true
---

# Implement task

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt.
2. Read `docs/process/prompts/06-implement-task.md` and follow it as the procedure for this job.
3. Read the task file in `docs/todo/<story>/task/` and only the spec modules it links to.

Follow TDD: failing tests first, smallest code change to pass, commit per step. Do not edit spec unless allowed by the task. Follow operator surface rule for root README.md. Close the slice (delete task file, append Closed in docs/todo/README.md, add one Unreleased bullet to CHANGELOG.md, remove empty story dir).
