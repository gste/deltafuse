# POSIX Evidence Index — J03 Document Flow Benchmark

**Qualification Card**: `J03-703`  
**Host Operating System**: Ubuntu 24.04 (Linux 6.6.87.2-microsoft-standard-WSL2 x86_64)  
**Interpreter**: Python 3.12.3  
**Source Commit**: `d6f79d5`  
**Framework Version**: `3.0.0`  
**Date**: 2026-09-15  

---

## 1. Execution Summary

POSIX qualification was conducted in a verified native Linux environment (Ubuntu 24.04 on WSL2 / Linux kernel 6.6.87.2), strictly distinguished from Windows Git Bash emulation.

| Component / Test Suite | Command | Exit Code | Result | Evidence / Notes |
|---|---|---:|---|---|
| POSIX Smoke Test | `bash tests/smoke-test.sh` | 0 | PASS | Fresh installation into `/tmp/tmp.*`, product layout validation, idempotent `--force` upgrade, layout re-validation |
| POSIX Asset Drift Check | `python3 scripts/sync_assets.py --check` | 0 | PASS | All 45 assets verified up to date on Linux filesystem |
| Deterministic Variant Reproduction | Python 3.12 variant generation check (`seed=42001`) | 0 | PASS | Operation count (33) and canonical SHA256 (`89a86d270af3d1420b79e62ede515443e7532794420bd81ceb07203ad56159fd`) are 100% byte-identical across Windows and Linux runtimes |

---

## 2. Platform Nuances & Distinction

- **Runtime Distinction**: POSIX smoke testing verified real Linux file paths (`/tmp`), symlink behavior, exit code propagation, and POSIX shell semantics under `/bin/bash` on Ubuntu 24.04.
- **Cross-Platform Determinism**: Scenario variant operations, random sequences, JSON canonicalization, and Merkle tree hashes generate identical byte outputs on POSIX and Windows.
