# Package 07 — Qualification and documentation

Status: planned; no package implementation/result is asserted.
Commit boundary: `bench: qualify and document document flow benchmark`.

## Cards in default order

- [J03-701 — Capture clean qualification build and public/judge inventories](../../cards/J03-701.md)
- [J03-702 — Qualify Windows baseline, framework and system harness](../../cards/J03-702.md)
- [J03-703 — Qualify POSIX baseline, framework and recovery](../../cards/J03-703.md)
- [J03-704 — Run fully attested external Worker pilot](../../cards/J03-704.md)
- [J03-705 — Execute three-run campaign and independent replay](../../cards/J03-705.md)
- [J03-706 — Close acceptance matrix and publish benchmark usage docs](../../cards/J03-706.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.
