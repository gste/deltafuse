# Package 03 — Generated oracle and system judge

Status: in_progress; J03-301 through J03-306 are complete; J03-307 is blocked pending live fault execution; J03-308 is complete ([result](cards/J03-308.md)).
Commit boundary: `bench: add generated document flow oracle`.

## Cards in default order

- [J03-301 — Generate replayable scenario variants](../../cards/J03-301.md) — [result](cards/J03-301.md)
- [J03-302 — Build independent pure domain interpreter](../../cards/J03-302.md) — [result](cards/J03-302.md)
- [J03-303 — Create private reference version-supersede implementation](../../cards/J03-303.md) — [result](cards/J03-303.md)
- [J03-304 — Complete private reference parallel approval implementation](../../cards/J03-304.md) — [result](cards/J03-304.md)
- [J03-305 — Build judge clients and stack execution harness](../../cards/J03-305.md) — [result](cards/J03-305.md)
- [J03-306 — Implement hidden functional scenarios](../../cards/J03-306.md) — [result](cards/J03-306.md); child evidence: [B1](cards/J03-306B1.md), [B2](cards/J03-306B2.md), [B closure](cards/J03-306B.md)
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
- [J03-306A result](cards/J03-306A.md)
- Frozen private functional scenarios: `process/bench/cases/J03-document-flow/hidden_suite/test_functional.py`, `test_consistency.py`
- [J03-306B1 result](cards/J03-306B1.md): live Kafka/DLQ boundary repaired; C02 passes on unchanged seed.
- [J03-306B2 result](cards/J03-306B2.md): reference audit propagation repaired; cumulative reference passes F01-F09/C02/C03 live.
- [J03-306B closure](cards/J03-306B.md): retained seed, negative-control and cumulative-reference facts close every original acceptance requirement.
- [J03-306 result](cards/J03-306.md): parent closed from the complete A/B child evidence.
- [J03-307 result](cards/J03-307.md): frozen R01-R04/C01 contract layer and fail-closed fact derivation added; live fault execution remains blocked by the current quota limit.

- [J03-308 result](cards/J03-308.md): hidden bounded load and resource checks (SYS.C04, SYS.E01-SYS.E04) and frozen budget contract.
