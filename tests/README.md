# Tests and Layout Validators

This directory contains the automated test suites, layout validators, and LLM evaluation benchmarks for the DeltaFuse framework.

## Structure

```
tests/
├── unit/
│   ├── test_schemas.py           # JSON Schema compliance for all 9 schemas
│   ├── test_frontmatter.py       # Markdown YAML frontmatter extraction
│   ├── test_graph.py             # Dependency DAG topological sort and cycle detection
│   ├── test_integrity.py         # Claim extraction and specification anchor lookup
│   ├── test_fsm.py               # FSM canonical states, allowed transitions, gate enforcement
│   ├── test_evidence.py          # Evidence runner classification and YAML write
│   ├── test_queue.py             # Derived work queue and deltafuse next
│   ├── test_board.py             # Read-only fuse-map board snapshot
│   ├── test_llm_adapter.py       # Skills bind Thinker (LLM); Process selects the step
│   └── test_fsm_mutations.py     # Semantic mutation tests (T1-T8)
├── integration/
│   ├── test_installer.py         # Product initialization and framework upgrade
│   ├── test_layout.py            # Product repository layout and adapter integrity
│   └── test_validator_cli.py     # CLI validator and gate checking commands
├── e2e/
│   ├── test_golden_workflow.py   # Full 8-step lifecycle flow with archival
│   ├── test_noop_workflow.py     # Terminal no-op / not-reproduced bug lifecycle
│   └── test_failure_modes.py     # Negative lifecycle flows and orphan claims
├── evals/
│   ├── test_dataset.py           # Eval dataset schema validation and loader
│   ├── test_mock_provider.py     # Deterministic MockLLMProvider scenarios
│   ├── test_eval_runner.py       # Benchmark evaluation engine and metric aggregations
│   └── test_eval_cli.py          # deltafuse eval CLI command and reporting
├── fixtures/
│   └── change_builder.py         # Fluent builder for constructing Change packages
├── validate-layout.ps1 / .sh     # Legacy shell layout validators (canonical in python `deltafuse validate-layout`)
└── smoke-test.ps1 / .sh          # Legacy shell smoke test scripts
```

## Running Tests

### Run Full Pytest Suite
```bash
python -m pytest -v
```

### Validate Product Layout
```bash
deltafuse validate-layout .
```

### Lint Change Context Budget
```bash
deltafuse lint-context docs/changes/CHG-001
```

### Record evidence (kernel)
```bash
deltafuse evidence docs/changes/CHG-001 --phase red --task TASK-001 --changed-path tests/test_foo.py -- pytest tests/test_foo.py -q
```

### Next ready step
```bash
deltafuse next --list
deltafuse next --human
```

### Board snapshot (fuse-map)
```bash
deltafuse board . --json
```

### Run with Coverage
```bash
python -m pytest --cov=deltafuse --cov-report=term-missing
```

### Run LLM Benchmark Evals
```bash
deltafuse eval --scenario golden --threshold 90.0
```

### Continuous Integration (CI)
All tests run automatically via GitHub Actions (`.github/workflows/test.yml`) across:
- Operating Systems: `ubuntu-latest`, `windows-latest`, `macos-latest`
- Python Versions: `3.10`, `3.11`, `3.12`, `3.13`, `3.14`
