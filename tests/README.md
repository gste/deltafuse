# Tests and Layout Validators

This directory contains the automated test suites and layout validators for the DeltaFuse framework.

## Structure

```
tests/
├── unit/
│   ├── test_schemas.py           # JSON Schema compliance for all 10 schemas
│   ├── test_frontmatter.py       # Markdown YAML frontmatter extraction
│   ├── test_graph.py             # Dependency DAG topological sort and cycle detection
│   ├── test_integrity.py         # Claim extraction and specification anchor lookup
│   ├── test_fsm.py               # FSM canonical states, allowed transitions, gate enforcement
│   ├── test_evidence.py          # Evidence runner classification and YAML write
│   ├── test_queue.py             # Derived work queue and deltafuse next
│   ├── test_board.py             # Read-only fuse-map board snapshot
│   ├── test_halt_contract.py     # Host halt contract (next --json choices)
│   ├── test_leash.py             # Write envelope and deltafuse leash
│   ├── test_llm_adapter.py       # Skills bind Worker (LLM); Core selects the step
│   └── test_fsm_mutations.py     # Semantic mutation tests (T1-T8)
├── integration/
│   ├── test_installer.py         # Product initialization and framework upgrade
│   ├── test_layout.py            # Product repository layout and adapter integrity
│   └── test_validator_cli.py     # CLI validator and gate checking commands
├── e2e/
│   ├── test_golden_workflow.py   # Full 7-step lifecycle flow, then archive
│   ├── test_noop_workflow.py     # Terminal no-op / not-reproduced bug lifecycle
│   └── test_failure_modes.py     # Negative lifecycle flows and orphan claims
├── fixtures/
│   └── change_builder.py         # Fluent builder for constructing Change packages
├── validate-layout.ps1 / .sh     # Python-free layout validators for the shell installers (`deltafuse init` checks its own)
└── smoke-test.ps1 / .sh          # Legacy shell smoke test scripts
```

## Running Tests

### Run Full Pytest Suite
In parallel (`pytest-xdist`, in the `dev` extras): the suite is about 850 tests, most of which
install a product and run the Core on it, so one process takes 7-8 minutes and `-n auto` about 2.
```bash
python -m pytest -n auto
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
The bench is the separate deltafuse-bench repository. `--pack .` works only when run from a deltafuse-bench checkout; elsewhere pass that checkout's path (or a case directory).
```bash
deltafuse-bench init M02-policy-stats ./m02
deltafuse-bench score ./m02 --pack . --json --label smoke --out-file ../scores/smoke.json
```

### Continuous Integration (CI)
All tests run automatically via GitHub Actions (`.github/workflows/test.yml`) across:
- Operating Systems: `ubuntu-latest`, `windows-latest`, `macos-latest`
- Python Versions: `3.10`, `3.11`, `3.12`, `3.13`, `3.14`
