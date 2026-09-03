---
name: fix-bug
description: Fixes an existing bug file from docs/todo/<story>/bug/ strictly against docs/spec/. Writes a failing regression test first, applies minimal code fix, cleans up the bug file, and updates CHANGELOG.
disable-model-invocation: true
---

# Fix bug

This skill carries no rules of its own. The repository files are the source of truth.

1. Read `docs/process/agent-prompt.md` and follow its core prompt (role: Implementer).
2. Read `docs/process/prompts/08-fix-bug.md` and follow it as the procedure for this job.
3. Read only the spec sections linked in the bug file's Spec delta.
4. Write failing regression test, implement fix, commit steps, delete inbox file, and update `CHANGELOG.md`.