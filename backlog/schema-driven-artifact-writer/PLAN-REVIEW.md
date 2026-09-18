# Plan review — 2026-09-18

Status: plan structure validated; implementation not started.

- 21 unique planned cards, 20 dependency edges, acyclic published order.
- Every card contains bounded read/write sets, ordered work, Red counterexample,
  Green acceptance, verification command/procedure and handoff expectations.
- 103 local links in generated planning documents resolve within this folder
  (including the separately copied intent and this review).
- Twelve source acceptance bullets mapped in VALIDATION.md.
- All ten source planning questions answered in ANALYSIS.md.
- All ten current artifact storage schema kinds classified by public/internal/
  deferred operation ownership in CONTRACT.md.
- Current findings supported by inspected source and an actual read-only
  characterization probe; raw results preserved under evidence/.
- Proposed paths/commands/tests explicitly labelled future implementation.
- No copied benchmark qualification prerequisites or product requirements.
- Original intent preserved separately; this plan's design choices do not
  overwrite the proposal.

## Key review findings resolved

1. Existing state/advance/decide remain authority; no enum-as-permission shortcut.
2. Verification evidence gets a real Core runner path, not a generic passed write.
3. Nested artifacts do not get an illegal universal schema_version field.
4. Existing open storage-schema extensions survive updates; typed inputs are
   narrow without secretly closing all storage schemas.
5. Metadata formatting versus exact body/value preservation is explicit.
6. CAS is coupled to a shared lock and honest external-writer limitations.
7. No-replace create and multi-file receipt recovery are separately tested.
8. Prepublication validation and post-write read-back both required.
9. Current scaffold mismatch is recorded; missing semantic content isn't guessed.
10. Real paired small-model evaluation keeps the same independent semantic
    oracle, classifies all failures and makes uncertainty/attrition visible.

## Limits

These checks establish a consistent actionable plan, not implementation
correctness. No framework smoke suite, atomic filesystem qualification or model
experiment was run by this planning task. The only executed code probe operated
on in-memory fixtures against current source. Future qualification remains in
AW-17–20.
