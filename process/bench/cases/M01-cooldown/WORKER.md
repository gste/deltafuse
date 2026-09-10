# M01-cooldown bench workspace

This tree is a DeltaFuse **product**. You are the Worker. The Core is the `deltafuse` CLI.

## Do

1. `deltafuse next` (or `--human` / `--json`) — do not pick the next slash command yourself.
2. Load the pinned skill for that step. Write only the files the step allows.
3. Close with `deltafuse check-gate` when the Core says the gate is due (`coverage` after Analyze slices; `specified` after all Specify slices).
4. After each lifecycle step, from this directory:

```text
deltafuse bench score . --json
```

Optional: `--stage specify` and `--label opus-5`.

## Do not

- Auto-accept Decisions or merge.
- Read `oracle.yaml` or `hidden_suite` from the framework repo. Those are scorer-only.
- Copy hidden tests into `tests/` to make Implement look green.
- Run `git push`.

Human Gates (DEC / spec accept) stay human. This case should not need a blocking Decision.

Intake source: `docs/intake/M01-cooldown.md`.
