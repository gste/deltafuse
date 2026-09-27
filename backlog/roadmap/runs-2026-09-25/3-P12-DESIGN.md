# P12: trace from a request claim to a test that asserts it (design, not implemented)

Status: proposal for the owner. Nothing here changes the framework yet.

## Why

A converged run can still miss a claim of the request: M02 on Gemma 31B reached `converged`
with Verify green at 53.5-56.1. The framework records `claim -> slice -> task` (coverage.yaml)
and `task -> Red/Green evidence`, but not `claim -> the assertion that proves it`. When a claim
is lost inside a test, nothing in the run says so, and the only way to find out is to read
the run by hand. That is also a hole in what the bench can measure.

## What the bench already does (bench 3.3.5, `claim_trace`, no framework change)

Heuristic, per claim: routed / sliced / tasked / tested / built, plus `unasserted`: names the
claim puts in backticks that the Red tests mention but no `assert` reaches. On the saved M02
runs: 0 unasserted claims at 100 and 98.4, two (CR-007, CR-008) at 56.1. Small sample.
Limits: it reads backticks, so a claim written in plain words is `unknown`; a mention in an
assert is not proof of the right assertion.

## Proposal (three layers, each useful alone)

1. **Convention (skills, no core change).** In `declare`, a test that proves a claim carries
   its id: the test name or a marker `# covers: CR-013`. In `verify`, the Worker lists claims
   with no such test. Cost: two skill paragraphs (about 60 words each; the compact variants
   are already 24% shorter, so budget exists).
2. **Record (core, advisory).** `deltafuse coverage` reads the markers from the tests named in
   the Red evidence (`tests.failed` names) and writes `claims.<CR>.tests: [...]` to
   `coverage.yaml`. A claim with none is reported by `check-gate --gate verified` as a
   *warning*, not an error. No new gate; existing fixtures keep passing.
3. **Enforce (core, later).** Promote the warning to an error only for claims of kind
   Expectation/Constraint once layer 2 has run on enough models to show a low false-positive
   rate (marker present but test unrelated is not detectable by the core; that stays the
   judge's job).

## Risks

- Models may add the marker without asserting the claim (marker gaming). The bench trace
  (`unasserted`) is the check that catches it; keep it independent of the marker.
- Extra words in skills cost input tokens on every call (about 17% of input is skill text).
- A per-claim requirement on M03 adversarial claims (which are hypotheses, not expectations)
  needs the claim kind, which `request.md` already carries.

## Decision needed

Layer 1 + 2 as an experiment behind `workflow.trace_claims: warn` (default off), measured on
Gemma 31B M02 x3 against the bench baseline, or leave to the bench-side heuristic only.
Recommendation: layers 1 + 2 behind the flag; the bench trace is the acceptance metric
(share of Expectation claims with an asserting test, before and after).
