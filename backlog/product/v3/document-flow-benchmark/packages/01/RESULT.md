# Package 01 — result

Status: in_progress
Package title: Scoring contracts
Cards: J03-101 complete; J03-102 through J03-108 planned

## Evidence index

- [J03-101 result](cards/J03-101.md)
- Frozen registry: `scripts/document_flow/contracts/checks.json`
- Registry loader: `scripts/document_flow/registry.py`
- Focused registry tests: `tests/bench/document_flow/test_registry.py`

## Handoff

J03-101 freezes the published check identities, weights, prerequisites,
evidence-source classes, and hard gates under registry identity `J03-checks-1`.
This is unit-level scoring-contract evidence only, not a benchmark run or live
qualification. The exact next dependency-ready card is J03-102.
