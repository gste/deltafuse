# Baseline system tests

This directory holds the public deterministic fixtures of the baseline
system profile. The scenarios are executed end to end by the public suite
(`public_suite/baseline_suite.py` at the benchmark case root) against the
pinned compose stack started by `infra/stack.ps1`.

- `fixtures/approve.json` — create, immutable version, submit, single
  approver approves; the workflow closes `APPROVED`.
- `fixtures/reject.json` — the same flow with a rejection; the workflow
  closes `REJECTED` and re-submitting the decided immutable version is
  `VERSION_IMMUTABLE`.

The suite additionally proves the idempotent replay guard (same decision id
replays the prior outcome and adds no audit effect; the same id with a
different payload is `IDEMPOTENCY_CONFLICT`) and observes the baseline
events on the run-owned Kafka topics. All assertions carry stable public
identifiers (`J03-PUB-001` … `J03-PUB-012`); infrastructure failures are
classified separately and score nothing.
