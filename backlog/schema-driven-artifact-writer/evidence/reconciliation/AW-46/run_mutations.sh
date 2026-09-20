#!/usr/bin/env bash
# AW-46 evidence driver: does any committed test protect JSON Pointer ~1/~0 unescaping?
#
# Phases:
#   Red   - pre-edit tests + each resolver mutation: the whole suite must stay green.
#   Green - post-edit tests + the same mutations: named assertions must fail.
#   Final - pristine control suite plus the repository checks this card requires.
#
# Safety: every mutation is written from a pristine backup stored outside the tree and
# is undone after each run, with the restored sha256 compared against the expected
# value in raw/restoration-transitions.log. An EXIT trap restores all three files.
set -u

EV="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$EV/../../../../.." && pwd)"
cd "$REPO" || exit 1

RAW="$EV/raw"
mkdir -p "$RAW"
BK="${TMPDIR:-/tmp}/aw46-backups"
mkdir -p "$BK"

F1="src/deltafuse/core/artifact_patch.py"
F2="scripts/evaluate_artifact_writer.py"
F3="tests/unit/test_artifact_writer_eval.py"
TRANS="$RAW/restoration-transitions.log"
: > "$TRANS"

sha() { sha256sum "$1" | cut -d' ' -f1; }

restore_all() {
  cp -f "$BK/writer.pristine" "$F1"
  cp -f "$BK/oracle.pristine" "$F2"
  cp -f "$BK/tests-post-edit.py" "$F3"
}

verify_restored() {
  local tag="$1" bad=0
  {
    echo "verify $tag $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    [ "$(sha "$F1")" = "$P1" ] || { echo "  MISMATCH $F1 $(sha "$F1") != $P1"; bad=1; }
    [ "$(sha "$F2")" = "$P2" ] || { echo "  MISMATCH $F2 $(sha "$F2") != $P2"; bad=1; }
    [ "$(sha "$F3")" = "$P3POST" ] || { echo "  MISMATCH $F3 $(sha "$F3") != $P3POST"; bad=1; }
    [ "$bad" = 0 ] && echo "  all three files byte-identical to their expected state"
  } >> "$TRANS"
  return $bad
}

trap 'restore_all; verify_restored trap-exit || true' EXIT INT TERM

cp -f "$F1" "$BK/writer.pristine"
cp -f "$F2" "$BK/oracle.pristine"
cp -f "$F3" "$BK/tests-post-edit.py"
git show "HEAD:$F3" > "$BK/tests-pre-edit.py"

P1="$(sha "$BK/writer.pristine")"
P2="$(sha "$BK/oracle.pristine")"
P3POST="$(sha "$BK/tests-post-edit.py")"
P3PRE="$(sha "$BK/tests-pre-edit.py")"

{
  echo "AW-46 pre-run identity $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "VERSION=$(cat VERSION)"
  echo "python=$(python -c 'import sys;print(sys.version.split()[0])')"
  echo "pytest=$(python -m pytest --version 2>&1 | head -1)"
  echo "writer_pristine_sha256=$P1"
  echo "oracle_pristine_sha256=$P2"
  echo "tests_post_edit_sha256=$P3POST"
  echo "tests_pre_edit_sha256=$P3PRE"
  echo "git_status_src_scripts_tests:"
  git status --porcelain -- src scripts tests | sed 's/^/  /'
  echo "manual restore command if this run is interrupted:"
  echo "  cp '$BK/writer.pristine' '$REPO/$F1'; cp '$BK/oracle.pristine' '$REPO/$F2'; cp '$BK/tests-post-edit.py' '$REPO/$F3'"
} > "$RAW/pre-run-identity.log"
echo "0" > "$RAW/pre-run-identity.exit"

# run <label> <variant> <tests-file> [pytest args...]
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

SUITE="tests/unit tests/integration tests/e2e"
FOCUSED="tests/unit/test_artifact_writer_eval.py tests/unit/test_artifact_patch.py"

echo "== Red: pre-edit tests, mutations applied =="
run "red-pre-tests-writer-unescape-deleted" writer-delete tests-pre-edit.py $SUITE
run "red-pre-tests-oracle-unescape-deleted" oracle-delete tests-pre-edit.py $SUITE

echo "== Green: post-edit tests, same mutations =="
run "green-post-tests-writer-unescape-deleted-full-suite" writer-delete tests-post-edit.py $SUITE
run "green-post-tests-writer-unescape-deleted-focused" writer-delete tests-post-edit.py -v -rA $FOCUSED
run "green-post-tests-oracle-unescape-deleted-focused" oracle-delete tests-post-edit.py -v -rA $FOCUSED
run "green-post-tests-writer-swapped-order-focused" writer-swapped tests-post-edit.py -v -rA $FOCUSED

echo "== Final: pristine control and repository checks =="
run "final-pristine-control-full-suite" none tests-post-edit.py -rA $SUITE

check() {
  local label="$1"; shift
  { echo "AW-46 check label=$label"; echo "argv=$*"; echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$RAW/$label.log"
  "$@" >> "$RAW/$label.log" 2>&1
  local rc=$?
  echo "--- rc=$rc" >> "$RAW/$label.log"
  echo "$rc" > "$RAW/$label.exit"
  echo "[$label] rc=$rc"
}

check backlog-checker python backlog/schema-driven-artifact-writer/check_backlog.py backlog/schema-driven-artifact-writer/queue.json
check backlog-checker-tests python -m pytest backlog/schema-driven-artifact-writer/tests/test_check_backlog.py -v -rA
check asset-sync-check python scripts/sync_assets.py --check
check git-diff-check git diff --check
check git-status-final git status --porcelain
check pointer-escaping-probe python backlog/schema-driven-artifact-writer/evidence/reconciliation/AW-42/probe_pointer_escaping.py
check aw39-card-text-unchanged git diff --exit-code -- backlog/schema-driven-artifact-writer/cards/AW-39.md backlog/schema-driven-artifact-writer/results/AW-39.md src scripts process docs
check untouched-file-hashes python -c "import hashlib,sys;[print(hashlib.sha256(open(p,'rb').read()).hexdigest(),p) for p in ['src/deltafuse/core/artifact_patch.py','scripts/evaluate_artifact_writer.py','tests/unit/test_artifact_patch.py','backlog/schema-driven-artifact-writer/cards/AW-39.md']]"

restore_all
verify_restored final
echo "AW46-DRIVER-DONE"
