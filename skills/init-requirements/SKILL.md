---
name: init-requirements
description: Captures product intent and raw requirements into docs/inbox/ before a specification exists. Use at repository bootstrap or when drafting new capabilities from raw ideas.
disable-model-invocation: true
---

# Init requirements

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Init author).
2. Read `docs/process/prompts/01-init-requirements.md` and follow it as the procedure for this job.
3. Capture the user's intent into `docs/inbox/**`.
4. Highlight open questions and forks for potential ADRs.

Output goes to files under `docs/inbox/`, never to chat only. Do not write the spec pack, tasks, or product code in this job.