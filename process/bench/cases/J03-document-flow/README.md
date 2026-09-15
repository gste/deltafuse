# J03 Document Flow Benchmark Case

[**English**](README.md) | [Docs](../../../../docs/bench.md)

`J03-document-flow` is a distributed event-driven benchmark evaluating AI coding agents on end-to-end multi-service architectures under realistic asynchronous messaging and transactional outbox constraints.

## 1. Case Architecture

- **Domain**: Multi-stage document review and approval workflow across 3 services (`document-service`, `workflow-service`, `audit-service`) communicating via Kafka and isolated PostgreSQL databases.
- **Baseline Behavior**: Single-step approval workflow.
- **Target Specification**: Multi-stage routing (`EXPERT_LEGAL` + `EXPERT_FINANCE` parallel review followed by `REGISTRAR` final seal), transactional outbox publishing, idempotent inbox delivery, DLQ routing, immutable version supersede mechanics, and replayable audit projections.

## 2. Directory Layout & Separation

| Directory / File | Visibility | Description |
|---|---|---|
| `case.yaml` | Public | Benchmark case metadata, capabilities, stage budgets, and test commands |
| `WORKER.md` | Public | Worker instructions and available tooling constraints |
| `input.md` | Public | Raw intake requirements and Change specification description |
| `public-inventory.json` | Public | Canonical inventory manifest for sandboxed worker product initialization |
| `public_suite/` | Public | Single-step baseline smoke and regression test client |
| `seed/` | Public | Java reactor baseline source code and Flyway migrations |
| `oracle/` | Private Judge | Stage reference models, domain interpreters, and variant contract |
| `hidden_suite/` | Private Judge | Hidden functional scenarios, resilience fault injection, and resource checks |
| `mutations/` | Private Judge | Frozen 28-mutant matrix and calibration manifests |
| `reports/` | Private Judge | Calibration and qualification indexes |

## 3. Judge & Benchmark Commands

### Run Mutation Calibration
```bash
python -m scripts.document_flow calibrate --plan process/bench/cases/J03-document-flow/mutations/manifest.json --out <output-dir>
```

### Execute Benchmark Run
```bash
python -m scripts.document_flow run --run-id <run-id> --sandbox-dir <product-sandbox> --output-dir <evidence-out>
```

### Evaluate Multi-Run Campaign
```bash
python -m scripts.document_flow campaign --plan <campaign-plan.json> --runs <evidence-runs-dir> --out <summary-out.json>
```

### Replay and Re-evaluate from Disk Store
```bash
python -c "from pathlib import Path; from scripts.document_flow.store import EvidenceStore; from scripts.document_flow.replay import reevaluate_run_from_store; print(reevaluate_run_from_store(EvidenceStore.open(Path('<evidence-run-dir>'))))"
```

## 4. Scoring & Invariants

- **Score Range**: 1..10,000 exact rational points.
- **Stage Points (7 stages $\times$ 1000)**: 600 correctness + 250 discipline + 150 efficiency.
- **System Points (3000)**: 1800 functional + 600 resilience + 400 compatibility + 200 efficiency.
- **Hard Ceilings**:
  - Incomplete lifecycle: 4,999 max
  - Functional failure: 6,999 max
  - Integrity or boundary violation: 1,999 max
  - Unobserved / missing evidence: null score / invalid status
