# Result template - copy for a task, never treat placeholders as evidence

## Task and status

- Card / acceptance revision:
- Status: planned / in_progress / completed (completion requires executor gate)
- Review and predecessor evidence inspected:
- Scope / explicit scope adjustments:

## Actual tested source identity

- Full HEAD and VERSION:
- Dirty tracked/untracked state before and after:
- Source/contract/test/fixture/asset manifest ref and SHA256:
- Scoped diff identity:
- Wheel hash and actual import origin, when applicable:
- OS, interpreter/dependency versions and filesystem:
- Actual provider/model identity and frozen protocol, when applicable:

HEAD alone is insufficient for a dirty checkout. Never invent a hash or runtime.

## Acceptance matrix

| Criterion ID | VERBATIM authoritative requirement / invariant | Probe or test | PASS / FAIL / NOT RUN | Raw evidence ref and hash | Remaining limitation |
|---|---|---|---|---|---|

Include original criteria and all reopened IDs. Every mandatory row must be PASS
before completion; inherited claims and intended future work are not PASS.

## Red, implementation, Green

- Exact counterexample, unchanged expectation and pre-edit source identity:
- Exact Red argv/input, exit, assertion and raw log hash:
- Minimal production change and why it enforces the invariant:
- Exact Green argv/input, exit, assertion and raw log hash:
- Nearby adversarial controls and legitimate-operation regression:

## Regression and coverage preservation

| Exact command / input ref | Actual exit | Result | Tested source identity | Raw log ref and hash |
|---|---|---|---|---|

List added/removed/replaced test invariants and executable replacements. Separate
platform/setup errors from behavioral failures. Do not hide mandatory skips.

## Independent truth and qualification scopes

- Syntax/schema validity:
- Requested semantic correctness and preservation:
- Core authorization and Gate/evidence safeguards:
- Whole-Change convergence (or explicitly not evaluated):
- Actual Windows/POSIX/wheel execution and missing mandatory checks:
- Actual paired-model raw runs/metrics/uncertainty (or explicitly unavailable):

## Closure decision and continuation

- Executor completion gate: PASS / NOT MET, with reasons:
- Evidence hash recheck and final source drift check:
- Current status in result/card/queue:
- Remaining mandatory prerequisites:
- Next ready task (or exact blocker):
- Copy-paste prompt for one bounded continuation:

Keep historical results distinguishable. Do not use this template as a reason to
claim unperformed work or fabricate raw evidence. No self-referential report hash.

## Literal requirement gap audit (required before status update)

- Card/queue criterion text preserved verbatim, including all required actions:
- Compound parent criteria have subrows and require all subrows PASS:
- Every PASS has inspected raw evidence for that exact action/environment:
- Model sessions, POSIX/capable-host checks and installed-schema damage tests
  are actual runs, not renamed or adjacent tests:
- Mandatory FAIL/NOT RUN count (must be zero for completion):
- No evaluator/open-prerequisite status contradicts card/queue/result closure:
- RECONCILIATION-CHECKLIST.md reviewed and remaining gaps listed:

If any mandatory evidence is absent, report partial implementation and the exact
external prerequisite. Do not mark completed merely because code tests pass.
