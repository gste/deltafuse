#!/usr/bin/env bash
# AW-42 native POSIX re-qualification on the final tree.
#
# AW-41's platform bundle hashes its raw logs but keeps them in an external
# "<preserved-run-location>" that the repository cannot resolve, so AW-42
# re-executes the mandatory POSIX subrows and retains the logs in-repo.
#
# Usage (from Windows):
#   wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/<repo>/backlog/schema-driven-artifact-writer/\
#       evidence/reconciliation/AW-42/posix_rerun.sh
set -uo pipefail

EVID="$(cd "$(dirname "$0")" && pwd)"
WIN_REPO="$(cd "$EVID/../../../../.." && pwd)"
WORK="$HOME/aw42-posix-run"
VENV="$WORK/venv"

echo "bundle=$EVID"
echo "repo=$WIN_REPO"
mkdir -p "$EVID/raw"
{
  echo "== host identity =="
  echo "user=$(id -un)"
  echo "kernel=$(uname -r)"
  echo "machine=$(uname -m)"
  echo "release=$(grep -oP '(?<=^PRETTY_NAME=").*(?=")' /etc/os-release)"
  echo "home_fs=$(df -PT "$HOME" | awk 'NR==2{print $2, $7}')"
  echo "workspace_fs=$(df -PT "$WORK" 2>/dev/null | awk 'NR==2{print $2, $7}')"
  echo "python=$(python3 --version 2>&1)"
} > "$WORK.host.log" 2>&1 || true

rm -rf "$WORK"
mkdir -p "$WORK"
# Copy only the tracked payload onto the native filesystem (ext4, not drvfs).
for d in src scripts tests docs process backlog pyproject.toml VERSION requirements-dev.txt; do
  [ -e "$WIN_REPO/$d" ] && cp -a "$WIN_REPO/$d" "$WORK/$d"
done
[ -e "$WIN_REPO/.gitignore" ] && cp -a "$WIN_REPO/.gitignore" "$WORK/.gitignore"
[ -e "$WIN_REPO/.gitattributes" ] && cp -a "$WIN_REPO/.gitattributes" "$WORK/.gitattributes"

echo "== venv + deps =="
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check \
  pytest pyyaml jsonschema attrs referencing 2>&1 | tail -5
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -e "$WORK" 2>&1 | tail -5
{
  echo "pytest=$("$VENV/bin/python" -m pytest --version 2>&1 | head -1)"
  echo "import_origin=$("$VENV/bin/python" -c 'import deltafuse,os;print(os.path.dirname(deltafuse.__file__))')"
  echo "pip_freeze:"; "$VENV/bin/pip" freeze
} > "$EVID/raw/posix-environment.log" 2>&1

cd "$WORK" || exit 1

echo "== POSIX concurrency / crash / security / CLI suite =="
"$VENV/bin/python" -m pytest \
  tests/integration/test_artifact_crash_recovery.py \
  tests/integration/test_artifact_locking.py \
  tests/integration/test_artifact_security.py \
  tests/integration/test_artifact_cli.py \
  -k "not isolated_wheel" -v > "$EVID/raw/posix-concurrency-crash-security.log" 2>&1
echo $? > "$EVID/raw/posix-concurrency-crash-security.exit"

echo "== POSIX focused Writer unit suites =="
"$VENV/bin/python" -m pytest \
  tests/unit/test_artifact_policy.py \
  tests/unit/test_artifact_writer_eval.py \
  tests/unit/test_artifact_patch.py \
  tests/unit/test_artifact_registry.py -v \
  > "$EVID/raw/posix-unit-suites.log" 2>&1
echo $? > "$EVID/raw/posix-unit-suites.exit"

echo "== POSIX bash smoke validator =="
bash tests/smoke-test.sh > "$EVID/raw/posix-smoke-sh.log" 2>&1
echo $? > "$EVID/raw/posix-smoke-sh.exit"

echo "== capable-host symlink / reparse probe =="
"$VENV/bin/python" - > "$EVID/raw/posix-symlink-capability.log" 2>&1 <<'PY'
import os, sys, tempfile
d = tempfile.mkdtemp()
link = os.path.join(d, "link")
try:
    os.symlink(os.path.join(d, "target"), link)
    print(f"symlink created: {link} -> {os.readlink(link)}")
    print("st_mode is link:", os.path.islink(link))
    print("SYMLINK_CAPABLE=yes")
except OSError as exc:
    print(f"symlink failed: {exc}")
    print("SYMLINK_CAPABLE=no")
finally:
    try:
        os.unlink(link)
    except OSError:
        pass
    os.rmdir(d)
PY

cp "$WORK.host.log" "$EVID/raw/posix-host-identity.log"
echo "== done =="
tail -1 "$EVID/raw/posix-concurrency-crash-security.log"
tail -1 "$EVID/raw/posix-unit-suites.log"
tail -1 "$EVID/raw/posix-smoke-sh.log"
