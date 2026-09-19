# Artifact Writer execution contract - remaining work

This file applies to implementation and qualification of this backlog. It does
not grant new product behavior, lifecycle authority, Git permissions or access
to external services. User instructions and canonical Process contracts prevail.

## Start one bounded task

1. Read repository AGENTS.md, REVIEW-4.md, README.md, PLAN.md, this file, the
   selected card, relevant CONTRACT.md/VALIDATION.md and actual predecessor evidence.
2. Select the first planned card whose dependencies have verified relevant
   completion evidence. Current entry: AW-37. Historical completed labels are
   claims to inspect, not permission to skip current acceptance checks.
3. Work on ONE card per implementation turn. Do not automatically execute all
   remaining cards. If too large, create dependency-ordered child cards retaining
   every original criterion; the parent stays open until every child qualifies.
   This is task decomposition, not authorization to spawn additional agents.
4. Record full HEAD, VERSION, dirty status and relevant tracked/untracked byte
   hashes before edits. Preserve concurrent work and all files outside the write
   set. Do not reset, stash, clean or rewrite user changes to obtain a clean tree.

Current sequence: AW-37 -> AW-39 -> AW-41 -> AW-40 -> AW-42 -> AW-20.
AW-38 remains completed for the proven missing-hash fix; retain its regressions.

## Freeze acceptance before coding

Create an acceptance matrix in the task result using RESULT-TEMPLATE.md. Include
EVERY original criterion plus the fourth-review acceptance IDs on the card/queue.
For each, state the observable invariant, public operation/probe and evidence
needed for PASS. Use PASS, FAIL or NOT RUN for checks. Initially unexecuted checks
are NOT RUN, not PASS. No count of passing tests can replace this mapping.

Scope expansion must be documented with its reason and preserved requirements.
Routine fixes within the authorized contract do not require another permission
request. Reducing a user requirement or mandatory live check requires explicit
user authorization; never infer a waiver from cost, time, unavailable tools,
context pressure, a prior completion label or a smaller implementation model.

## Required implementation loop

1. **Behavioral Red:** reproduce the stated counterexample through the real CLI
   or public service before production edits. Capture exact argv/input, assertions,
   output and actual exit. A TypeError for an unimplemented parameter, import
   error or missing fixture proves setup failure, not the behavioral invariant.
   For a qualification task, show the exact missing evidence/failing qualification
   boundary; do not manufacture an old runtime failure.
2. **Minimal implementation:** fix the invariant inside the allowed write set.
   Do not special-case test IDs, corpus values, review strings or fixture paths.
   Keep Core authority distinct from Writer serialization and Worker semantics.
3. **Green:** rerun the same Red test with the same expectation/input against
   changed production code. Changing the expected outcome to match the bug is not
   Green. Add nearby negative cases that a narrow special case would miss and
   positive cases showing legitimate behavior still works.
4. **Regression:** run affected tests and all repository-required checks at the
   appropriate scope. Record setup errors separately; resolve or leave them open.
   Run public cross-process/installed-wheel paths for contracts concerning those
   paths; helper-only tests cannot qualify unwired public behavior.
5. **Source binding:** record the actual tested bytes and test inputs after the
   run. Recheck source drift before updating completion. If relevant source or
   contract changes after tests, rerun affected checks and update the identity.
6. **Evidence and status:** fill every acceptance row and apply the completion
   rule below. A test summary alone is not a result report.

## Prohibited shortcuts

- Do not delete, skip, xfail, narrow or weaken a failing regression to report
  success. If a test must be replaced, document its original invariant and an
  equivalent or stronger executable replacement before retiring it. Inventory
  added/removed/replaced tests; explain coverage, not just count differences.
- Do not replace isolated Writer create/update/validate with generic wheel
  help/init/config checks. Preserve missing/tampered envelope negative tests.
  Never import the checkout into an isolation test to fix installation failure.
- Do not replace schema/identity/reference checks with file existence, arbitrary
  status strings, enum membership, substrings, error-string heuristics or caller
  success flags. Validate requested values for every supported kind and operation.
- Do not invent missing Change state, slice selection, semantic inputs, schema
  identity or lifecycle defaults. Denial must fail before unauthorized mutation.
- Do not fabricate hashes, timestamps, raw logs, provider/model identity, trials,
  retries or rates. Never hardcode comparison scores or label local fixed-input
  calls as model evidence. Compute metrics from preserved real raw runs.
- Do not treat removing a false qualification claim as completing the missing
  qualification. unavailable_no_endpoint and open_for_AW-20 mean OPEN.
- Do not replace actual POSIX evidence with Git Bash, Windows tests or mocks.
  Mandatory missing host/privilege checks and symlink skips remain open.
- Fault injection is useful for deterministic failure behavior, but is not a
  substitute for required real process crashes, filesystem races or model runs.
- Do not suppress nonzero exits, redirect away failure evidence, reuse stale
  logs as a current run or silently exclude failed/incomplete trials.
- Do not modify the oracle, thresholds or expected corpus semantics after seeing
  experiment results to obtain success. Preregister changes and rerun as a new
  explicitly identified experiment if a legitimate protocol defect is found.

## Evidence identity and storage

HEAD identifies a commit, not uncommitted implementation. For a dirty checkout,
record HEAD plus a source manifest of exact relevant tracked and untracked bytes,
the scoped diff identity, contracts, generated assets, tests and fixtures. Record
wheel SHA256 and import origin for wheel tests; real provider/model identity and
raw invocation refs for model trials; OS/runtime/filesystem for platform checks.

Preserve old reports/logs as historical. Do not rewrite an old hash to imply an
unobserved past run used the new source. Save a new verification record and mark
superseded claims explicitly. Raw evidence belongs in a preserved run location
with hash-indexed references; tracked reports contain portable refs, not secrets
or machine-specific absolute paths. Recompute hashes from actual bytes. A receipt
or digest demonstrates integrity only, not independent truth of its claims.

Do not hash a result file into itself. Hash supporting artifacts/source separately;
record report identity externally if needed. Keep structural/schema success,
semantic correctness, Core authority, whole-Change convergence and execution truth
as separate scopes, with not-evaluated scopes explicit.

## Completion rule - apply literally

A card may be completed ONLY if:

- every original and reopened mandatory acceptance row is PASS;
- each PASS has inspected raw evidence bound to the actual tested source;
- required negative controls fail weakened behavior and positive cases pass;
- no mandatory FAIL, NOT RUN, skip, missing platform/model run or unresolved setup
  error remains for that card;
- no relevant test invariant was lost and no source drift invalidates the runs;
- result, card and queue describe the same verified status.

If a prerequisite is unavailable, save partial progress and the exact missing
prerequisite, leave the card planned/in_progress with an explicit blocker, and
stop dependent execution. Do not label it completed-with-limitations. Continue
independent authorized work only when its own prerequisites are satisfied.
Do not create recurring tasks, send messages or purchase endpoint access implicitly.

AW-42 independently reconciles final source/evidence and lost-test coverage.
AW-20 performs the final original-criteria audit. Neither can waive missing live
model evidence, POSIX qualification or runtime defects. Both remain open until
actual acceptance is satisfied. An earlier model's completion report is untrusted.

## Result and handoff

Use RESULT-TEMPLATE.md for results/<ID>.md. Update only the owned result/card/queue
and authorized implementation surfaces. Synchronize canonical docs/skills/schemas/
templates/installer/validators/assets together when their contract changes.
Do not commit unless explicitly authorized; never push or merge the default branch.

End with: what changed; exact Red/Green and regression outcomes; acceptance rows
still open; source identity; next dependency-ready card or concrete missing
prerequisite; and a copy-paste continuation prompt. Do not promise acceptance
based on intended future runs. Stop after the selected bounded card.

## Copy-paste continuation prompt

Implement ONE dependency-ready Artifact Writer card in the canonical DeltaFuse
repository. Read AGENTS.md, backlog/schema-driven-artifact-writer/REVIEW-4.md,
README.md, EXECUTOR.md, RESULT-TEMPLATE.md, PLAN.md, the selected queue.json card
and relevant CONTRACT.md/VALIDATION.md sections. Current entry is AW-37.
Recheck actual dependencies and dirty source; preserve unrelated work. Freeze an
acceptance matrix for every original criterion and reopened acceptance ID. Capture
behavioral Red through the public entry point, implement the smallest contract-
correct fix, run Green and required regressions, and preserve raw evidence with
actual working-tree byte identities. Do not weaken/delete failing test invariants,
substitute generic wheel checks, fake model/platform runs, invent defaults or
close unavailable mandatory checks. Complete only when every required row is
source-bound PASS; otherwise save partial progress and leave the task open. End
with the next evidence-ready card or exact blocker and a precise continuation
prompt. Do not execute the entire remaining queue, commit or push implicitly.
