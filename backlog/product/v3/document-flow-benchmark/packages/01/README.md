# Package 01 — Scoring contracts

Status: planned; no package implementation/result is asserted.
Commit boundary: `bench: define document flow scoring contracts`.

## Cards in default order

- [J03-101 — Create frozen check registry](../../cards/J03-101.md)
- [J03-102 — Define raw event schemas and safe decoding](../../cards/J03-102.md)
- [J03-103 — Define stage and system report schemas](../../cards/J03-103.md)
- [J03-104 — Define run and campaign schemas](../../cards/J03-104.md)
- [J03-105 — Define attestation and variant schemas](../../cards/J03-105.md)
- [J03-106 — Implement pure run scoring and failure precedence](../../cards/J03-106.md)
- [J03-107 — Implement campaign and comparison arithmetic](../../cards/J03-107.md)
- [J03-108 — Implement evidence store and sealed event integrity](../../cards/J03-108.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.
