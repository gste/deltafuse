#!/usr/bin/env bash
set -euo pipefail
# Portable: invoked from WSL with REPO_MNT and ARCHIVE_TAR set.
SRC="${WORK}/src"
mkdir -p "$SRC"
tar -xf "$ARCHIVE_TAR" -C "$SRC"
python3 - <<'PY'
from pathlib import Path
import os
p = Path(os.environ["WORK"]) / "src" / "tests" / "smoke-test.sh"
data = p.read_bytes()[:24]
print("shebang_bytes", data)
if b"\r" in data:
    raise SystemExit("archive smoke-test.sh still contains CR")
print("archive_lf_ok")
PY
bash "$SRC/tests/smoke-test.sh"
echo "SMOKE_SH_ARCHIVE_EXIT=0"
