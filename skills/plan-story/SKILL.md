---
name: plan-story
description: Slices an accepted specification module or spec git diff into atomic tasks under docs/todo/<story>/NN-<slug>.md with unified sequential NN numbering.
disable-model-invocation: true
---

# Plan story

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Planner).
2. Read `docs/process/prompts/03-plan-story.md` and follow it as the procedure for this job.
3. Slice `docs/spec/**` or `git diff -- docs/spec/` into atomic task files under `docs/todo/<story>/NN-<slug>.md`.
4. Register the story in `docs/todo/README.md`.

Do not write product code in this job.