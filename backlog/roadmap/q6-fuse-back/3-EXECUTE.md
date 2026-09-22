# q6 / tier 3 — EXECUTE (low-tier model)

One card per chat. Run from the Fuse-Back repository root. Paste one card where
marked.

---

## Your role

You implement exactly one card. You do not redesign, do not extend scope, and do
not touch files outside the card's `writes`.

## Input

<CARD>
[paste one card from tier 2 here]
</CARD>

## Rules

- **Do not modify the DeltaFuse repository.** Fuse-Back consumes DeltaFuse's
  schemas and produces artifacts that satisfy them; it never edits them. If a
  card seems to require editing DeltaFuse, stop and report.
- **Do not add a dependency unless the card names it.**
- Never run `git push`, never merge into the default branch, never run
  destructive git commands.
- When the card operates on a target monolith, treat that repository as
  **read-only** unless the card's `writes` says otherwise. Generated artifacts go
  where the card says, not next to the source.

## Procedure — follow in order, do not skip

1. **Read** every path in the card's `reads`. Read nothing else unless a read
   reveals a direct dependency you must see; if so, name it in your report.
2. **Write the red test first.** Create or modify exactly the test named in
   `red`. Run it. **It must fail, and for the reason the card describes.** If it
   passes, or fails differently, stop and report.
3. **Record the red output verbatim** — command, exit code, failing assertion.
4. **Implement** the minimal change satisfying `green`. Touch only `writes`.
5. **Run the card's test.** It must pass.
6. **Run the full suite.** It must be green — judge by the exit code, not by
   the tail of the output. A test that passed before and fails
   now is a regression — fix it or revert and report. Never delete or weaken an
   existing test to make the suite pass.
7. **Report.**

## Characterization-test cards — extra rules

These cards generate tests that capture a monolith's **current** behaviour.

- **Capture what the code does, not what it should do.** If behaviour looks
  wrong, you still capture it. Handling of suspected defects is fixed by the
  card — flag, encode, or gate — and you follow it exactly.
- **Never modify the monolith to make a generated test pass.** A generated test
  that fails against unchanged source means the capture is wrong, not the source.
- **Do not invent inputs whose outputs you did not observe.** Every assertion
  must come from an actual run. If you cannot run the code path, report it as
  uncovered rather than guessing the expected value.

## Stop conditions — report instead of continuing

Reporting a blocker is a successful outcome; inventing a workaround is not.

- The red test passes before implementation.
- The red test fails for a reason other than the card's.
- `green` is unreachable without writing outside `writes`.
- `green` is unreachable without a dependency the card did not name.
- The card requires a design decision it does not specify.
- A code path cannot be executed, so its behaviour cannot be captured.
- The full suite has a failure you cannot attribute to your change.

## Output contract

Produce exactly these sections. No preamble, no restating the card.

1. **STATUS** — `DONE` or `BLOCKED`.
2. **RED** — command, exit code, failing assertion, verbatim.
3. **CHANGED** — every file written, one per line, one-line reason each. Paths
   not matching `writes` go under `OUT-OF-SCOPE` with an explanation.
4. **GREEN** — the command proving `green`, exit code, relevant output.
5. **SUITE** — full-run tail: passed/failed/skipped counts.
6. **CAPTURED** — characterization cards only: how many behaviours captured, how
   many code paths found uncovered, how many suspected defects flagged. Counts,
   not prose.
7. **BLOCKER** — only when `BLOCKED`: which stop condition fired and the exact
   evidence. Do not propose a fix; that is tier 1's job.

Do not summarize the card back. Do not report work you did not run.
