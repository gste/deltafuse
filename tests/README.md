# Tests and Layout Validators

This directory contains the automated test suites and layout validators for the DeltaFuse framework.

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
│   ├── test_halt_contract.py     # Host halt contract (next --json choices)
│   ├── test_llm_adapter.py       # Skills bind Worker (LLM); Core selects the step
│   ├── test_bench.py             # Agent-agnostic Worker bench (init / score / compare)
│   └── test_fsm_mutations.py     # Semantic mutation tests (T1-T8)
├── integration/
│   ├── test_installer.py         # Product initialization and framework upgrade
│   ├── test_layout.py            # Product repository layout and adapter integrity
│   └── test_validator_cli.py     # CLI validator and gate checking commands
├── e2e/
│   ├── test_golden_workflow.py   # Full 8-step lifecycle flow with archival
│   ├── test_noop_workflow.py     # Terminal no-op / not-reproduced bug lifecycle
│   └── test_failure_modes.py     # Negative lifecycle flows and orphan claims
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

### Worker bench (no LLM)
```bash
deltafuse bench init M02-policy-stats ./m02
deltafuse bench score ./m02 --pack . --json --label smoke --out-file ../scores/smoke.json
```

### Continuous Integration (CI)
All tests run automatically via GitHub Actions (`.github/workflows/test.yml`) across:
- Operating Systems: `ubuntu-latest`, `windows-latest`, `macos-latest`
- Python Versions: `3.10`, `3.11`, `3.12`, `3.13`, `3.14`
