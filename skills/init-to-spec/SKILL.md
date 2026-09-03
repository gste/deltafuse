---
name: init-to-spec
description: Assembles the modular Specification pack under docs/spec/ from raw requirements in docs/inbox/ and accepted ADRs. Moves processed files to docs/archive/inbox/.
disable-model-invocation: true
---

# Init to spec

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Spec editor).
2. Read `docs/process/prompts/02-init-to-spec.md` and follow it as the procedure for this job.
3. Inputs are `docs/inbox/**` plus ADRs with `accepted: true` only.
4. Output the modular specification pack under `docs/spec/` and draft ADRs under `docs/decisions/`.
5. Archive processed files to `docs/archive/inbox/`.

Do not create tasks under `docs/todo/` and do not write product code in this job.