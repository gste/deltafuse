---
name: run
description: Run the DeltaFuse Process through-mode. Follow `deltafuse next` in this same session until a Human Gate, a failed gate, or there is nothing ready. Use as the default Worker entry instead of pasting each slash command.
---

# Run

Stay on the Process without waiting for the human to paste `/analyze`, `/specify`, `/decompose`, `/declare`, `/implement`, or `/verify`.

This file binds the Worker to an LLM. It is not the Core. The Core owns `next`, `evidence`, `check-gate`, `decide`, and `archive`. Through-mode is not a lifecycle step and not a Human Gate.

## Worker (LLM)

1. Run `deltafuse next --json` at the product root.
2. If `selected` names a ready step other than intake, load that skill and execute it in this same session. Do not choose the next slash command yourself.
3. If `selected.skill` is `intake` and `intake_pending` is true, load `/intake` and execute it in this same session.
4. If `selected.skill` is `intake` and `intake_pending` is false: only run `/intake` when the human already stated a new Change in this chat. Otherwise stop. Do not invent a Change. Merge/push is a Human Gate. Do not git push.
5. After each step's `check-gate` passes, go back to step 1. Do not wait for a pasted slash command.
6. If `next` exits non-zero, read `halt`:
   - `decision` or `spec`: present `halt.choices` in the host multiple-choice UI. Wait. Do not pick. After the human answers, run the matching `deltafuse decide …` command (never invent accepted/rejected). Then go back to step 1.
   - `blocked`: stop. Show the reason. The human inspects and restarts through-mode.
   - `done`: stop. Merge/push is a Human Gate. Do not git push.
7. If `check-gate` or `evidence` fails: stop. Show the errors. Do not skip the step or auto-accept anything. The human inspects and restarts the named step or `/run`.
8. Do not auto-accept Decisions or merge. Do not call `deltafuse decide` unless the human answered a halt choice in this turn.

## Halt

Human action is required only for:

1. A Decision (`halt.kind: decision`) — buttons from `halt.choices`.
2. A specification Human Gate (`halt.kind: spec`) — buttons from `halt.choices`.
3. A failed gate, blocked task, or anything that needs inspection (`halt.kind: blocked`, or a non-zero `check-gate`).

`deltafuse decide` records the human's click. It is not auto-accept. `inspect` means stop.
