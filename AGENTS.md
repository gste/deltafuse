# AGENTS.md

This repository is the canonical source of the DeltaFuse framework. It is not a product repository initialized with DeltaFuse.

## Mandate

Keep the framework internally consistent across:

- `docs/process/**` — lifecycle, roles, context slicing, and state machine;
- `skills/**` — executable agent contracts;
- `schemas/**` — artifact schemas;
- `templates/**` — product-owned files created by the installer;
- `validators/**` — product layout and compatibility checks;
- `migrations/**` — controlled upgrade guidance.

Product behavior belongs only in a consuming repository's `docs/spec/**`. Never add product-specific requirements to this framework.

## Framework/product boundary

- Canonical process files stay in this repository.
- The installer must not copy `docs/process/**` into a product repository.
- A product repository pins DeltaFuse in `.deltafuse/config.yaml` and `.deltafuse/lock.yaml`.
- Tool-specific local skills are generated snapshots. Mark them `DO NOT EDIT`, stamp framework version/source/hash, and validate them against the lock file.
- Product tasks live under `docs/changes/<change-id>/tasks/**`; do not recreate `docs/todo/**`.
- Bootstrap is a workflow profile represented by `project.baseline`; do not recreate `docs/init/**` or a repository-local process status file.

## Lifecycle vocabulary

Use these names consistently:

`Intake -> Route and Analyze -> Specify -> Decompose -> Target -> Implement -> Verify, Converge and Archive`

`Red` and `Green` are evidence states inside Target and Implement, not lifecycle step names.

## Change rules

- Treat [context-sliced-workflow-proposal.md](docs/process/context-sliced-workflow-proposal.md) as the accepted redesign rationale until it is replaced by a versioned specification.
- Update canonical docs, skills, schemas, templates, installers, validators, and migration notes together when a contract changes.
- Keep skills concise and self-contained enough to work as generated snapshots.
- Preserve user intent and do not invent product requirements.
- Never run `git push`, destructive git commands, or merge into the default branch.
- Do not commit secrets, credentials, or environment-specific absolute paths.

## Verification

For a framework change:

1. Run the smoke tests: 	ests/smoke-test.ps1 and 	ests/smoke-test.sh.
2. Validate layout on target repositories using 	ests/validate-layout.ps1 / 	ests/validate-layout.sh.
3. Validate the generated product layout.
4. Search for legacy runtime paths and commands outside migration/history documents.
5. Report any platform check that could not be run.
