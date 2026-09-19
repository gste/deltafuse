# AW-41 platform qualification evidence (2026-09-20 rerun)

Raw logs for the Windows and POSIX platform runs live in the preserved run
location referenced as `<preserved-run-location>/aw41-evidence-20260920`
(win/ and posix/ subdirectories) and are hash-indexed by `MANIFEST.json`
in this directory. Re-verify by hashing the named files and comparing digests.

## What ran

- **Windows (win32, NTFS, Python 3.14.3, pytest 9.1.1):**
  - concurrency/crash/security + public CLI subprocess suites: 26 passed,
    1 skipped (symlink, WinError 1314 - privilege not held), exit 0;
  - full framework suite `tests/unit tests/integration tests/e2e`: 523 passed,
    3 skipped (2 symlink privilege, 1 no local PBT runner), exit 0;
  - `tests/smoke-test.ps1`: fresh install, layout validation, idempotent
    upgrade, re-validation, exit 0;
  - `tests/smoke-test.sh` under Git Bash (Windows-hosted): exit 0 (this is
    script execution on Windows, not POSIX-filesystem evidence).
- **POSIX (Ubuntu 24.04.3 LTS, kernel 6.6.87.2-microsoft-standard-WSL2,
  x86_64, native ext4, Python 3.12.3 venv, pytest 9.1.1):**
  - repo copied to the native Linux filesystem (`~/aw41-run/repo`) - not drvfs;
  - concurrency/crash/security + public CLI subprocess suites: 27 passed,
    0 skipped (including the capable-host symlink cases), exit 0;
  - `tests/smoke-test.sh`: fresh install, layout validation, idempotent
    upgrade, re-validation on Linux, exit 0.

## Setup vs behavior

The first POSIX run had 8 failures; all 8 were `ModuleNotFoundError: No
module named 'deltafuse'` in spawned CLI subprocesses because only pytest
deps were installed in the fresh venv. `setup-failure-repro.log` retains an
authentic reproduction; after `pip install -e .`, the same suite passed
27/27. This is documented as a setup-availability finding (AW41-R2-style),
not a Writer defect.

## Remains open elsewhere

- AW-40: live paired small-model sessions (authorized endpoint required).
- AW-20: final closure audit.
- Windows symlink creation remains unprivileged on this host; the capable-host
  symlink/reparse requirement itself is satisfied by the Linux run.