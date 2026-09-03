---
name: spec-to-story
description: Slices an accepted specification into a story and atomic task files under docs/todo/. Use when the spec pack is accepted and work needs to be planned, or when a requested change has no task file yet and someone is about to start coding without one.
disable-model-invocation: true
---

# Spec to story

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt.
2. Read `docs/process/prompts/04-spec-to-story.md` and follow it as the procedure for this job.
3. Read only the spec modules that fall inside the requested story scope.

Write slices to `docs/todo/<story>/task/` or `docs/todo/<story>/bug/`. Allocate `NN` from `docs/todo/README.md` (Closed ∪ live files). Tasks link to spec anchors and carry a DoD; they never copy requirement text. Do not write product code, do not edit `docs/spec/**`, and do not edit `CHANGELOG.md` in this job. Commit the slice.
