# Package 04 — Lifecycle observations and reports

Status: planned; no package implementation/result is asserted.
Commit boundary: `bench: report every DeltaFuse lifecycle stage`.

## Cards in default order

- [J03-401 — Adapt Core snapshots without changing the Process](../../cards/J03-401.md)
- [J03-402 — Capture immutable stage and task boundary snapshots](../../cards/J03-402.md)
- [J03-403 — Implement Intake and Analyze deterministic oracles](../../cards/J03-403.md)
- [J03-404 — Implement Specify and Decompose deterministic oracles](../../cards/J03-404.md)
- [J03-405 — Implement authentic Declare and frozen test oracle](../../cards/J03-405.md)
- [J03-406 — Implement Implement and Verify convergence oracles](../../cards/J03-406.md)
- [J03-407 — Compute measured context/file/tool/retry efficiency](../../cards/J03-407.md)
- [J03-408 — Re-evaluate runs from source artifacts](../../cards/J03-408.md)
- [J03-409 — Render reports and define read-only report commands](../../cards/J03-409.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.
