# Package 02 — Working Java seed

Status: in_progress; J03-201 through J03-207 are complete and later package cards remain planned.
Commit boundary: `bench: add working Java document flow seed`.

## Cards in default order

- [J03-201 — Pin Java reactor and offline dependency inventory](../../cards/J03-201.md) — [result](cards/J03-201.md)
- [J03-202 — Publish baseline event/API contracts](../../cards/J03-202.md) — [result](cards/J03-202.md)
- [J03-203 — Create isolated service schemas and migrations](../../cards/J03-203.md) — [result](cards/J03-203.md)
- [J03-204 — Implement document baseline commands](../../cards/J03-204.md) — [result](cards/J03-204.md)
- [J03-205 — Implement single-step workflow baseline](../../cards/J03-205.md) — [result](cards/J03-205.md)
- [J03-206 — Implement reliable Kafka inbox/outbox delivery](../../cards/J03-206.md) — [result](cards/J03-206.md)
- [J03-207 — Implement audit projection and canonical query](../../cards/J03-207.md) — [result](cards/J03-207.md)
- [J03-208 — Wire pinned Compose stack and fault controls](../../cards/J03-208.md)
- [J03-209 — Prove public baseline end to end](../../cards/J03-209.md)
- [J03-210 — Add realistic noise and safe public pack installation](../../cards/J03-210.md)

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

- [Package result](RESULT.md)
- [J03-201 result](cards/J03-201.md)
- [J03-202 result](cards/J03-202.md)
- [J03-203 result](cards/J03-203.md)
- [J03-204 result](cards/J03-204.md)
- [J03-205 result](cards/J03-205.md)
- [J03-206 result](cards/J03-206.md)
- [J03-207 result](cards/J03-207.md)
- Audit projection/query: `process/bench/cases/J03-document-flow/seed/audit-service/src/`
- Canonical flow query: `process/bench/cases/J03-document-flow/seed/document-service/src/main/java/dev/deltafuse/bench/document/query/`
- Shared delivery implementation: `process/bench/cases/J03-document-flow/seed/shared-contracts/src/main/java/dev/deltafuse/bench/messaging/`
- Document/workflow messaging adapters and live tests: `process/bench/cases/J03-document-flow/seed/*-service/src/**/messaging/`, `Delivery*IntegrationTest.java`
- Java reactor: `process/bench/cases/J03-document-flow/seed/pom.xml`
- Dependency inventory: `process/bench/cases/J03-document-flow/dependencies.lock.json`
- Focused inventory tests: `tests/bench/document_flow/test_dependency_inventory.py`
- Baseline contracts: `process/bench/cases/J03-document-flow/seed/docs/spec/contracts/README.md`
- Public compatibility fixtures: `process/bench/cases/J03-document-flow/seed/docs/spec/contracts/fixtures/`
- Capability catalog: `process/bench/cases/J03-document-flow/seed/docs/spec/_capabilities.yaml`
- Contract test sources: `process/bench/cases/J03-document-flow/seed/shared-contracts/src/test/java/dev/deltafuse/bench/contracts/`
- Service migration tests: `process/bench/cases/J03-document-flow/seed/*-service/src/test/java/dev/deltafuse/bench/*/MigrationContractTest.java`
- PostgreSQL provisioning: `process/bench/cases/J03-document-flow/seed/infra/postgres/README.md`
- Document command/API implementation: `process/bench/cases/J03-document-flow/seed/document-service/src/main/java/dev/deltafuse/bench/document/`
- Document command receipts: `process/bench/cases/J03-document-flow/seed/document-service/src/main/resources/db/migration/V2__document_command_receipts.sql`
- Document command/API tests: `process/bench/cases/J03-document-flow/seed/document-service/src/test/java/dev/deltafuse/bench/document/DocumentCommandServiceTest.java`, `DocumentControllerTest.java`
- Workflow command/API implementation: `process/bench/cases/J03-document-flow/seed/workflow-service/src/main/java/dev/deltafuse/bench/workflow/`
- Workflow receipts: `process/bench/cases/J03-document-flow/seed/workflow-service/src/main/resources/db/migration/V2__workflow_receipts.sql`
- Workflow command/API tests: `process/bench/cases/J03-document-flow/seed/workflow-service/src/test/java/dev/deltafuse/bench/workflow/WorkflowCommandServiceTest.java`, `WorkflowControllerTest.java`
