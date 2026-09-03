---
name: plan-spec-patch
description: Slices specification diffs/patches into atomic task files under docs/todo/. Use when docs/spec/ was modified and atomic implementation tasks need to be generated automatically.
disable-model-invocation: true
---

# Plan spec patch

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt.
2. Read `docs/process/prompts/07-plan-spec-patch.md` and follow it as the procedure for this job.
3. Run `git diff HEAD~1 -- docs/spec/` to extract modified anchors.

Slice the diff into atomic task files under `docs/todo/<story>/task/`, register in `docs/todo/README.md`, and commit the plan.
