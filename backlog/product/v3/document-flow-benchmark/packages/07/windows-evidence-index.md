# Windows Evidence Index — J03 Document Flow Benchmark

**Qualification Card**: `J03-702`  
**Host Operating System**: Windows (AMD64)  
**Interpreter**: Python 3.14 (pythoncore-3.14-64)  
**Source Commit**: `8018bdf`  
**Framework Version**: `3.0.0`  
**Date**: 2026-09-15  

---

## 1. Execution Summary

All primary Windows framework acceptance and benchmark evaluation tests were executed on the native Windows host environment.

| Component / Test Suite | Command | Exit Code | Result | Evidence / Notes |
|---|---|---:|---|---|
| PowerShell Smoke Test | `powershell -NoProfile -File tests/smoke-test.ps1` | 0 | PASS | Fresh product init, layout validation, idempotent -Force upgrade, layout re-validation |
| Asset Drift Check | `python scripts/sync_assets.py --check` | 0 | PASS | Clean asset synchronization, 45 assets verified up to date |
| Document Flow Benchmark Suite | `python -m pytest tests/bench/document_flow --override-ini=addopts= -q` | 0 | PASS | 306 passed, 6 skipped (expected symlink/live skips) |
| Unit Test Suite (portable) | `python -m pytest tests/bench/document_flow tests/unit -k "not test_result_integrity" -q` | 0 | PASS | 884 passed, 7 skipped |
| Legacy Reference Search | `git grep` against `docs`, `process`, `src`, `scripts` | 0 | PASS | All occurrences of `docs/init`, `docs/todo`, `docs/process`, `deltafuse eval` classified as migration guidance or layout enforcement |

---

## 2. Platform Nuances & Limitations

- **Symlinks**: Windows non-elevated user mode does not permit symlink/junction creation without developer mode or elevated privileges. `test_install.py` and `test_system_runner.py` gracefully skip symlink tests (`symlink creation unavailable on this platform`).
- **Live Compose Services**: Public and reference stack tests fall back cleanly to portable checks when the live compose cluster is not running during unit/contract testing.
- **Git Result Integrity**: Historical QF results test `test_result_integrity.py` requires historical parent commit trees from prior waves.
