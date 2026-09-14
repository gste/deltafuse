# Package 02 — result

Status: in_progress
Package title: Working Java seed
Cards: J03-201 through J03-207 complete; J03-208 through J03-210 planned

## Evidence index

- [J03-201 result](cards/J03-201.md)
- [J03-202 result](cards/J03-202.md)
- [J03-203 result](cards/J03-203.md)
- [J03-204 result](cards/J03-204.md)
- [J03-205 result](cards/J03-205.md)
- [J03-206 result](cards/J03-206.md)
- [J03-207 result](cards/J03-207.md)
- Java 21 reactor: `process/bench/cases/J03-document-flow/seed/pom.xml`
- Four module POMs: `process/bench/cases/J03-document-flow/seed/*/pom.xml`
- Reproducibility configuration: `process/bench/cases/J03-document-flow/seed/.mvn/`
- Complete resolved artifact inventory: `process/bench/cases/J03-document-flow/dependencies.lock.json`
- Focused inventory tests: `tests/bench/document_flow/test_dependency_inventory.py`
- Baseline contracts: `process/bench/cases/J03-document-flow/seed/docs/spec/contracts/`
- Isolated schemas: `process/bench/cases/J03-document-flow/seed/*-service/src/main/resources/db/migration/`
- Document commands/API: `process/bench/cases/J03-document-flow/seed/document-service/src/`
- Baseline workflow commands/API: `process/bench/cases/J03-document-flow/seed/workflow-service/src/`

## Handoff

J03-201 establishes the Java 21 reactor and measured offline closure; J03-202
freezes the baseline contracts; J03-203 installs isolated schemas; J03-204 adds
atomic document commands; J03-205 adds the one-approver baseline workflow;
J03-206 adds bounded Kafka inbox/outbox delivery and measured restart barriers;
J03-207 adds replay-safe audit projection and deterministic read-only flow output.
Package 02 remains incomplete. The first exact dependency-ready card is J03-208.
