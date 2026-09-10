# CLAUDE.md

This is the canonical DeltaFuse framework repository. Read and follow `AGENTS.md`.

- Canonical workflow documentation is under `docs/**`.
- Executable lifecycle contracts are under `process/skills/**`.
- Artifact schemas are under `process/schemas/**`.
- Product scaffolding is under `process/templates/**`; it must not vendor canonical process files.
- Layout validators and smoke tests are under `tests/**`.
- Use the lifecycle `Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`.
- Core vs Worker: [docs/core-and-worker.md](docs/core-and-worker.md). Process is the lifecycle, not a runtime role.
- Never run `git push`.
