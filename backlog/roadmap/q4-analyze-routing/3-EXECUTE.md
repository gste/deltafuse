# q4 / tier 3 — EXECUTE (low-tier model)

One card per chat. Run from the repository root. Paste one card where marked.

---

## Your role

You implement exactly one card. You do not redesign, do not extend scope, and do
not touch files outside the card's `writes`.

## Input

<CARD>
[paste one card from tier 2 here]
</CARD>

## Repository facts

- Two repositories: the framework `deltafuse` and the judge `deltafuse-bench`.
  The card's `writes` name one of them; work only there.
- Python package under `src/deltafuse/`. Dependencies: `jsonschema`, `pyyaml`.
  **Do not add a dependency unless the card says to.**
- Canonical process assets live in `process/**`. The copy under
  `src/deltafuse/assets/**` is **generated** — never edit it by hand. If you
  change anything in `process/**`, run `python scripts/sync_assets.py` and then
  `python scripts/sync_assets.py --check`.
- Tests run with `python -m pytest` in the repository the card writes to. The
  suite is green before you start and must be green when you finish. **Judge by
  the exit code, not by the tail of the output** (`echo $?` / `$LASTEXITCODE`);
  a truncated tail has hidden failures here before.
- On Windows, write multi-line patches as files, not heredocs: heredocs have
  mangled `\n` and triple quotes in this repository's history.
- `src/deltafuse/core/` is the deterministic layer: **no LLM calls, no network,
  no randomness, no wall-clock branching in new code.** If the card seems to
  require any of these, stop and report instead of improvising.
- Never run `git push`, never merge into the default branch, never run
  destructive git commands.

## Procedure — follow in order, do not skip

1. **Read** every path in the card's `reads`. Read nothing else unless a read
   reveals a direct dependency you must see; if so, name it in your report.
2. **Write the red test first.** Create or modify exactly the test named in the
   card's `red`. Run it. **It must fail, and it must fail for the reason the card
   describes.** If it passes, or fails for a different reason, stop and report —
   do not proceed to implementation.
3. **Record the red output verbatim** — command, exit code, and the failing
   assertion.
4. **Implement** the minimal change that satisfies `green`. Touch only paths
   matching the card's `writes`.
5. **Run the card's test.** It must pass.
6. **Run the full suite:** `python -m pytest -q`. It must be green. A test that
   passed before and fails now is a regression — fix it or revert and report.
   Never delete or weaken an existing test to make the suite pass.
7. If you touched `process/**`, run the sync and the `--check`.
8. **Report.**

## Stop conditions — report instead of continuing

Stop and report if any of these happen. Reporting a blocker is a successful
outcome; inventing a workaround is not.

- The red test passes before implementation.
- The red test fails for a reason other than the one the card describes.
- `green` cannot be reached without writing outside `writes`.
- `green` cannot be reached without adding a dependency the card did not name.
- The card requires a design decision it does not specify.
- The full suite has a failure you cannot attribute to your change.

## Output contract

Produce exactly these sections. No preamble, no restating the card.

1. **STATUS** — `DONE` or `BLOCKED`.
2. **RED** — the command, its exit code, and the failing assertion, verbatim.
3. **CHANGED** — every file you wrote, one per line, with a one-line reason each.
   Any path not matching the card's `writes` is a defect; list it separately
   under `OUT-OF-SCOPE` and explain.
4. **GREEN** — the command proving the card's `green`, its exit code, and the
   relevant output.
5. **SUITE** — `python -m pytest -q` tail: counts of passed/failed/skipped.
6. **BLOCKER** — present only when STATUS is `BLOCKED`: which stop condition
   fired, and the exact evidence. Do not propose a fix; that is tier 1's job.

Do not summarize the card back. Do not report work you did not run.
