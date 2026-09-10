# Target — CHG-001-docs-s08b

## Status

NOT APPLICABLE — documentation-only change.

## Reasoning

The `target-task` skill freezes an executable behavioral target and proves it
fails for the expected reason before production code changes. This change is
documentation-only:

- No production code is modified (allowed_paths are docs only; forbidden_paths
  include src/, tests/, *.py).
- No runtime behavior changes (CR-007).
- The task oracles are grep-based text assertions, not executable behavioral
  targets.

Therefore there is no executable behavioral target that can fail Red. The gate
`targeting` is satisfied by confirming that no Red target is required for a
documentation-only change.
