# Package 01 — result

Status: in_progress
Package title: Scoring contracts
Cards: J03-101 through J03-103 complete; J03-104 through J03-108 planned

## Evidence index

- [J03-101 result](cards/J03-101.md)
- [J03-102 result](cards/J03-102.md)
- [J03-103 result](cards/J03-103.md)
- Frozen registry: `scripts/document_flow/contracts/checks.json`
- Registry loader: `scripts/document_flow/registry.py`
- Focused registry tests: `tests/bench/document_flow/test_registry.py`
- Event and EvidenceRef schemas: `scripts/document_flow/schemas/`
- Safe decoder: `scripts/document_flow/validation.py`
- Focused event-schema tests: `tests/bench/document_flow/test_events_schema.py`
- Stage/system report schemas: `scripts/document_flow/schemas/`
- Focused stage/system tests: `tests/bench/document_flow/test_stage_system_schema.py`

## Handoff

J03-101 freezes the published check identities, weights, prerequisites,
evidence-source classes, and hard gates under registry identity `J03-checks-1`.
J03-102 adds closed raw-event and EvidenceRef schemas plus duplicate-key,
nonfinite, local-reference-only decoding. This remains unit-level contract
evidence, not a benchmark run or live qualification. J03-103 adds closed stage
and system report envelopes, explicit task attempts/not-reached states, and
separate invalid-infrastructure versus product-failure outcomes. The first
exact dependency-ready card in queue order is J03-104.
