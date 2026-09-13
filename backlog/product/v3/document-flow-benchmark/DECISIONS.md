# Decisions to freeze before implementation consumes them

These are planning choices and open questions, not new accepted product
requirements. Source intent is INSTRUCTION.md. J03-002 records disposition:
accepted-from-intent, compatible-design-choice, or awaiting real Human Gate.
Do not ask the maintainer to approve every routine implementation detail.
Escalate only a materially ambiguous observable requirement.

## DEC-A — cross-service supersede transaction

Intent: old route closes SUPERSEDED and successor is created atomically; no
cross-service transaction. Proposed realization: workflow-service owns both
route rows and performs one local transaction. document-service publishes
immutable version submission through its outbox; canonical query exposes
pending synchronization until the workflow observation catches up.
Freeze the public acceptance/visibility point. If immediate distributed atomic
visibility is actually required, this is a blocking ambiguity; do not fake it
with shared DB transaction or synchronous mutation calls.

## DEC-B — actor identity and roles

Intent: distinct legal/security actors, one actor cannot fulfill two roles.
Use seed-owned stable actor assignments and explicit actor/document/version/
route/decision IDs in the public contract. Do not invent an OAuth/security
platform or accept an arbitrary client role as evidence of authorization.
Define exact rejection when actor and assigned role disagree; judge must not
expect hidden identity rules. Include actor assignments in generated variants.

## DEC-C — registrar rejection and unsupported actions

Intent explicitly describes expert rejection and registrar approval only.
Proposed minimal policy: registrar approve is supported; other registrar action
is invalid with a documented reason and no transition. This is a proposal,
not an extra hidden required feature. If seed/intake instead establishes a
registrar rejection contract, retain it and test that exact public behavior.
Public variant contract must settle this before a hidden case can score it.

## DEC-D — idempotency and conflicting identifiers

Exact repeated command/decision ID with identical canonical payload returns the
existing result and produces no duplicate observable effect. A reused ID with
different payload is an explicit conflict, not a second valid decision.
Freeze HTTP status/error schema, DLQ/audit semantics and conflict dedup key.
Do not call an infrastructure retry a domain rejection.

## DEC-E — ordering, stale decisions and invalid messages

Use event_id for delivery dedup and decision_id for domain decision identity;
do not conflate them. Bind all decisions to document_id+version_id+route_id.
Declare precedence for superseded-route late decisions versus malformed schema
or unauthorized actor: validate envelope/identity first, then apply public
late-event rules. Early registrar stays invalid and is not silently applied
when experts later finish. Freeze ordering constraints for valid generated
scenarios and separate deliberately invalid schedules.

## DEC-F — canonical endpoint

Stable canonical JSON has document/active version/workflow/open slots/audit
sequence plus an explicit consistency watermark. Define order via domain
sequence, deterministic tie handling and duplicate suppression. Read-only HTTP
aggregation is allowed as a query mechanism; Kafka remains the asynchronous
mutation/event channel. No wall-clock-only ordering assertion.
Define behavior when projections are not ready; judge polls the watermark and
then compares actual values rather than sleeping and assuming convergence.

## DEC-G — deterministic semantics versus natural language

Use finite public typed normative blocks in existing allowed artifacts, and
test their connection to actual claims/spec/task/assertions. Do not require a
new root witness file outside Core envelopes. This trades unrestricted prose
grading for reproducible grading of explicitly expressed semantics.
Syntax/keyword presence cannot prove arbitrary text semantically correct.
J03-002 must document both observable coverage and this limit; no LLM judge.

## DEC-H — measurement, budgets and infrastructure trust

Freeze factor/classification definitions from SCORING-PLAN before calibration.
Do not freeze a guessed resource number; measure reference calibration and
approve the versioned budget contract before Worker outcomes exist.
A missing mandatory observation means invalid qualification. Proven misconduct
with an intact host trace may be scored with a cap; missing trust root cannot.
Half-even rounding and per-file focus are proposed clarifications; the source
formulas and total weights are unchanged.
Closed-provider pilot may be non-release if weights/quantization cannot be
attested. Do not assert access to an endpoint from a locally installed package.

## Stage-witness placement review

Before J03-101, produce a table for each of seven stages:
public witness block location -> Core envelope read/write rule -> schema field
or allowed markdown block -> source obligation -> judge predicate.
If a needed block requires a Core contract extension, create a separate
reviewable framework change with synchronized docs/skills/schemas/templates/
validators and tests; do not smuggle that change into a product case.
Prefer representable existing artifacts to widening the framework for J03.
