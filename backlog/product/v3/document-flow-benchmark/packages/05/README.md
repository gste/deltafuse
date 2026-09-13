# Package 05 — External Worker adapter and boundary

Status: planned; no package implementation/result is asserted.
Commit boundary: `bench: add external little-coder worker adapter`.

## Cards in default order

- [J03-501 — Integrate external little-coder session transport](../../cards/J03-501.md)
- [J03-502 — Capture actual model and compaction measurements](../../cards/J03-502.md)
- [J03-503 — Enforce native tool envelopes and disabled capabilities](../../cards/J03-503.md)
- [J03-504 — Observe and confine arbitrary shell subprocesses](../../cards/J03-504.md)
- [J03-505 — Enforce isolated Worker network and filesystem policy](../../cards/J03-505.md)
- [J03-506 — Seal actual host/agent/model attestation](../../cards/J03-506.md)
- [J03-507 — Wire runner CLI and durable failure handling](../../cards/J03-507.md)
- [J03-508 — Verify adapter with real process and no scored Worker campaign](../../cards/J03-508.md)

Use [EXECUTOR.md](../../EXECUTOR.md) for bounded execution and evidence handling.
Write card results under `cards/<ID>.md` within this package directory.
After all cards satisfy their acceptance, write `RESULT.md` using
[the result template](../../RESULT-TEMPLATE.md); do not prefill it as passed.

Each package closes with evidence review, exact source identities and a focused
commit or small commit sequence. Raw logs/runs remain in the external judge
evidence store. A result-index commit may record a preceding implementation
commit hash; do not invent a self-referential SHA.

The next package cannot treat this README as completion evidence.
