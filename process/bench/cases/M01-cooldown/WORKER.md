# M01-cooldown bench workspace

This tree is a DeltaFuse **product**. You are the Worker. The Core is the `deltafuse` CLI.

## Do

1. `deltafuse next` (or `--human` / `--json`) — do not pick the next slash command yourself.
2. Load the pinned skill for that step. Write only the files the step allows.
3. Close with `deltafuse check-gate` when the Core says the gate is due (`coverage` after Analyze slices; `specified` after all Specify slices).
4. Use `deltafuse evidence` when the step needs Red/Green/regression.

## Do not

- Run `deltafuse bench score` or look for a scorecard. A judge host scores a copy of this tree.
- Auto-accept Decisions or merge.
- Search parent directories, the framework checkout, or the web for hidden tests or an answer key.
- Run `git push`.

Human Gates (DEC / spec accept) stay human. This case should not need a blocking Decision.

Intake source: `docs/intake/M01-cooldown.md`.
