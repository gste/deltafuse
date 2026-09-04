#!/usr/bin/env bash
# DeltaFuse end-to-end smoke test for Bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t df-smoke)"

cleanup() {
  rm -rf -- "$TEMP_DIR"
}
trap cleanup EXIT

printf "[1/4] Running fresh installation into temporary directory...\n"
bash "$SCRIPT_DIR/scripts/init.sh" "$TEMP_DIR"

printf "[2/4] Validating installed product layout...\n"
bash "$SCRIPT_DIR/tests/validate-layout.sh" "$TEMP_DIR"

printf "[3/4] Testing idempotent upgrade with --force...\n"
bash "$SCRIPT_DIR/scripts/init.sh" --force "$TEMP_DIR"

printf "[4/4] Re-validating product layout after upgrade...\n"
bash "$SCRIPT_DIR/tests/validate-layout.sh" "$TEMP_DIR"

printf "Smoke test passed successfully!\n"
