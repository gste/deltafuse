# Package 00 — Entry gates and decisions

Status: blocked at J03-000; no package implementation/result is asserted.
Commit boundary: `planning/readiness evidence (separate from implementation)`.

## Cards in default order

- [J03-000 — Capture qualified framework baseline](../../cards/J03-000.md)
- [J03-001 — Prove external Worker instrumentation feasibility](../../cards/J03-001.md)
- [J03-002 — Freeze public semantics and judge observability](../../cards/J03-002.md)
- [J03-003 — Define reproducible host and dependency provisioning](../../cards/J03-003.md)

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

- [J03-000 blocked result](cards/J03-000.md) — the Wave 3 qualification
  evidence and version are valid, but the implementation entry tree is not
  clean. See [package result](RESULT.md).
