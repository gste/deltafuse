# Package 03 — Generated oracle and system judge

Status: in_progress; J03-301 through J03-305 are complete and later package cards remain planned.
Commit boundary: `bench: add generated document flow oracle`.

## Cards in default order

- [J03-301 — Generate replayable scenario variants](../../cards/J03-301.md) — [result](cards/J03-301.md)
- [J03-302 — Build independent pure domain interpreter](../../cards/J03-302.md) — [result](cards/J03-302.md)
- [J03-303 — Create private reference version-supersede implementation](../../cards/J03-303.md) — [result](cards/J03-303.md)
- [J03-304 — Complete private reference parallel approval implementation](../../cards/J03-304.md) — [result](cards/J03-304.md)
- [J03-305 — Build judge clients and stack execution harness](../../cards/J03-305.md) — [result](cards/J03-305.md)
- [J03-306 — Implement hidden functional scenarios](../../cards/J03-306.md)
- [J03-307 — Implement hidden transaction and resilience scenarios](../../cards/J03-307.md)
- [J03-308 — Implement hidden bounded load and resource checks](../../cards/J03-308.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.

## Evidence index

- [J03-301 result](cards/J03-301.md)
- Frozen variant contract: `process/bench/cases/J03-document-flow/oracle/variant-contract.json`
- Variant generator: `scripts/document_flow/variants.py`
- Generator tests: `tests/bench/document_flow/test_variants.py`
- [J03-302 result](cards/J03-302.md)
- Pure domain interpreter: `process/bench/cases/J03-document-flow/oracle/interpreter.py`
- Interpreter fixtures: `tests/bench/document_flow/test_interpreter.py`
- [J03-303 result](cards/J03-303.md)
- Private version-supersede reference: `process/bench/cases/J03-document-flow/oracle/reference/patches/version-supersede/overlay.json`
- Reference acceptance: `tests/bench/document_flow/test_reference_supersede.py`
- [J03-304 result](cards/J03-304.md)
- Private parallel-approval reference: `process/bench/cases/J03-document-flow/oracle/reference/patches/parallel-approval/overlay.json`
- Approval acceptance: `tests/bench/document_flow/test_reference_approval.py`
- [J03-305 result](cards/J03-305.md)
- Snapshot-bound system runner: `scripts/document_flow/system_runner.py`
- Restricted judge clients and fault controls: `scripts/document_flow/clients.py`, `scripts/document_flow/faults.py`
