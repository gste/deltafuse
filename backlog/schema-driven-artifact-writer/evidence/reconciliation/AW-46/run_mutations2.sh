#!/usr/bin/env bash
# AW-46 second mutation family: does anything protect "do not skip a failed lookup"?
# Same safety protocol as run_mutations.sh; appends to the shared transition log.
set -u

EV="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$EV/../../../../.." && pwd)"
cd "$REPO" || exit 1

RAW="$EV/raw"
BK="${TMPDIR:-/tmp}/aw46-backups"
mkdir -p "$BK"
TRANS="$RAW/restoration-transitions.log"

F1="src/deltafuse/core/artifact_patch.py"
F2="scripts/evaluate_artifact_writer.py"
F3="tests/unit/test_artifact_writer_eval.py"

sha() { sha256sum "$1" | cut -d' ' -f1; }

cp -f "$F1" "$BK/writer.pristine"
cp -f "$F2" "$BK/oracle.pristine"
cp -f "$F3" "$BK/tests-post-edit.py"
git show "HEAD:$F3" > "$BK/tests-pre-edit.py"

P1="$(sha "$BK/writer.pristine")"
P2="$(sha "$BK/oracle.pristine")"
P3POST="$(sha "$BK/tests-post-edit.py")"

restore_all() {
  cp -f "$BK/writer.pristine" "$F1"
  cp -f "$BK/oracle.pristine" "$F2"
  cp -f "$BK/tests-post-edit.py" "$F3"
}

verify_restored() {
  local tag="$1" bad=0
  {
    echo "verify $tag $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    [ "$(sha "$F1")" = "$P1" ] || { echo "  MISMATCH $F1"; bad=1; }
    [ "$(sha "$F2")" = "$P2" ] || { echo "  MISMATCH $F2"; bad=1; }
    [ "$(sha "$F3")" = "$P3POST" ] || { echo "  MISMATCH $F3"; bad=1; }
    [ "$bad" = 0 ] && echo "  all three files byte-identical to their expected state"
  } >> "$TRANS"
  return $bad
}

trap 'restore_all; verify_restored trap-exit-phase2 || true' EXIT INT TERM

run() {
  local label="$1" variant="$2" testsfile="$3"; shift 3
  local log="$RAW/$label.log" ex="$RAW/$label.exit" rc
  cp -f "$BK/$testsfile" "$F3"
  python "$EV/mutate.py" --backup-dir "$BK" --variant "$variant" > "$RAW/$label.mutation.txt" 2>&1 || {
    echo "MUTATION-SETUP-FAIL" >> "$RAW/$label.mutation.txt"; return 90; }
  {
    echo "AW-46 run label=$label variant=$variant"
    echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "cwd=$REPO"
    echo "argv=python -m pytest $*"
    echo "sha256 $F1=$(sha "$F1")"
    echo "sha256 $F2=$(sha "$F2")"
    echo "sha256 $F3=$(sha "$F3")"
  } > "$log"
  python -m pytest "$@" >> "$log" 2>&1
  rc=$?
  echo "--- pytest rc=$rc" >> "$log"
  echo "$rc" > "$ex"
  restore_all
  verify_restored "$label"
  echo "[$label] variant=$variant rc=$rc"
}

echo "== Phase 2: failed-lookup mutation =="
run "red2-pre-tests-silent-failed-lookup-full-suite" writer-silent-remove tests-pre-edit.py tests/unit tests/integration tests/e2e
run "green2-post-tests-silent-failed-lookup-focused" writer-silent-remove tests-post-edit.py -v -rA tests/unit/test_artifact_writer_eval.py tests/unit/test_artifact_patch.py
echo "AW46-DRIVER2-DONE"
