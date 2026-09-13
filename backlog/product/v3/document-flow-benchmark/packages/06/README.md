# Package 06 — Mutation calibration

Status: planned; no package implementation/result is asserted.
Commit boundary: `bench: calibrate document flow mutation matrix`.

## Cards in default order

- [J03-601 — Implement process-artifact mutants](../../cards/J03-601.md)
- [J03-602 — Implement Java functional mutants](../../cards/J03-602.md)
- [J03-603 — Implement Java delivery and atomicity mutants](../../cards/J03-603.md)
- [J03-604 — Implement score/provenance and boundary mutants](../../cards/J03-604.md)
- [J03-605 — Run complete calibration and freeze judge pack](../../cards/J03-605.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.
