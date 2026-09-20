# Artifact Writer execution contract - remaining work

This file applies to implementation and qualification of this backlog. It does
not grant new product behavior, lifecycle authority, Git permissions or access
to external services. User instructions and canonical Process contracts prevail.

## Start one bounded task

1. Read repository AGENTS.md, REVIEW-6.md, README.md, PLAN.md, this file, the
   selected card, relevant CONTRACT.md/VALIDATION.md and actual predecessor evidence.
2. Select the first unfinished card in queue.execution_order whose dependencies have verified relevant
   completion evidence. Current entry: AW-42. Historical completed labels are
   claims to inspect, not permission to skip current acceptance checks.
3. Work on ONE card per implementation turn. Do not automatically execute all
   remaining cards. If too large, create dependency-ordered child cards retaining
   every original criterion; the parent stays open until every child qualifies.
   This is task decomposition, not authorization to spawn additional agents.
4. Record full HEAD, VERSION, dirty status and relevant tracked/untracked byte
   hashes before edits. Preserve concurrent work and all files outside the write
   set. Do not reset, stash, clean or rewrite user changes to obtain a clean tree.

Current sequence: AW-42 -> AW-20.
AW-43, AW-44, AW-45 and AW-46 are completed with inspected evidence; do not skip
their records. AW-40 and AW-41 are completed for the runs they actually executed;
their AW-42 reconciliation rows remain open.
AW-39 remains completed for the verified routing-patch fix; retain its regressions.
AW-46 added the escaped-pointer and nested-lookup regressions AW39-R3 was missing and
changed no AW-39 row, no oracle byte and no runtime byte.
AW-38 remains completed for the proven missing-hash fix; retain its regressions.

## Sixth-review execution gates - no inferred completion

The current queue entry is AW-42 (2026-09-20, after AW-46). It is dependency-ready but
cannot close from its own write set: `AW42-R3` subrows b and e stay NOT RUN on evidence
owned by AW-41 and AW-44 (13 unretrievable raw logs behind
`<preserved-run-location>`; a non-re-derivable wheel digest), and `AW42-R4` requires
re-running AW-42's own probe and reconciler at the post-AW-46 tree.
Run the backlog checker regularly: `python check_backlog.py
backlog/schema-driven-artifact-writer/queue.json`. AW-37 is not reopened.
Retain its passing regressions. Do not route directly to AW-20 while AW-42's
acceptance rows remain open. Existing live qualification
remains mandatory in AW-41/AW-40.

Before ANY edit, write a short execution ledger in the selected result:
criterion ID and exact text; mandatory subrows; observed pre-edit state; intended
public probe; required host/model; expected observable failure; allowed files.
Do not populate PASS from the previous agent's prose. Read the referenced objects.

Apply these gates in order and stop the dependent work at the first unmet gate:

1. Readiness: compute unfinished cards and unmet dependencies from queue.json.
   Inspect predecessor evidence, not just completed strings. Report dependency
   readiness and environmental availability separately. An unavailable host does
   not authorize jumping to final acceptance. Independent ready work is allowed.
2. Red: preserve the actual pre-edit counterexample. Documentation reconciliation
   uses a contradictory-claims ledger; qualification uses a missing-evidence or
   setup reproduction. Neither may be presented as a runtime behavioral failure.
3. Execution: perform the exact required operation in the specified environment.
   For wheel tests, build/install a real wheel, strip checkout import paths and
   verify origin. Fix setup honestly or leave NOT RUN. A passing import/help test
   does not replace Writer operations or installed-schema damage probes.
4. Evidence: record argv, input refs, actual exit, stdout/stderr, source and wheel
   hashes, environment, and before/after effects. Store sanitized evidence through
   portable retrievable refs with an external hash index. Verify every ref/hash.
   Never expose credentials, fabricate old logs, use this_file as a digest, or
   substitute a fresh run for an old one without labeling the new source/run.
5. Status: NOT RUN means no qualifying execution, FAIL means a violated invariant,
   and PASS requires inspected qualifying evidence. Queue open maps to result
   FAIL/NOT RUN; queue passed maps only to complete PASS. Compound parents stay
   open if ANY mandatory subrow is FAIL/NOT RUN. No PASS (audit) shortcut for a
   parent that also requires actual execution. Correct reporting can finish a
   reporting card, never its platform/model/acceptance parent.
6. Handoff: recompute readiness after the proposed status update. Synchronize
   current navigation; distinguish historical handoffs explicitly. Run AW-45's
   checker once it exists, plus independent evidence inspection. A structural
   checker does not certify raw evidence truth or justify a completion claim.

A result must include a final refusal-to-close ledger: each missing prerequisite,
its owning card/check, observed reason, required next action and dependent cards
that remain blocked. If empty, demonstrate why every mandatory row is PASS.
Do not add implementation work outside the card to chase a green report; record
new defects as bounded work retaining the original acceptance requirements.

## Freeze acceptance before coding

Create an acceptance matrix in the task result using RESULT-TEMPLATE.md. Include
EVERY original criterion plus the all review acceptance IDs on the card/queue.
For each, state the observable invariant, public operation/probe and evidence
needed for PASS. Use PASS, FAIL or NOT RUN for checks. Initially unexecuted checks
are NOT RUN, not PASS. No count of passing tests can replace this mapping.

Scope expansion must be documented with its reason and preserved requirements.
Routine fixes within the authorized contract do not require another permission
request. Reducing a user requirement or mandatory live check requires explicit
user authorization; never infer a waiver from cost, time, unavailable tools,
context pressure, a prior completion label or a smaller implementation model.

## Mandatory literal-criterion and evidence gate (fifth review)

Before implementation, copy each original criterion and each reopened acceptance
ID VERBATIM into the result matrix. Do not shorten a requirement in its result
row. In particular, keep words such as actual, both arms, Windows and POSIX,
installed package, missing/tampered schema, and before publication. A shorter
label may be added separately, but cannot replace the authoritative requirement.

Split compound criteria into subrows, preserving the original parent row. The
parent is PASS only when every required subrow passes. Example: honest endpoint
status may PASS while actual paired sessions remain NOT RUN; their task is OPEN.
Windows execution may PASS while POSIX or required symlink coverage is NOT RUN;
the platform task is OPEN. Disclosure is evidence of honesty, not execution.

For each PASS, answer all five questions with concrete evidence:

1. What exact required action ran, against which public operation and input?
2. Which actual source/wheel/model/OS/filesystem was used?
3. What raw output, exit, artifact bytes or independent oracle proves the result?
4. Does that evidence prove the original requirement, or only a weaker neighbor?
5. What adversarial control would fail if the required behavior were absent?

If any answer is missing, the row is FAIL or NOT RUN, not PASS. A future command,
a renamed adapter/test, a broad test count or a test asserting a status string
cannot answer these questions. Never replace unexecuted qualification with a
unit test asserting that its absence is honestly reported.

Specific required negative tests are NOT interchangeable:

| Required invariant | Necessary probe | Insufficient substitute |
|---|---|---|
| Required Change ID | Missing/null/empty/wrong-type ID in otherwise usable live context must deny | Only a different nonempty ID |
| Packaged schema missing | Remove installed schema file, invoke isolated Writer mutation | Missing JSON request identity |
| Packaged schema tampered | Change installed schema bytes without updating verified manifest | Wrong target expected_sha256 |
| Actual POSIX qualification | Run on POSIX host/filesystem and preserve raw logs | Windows/Git Bash or disclosed skip |
| Genuine paired model benefit | Actual model calls in both preregistered arms and replayable raw traces | Oracle use, fixed corpus, adapter label or unavailable status |

Before changing a status to completed, reread the card and the original source
criteria, compare them word-for-word to the result requirements, and inspect raw
evidence rather than trusting another completion table. Run the gap audit in
RECONCILIATION-CHECKLIST.md. Keep the task open if any mandatory gap remains.
There is no completed-with-limitations shortcut under this backlog's contract.

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
repository. Read AGENTS.md, backlog/schema-driven-artifact-writer/REVIEW-6.md,
README.md, EXECUTOR.md, RESULT-TEMPLATE.md, PLAN.md, the selected queue.json card
and relevant CONTRACT.md/VALIDATION.md sections. Current entry is AW-42
(reconciliation of final source/evidence; AW-43/AW-44/AW-45/AW-46/AW-41/AW-40 are
completed — AW-40's live paired run was executed 2026-09-20 under the
delivery-verified AMEND-3 transport with 28 raw traces and replayable metrics in
evaluation/live-run-2026-09-20/, and AW-46 supplied the AW39-R3 escaped-pointer
regression on 2026-09-20). Run `python
backlog/schema-driven-artifact-writer/check_backlog.py
backlog/schema-driven-artifact-writer/queue.json` to confirm readiness, and
stop — do not claim execution or route to AW-20 before AW-42 reconciles raw
evidence against verbatim criteria.
Recheck actual dependencies and dirty source; preserve unrelated work. Freeze an
acceptance matrix with VERBATIM original criteria and reopened acceptance IDs;
split compound criteria into mandatory evidence subrows without weakening them. Capture
behavioral Red through the public entry point, implement the smallest contract-
correct fix, run Green and required regressions, and preserve raw evidence with
actual working-tree byte identities. Do not weaken/delete failing test invariants,
substitute generic wheel checks, fake model/platform runs, invent defaults or
close unavailable mandatory checks. Complete only when every required row is
source-bound PASS; otherwise save partial progress and leave the task open. End
with the next evidence-ready card or exact blocker and a precise continuation
prompt. Do not execute the entire remaining queue, commit or push implicitly.
