# Smaller-LLM execution protocol

This is an execution guide for implementing the benchmark later. It is not a
new DeltaFuse lifecycle, a product spec, or a request to implement now.

## Scope and context budget

One card = one primary invariant, one reviewable change, one evidence result.
Start a fresh implementation session per card when practical. The benchmark
Worker's 32768 context cap is mandatory; the following implementation-reading
limits are planning heuristics, not new scoring thresholds:

- Read this protocol, the chosen card, and prerequisite result summaries.
- Resolve wildcard read sets using rg --files and targeted rg queries.
  A wildcard is a search boundary, not an instruction to concatenate a tree.
- Initially open at most eight relevant files and approximately 12000 source
  tokens. Include only sections the card names. Preserve room for reasoning,
  tools, tests and output within the implementation model's real context.
- If one card cannot fit, split it into sequential child cards before code:
  retain parent invariant and acceptance, give children stable IDs/read/write
  sets, update queue dependencies, and require all children before parent done.
  Never discard required tests to fit a context window.
- Do not load sibling cards or entire qualification logs without a specific
  question. Read immutable evidence by a named check or artifact reference.

## Selection and prerequisites

Use queue.json order as the default deterministic topological execution order.
A card is ready only when every dependency has verified evidence, not just
status=done. Package 00 establishes the baseline and architectural decisions.
Treat all completion flags here as future mutable implementation state.
During planning all 58 cards remain planned.

At every session read AGENTS.md and check git status. Use per-command
safe.directory if necessary; never alter global Git configuration.
Do not stage/revert/commit concurrent qualification work. If HEAD or a needed
input changed, verify relevant contracts/hashes and update the handoff before
continuing. Do not silently carry forward a stale baseline pin.

## Work cycle

1. Restate the card invariant and locate only named inputs.
2. Verify predecessor results and record full starting SHA and dirty paths.
3. Add a meaningful failing acceptance test. Missing-module Red is acceptable
   only with concrete behavior assertions that later exercise the invariant.
   An import error alone is not proof of semantic test strength.
4. Capture Red argv, environment, output and exit under a fresh evidence path.
   Use an isolated snapshot if testing parent behavior; never reset user files.
5. Make the smallest change within write_set. Dependencies/import call sites
   outside it require a recorded scope adjustment or child card, not silent
   expansion. Shared schema/registry changes rerun their consumers' tests.
6. Run the named Green test and relevant neighboring regression tests. Live
   checks require the real service/boundary, not a mocked result.
7. Record outputs and evidence refs; review the focused diff and diff --check.
8. Update card/queue state and package RESULT. Report next ready card(s).

Card write sets implicitly allow its tests' small local fixtures, necessary
package __init__.py scaffolding, its own queue/card status, and its package
evidence index. They do not authorize product/framework contract changes.
Do not place secrets or machine-specific absolute paths in tracked results.

## Commit and result protocol

Keep the seven package commit boundaries in INSTRUCTION.md. A package may have
several small commits if a card requires a separate reviewable checkpoint.
No megacommit, no push, no destructive Git commands and no default-branch merge.
Stage only card-owned files and inspect staged diff before committing.

Each completed card has a result record under packages/<NN>/cards/<ID>.md.
Each package has RESULT.md listing card results and Red/Green/regression evidence.
Raw logs, stacks and actual runs stay in an external operator-selected evidence
root. Tracked indices reference hashes/relative evidence IDs, not credentials.

A commit cannot contain its own hash. Store completed source SHA in the next
evidence manifest/index commit, clearly distinguishing implementation SHA from
evidence-index SHA. Do not write "the current commit" as a substitute for a
full, resolvable final identity in the external evidence manifest.

## Stop and resume

Stop for an unmet explicit prerequisite, real Human Gate, exhausted permitted
scope, missing mandatory observability, or actual infrastructure failure.
Do not request approval for routine implementation choices already covered.
Record the smallest unresolved fact and exact next command/artifact needed.

On interruption persist:
card ID; parent/current SHA; modified files; failing/passing check IDs;
evidence location and hash; next action; unresolved contract assumptions.
Mark in_progress or blocked, never done because time/context ran out.
Do not repeat completed runs unless code, inputs or a known concern changed.

## Trust and honesty

- Public seed has single-step baseline behavior; only private reference
  patches implement the target Change during benchmark development.
- Benchmark implementation LLM and evaluated little-coder Worker are different
  roles. Judge assets are available to the former, inaccessible to the latter.
- Read_only tools, shell subprocesses and extensions all matter to isolation.
- A valid failed Worker run is data. Do not rescue it with human coding help.
- Gates stay human; no synthetic acceptance or automatic merge.
- All missing/invalid measurements follow SCORING-PLAN; never invent scores.
- Unit tests, simulated providers, mock containers and interpreter tests must
  be labelled as such. They cannot prove full-stack or pilot acceptance.
