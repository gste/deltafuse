"""Run a product command and write Change evidence YAML (kernel, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from typing import Any

import yaml

from deltafuse.core.config import load_evidence_timeout
from deltafuse.core.context import load_change_route, posix_relpath
from deltafuse.core.fsm import (
    CONTRACT_GATES,
    RED_TAKEN_STATUSES,
    _TASKS_CLOSED,
    _frontmatters,
    _load_record,
    _validate_evidence_changed_paths_contract,
    find_repo_root,
    green_record_errors,
)
from deltafuse.core.hasher import compute_product_baseline_revision, compute_red_oracle_digest
from deltafuse.core.oracle import freeze_red_oracle, isolation_plan
from deltafuse.core.integrity import scan_changed_paths_for_private_test_access
from deltafuse.core.red_cause import environment_error, own_code_error
from deltafuse.core.runners import report_less_runner_error, runner_is_authorized
from deltafuse.core.test_reports import (
    FAILED,
    NOT_RUN,
    PASSED,
    SKIPPED,
    green_covers_red,
    no_test_error,
    read_report,
    red_is_authentic,
    restricted,
    suite_errors,
    runner_family,
    task_test_files,
    task_test_ids,
    wants_junit_flag,
    worker_junit_path,
)
from deltafuse.core.leash import git_dirty_paths, is_exempt_path, LeashError

AUTHENTIC_RED_CATEGORY = "behavioral-mismatch"
OWN_CODE_RED_CATEGORY = "test-own-error"
# The run failed, but not on the task's own tests (audit 2026-11-16, df-evidence #1).
NOT_THE_TASKS_RED_CATEGORY = "not-the-tasks-tests"
# Nothing named the task's tests: no declared test file, no file or class on the command line.
UNNAMED_RED_CATEGORY = "tests-not-named"
# The task's tests fail on their environment (audit 2026-11-16, df-evidence #7).
ENVIRONMENT_RED_CATEGORY = "environment-error"
RECORDED_BY = "deltafuse-evidence"
STAMP_KEYS = frozenset({"recorded_by", "recorded_sha256"})
_SYNTAX_MARKERS = ("SyntaxError", "IndentationError", "TabError")
_IMPORT_MARKERS = ("ImportError", "ModuleNotFoundError")


class EvidenceRunError(Exception):
    """Usage or package error before a command is classified."""


@dataclass
class EvidenceOutcome:
    payload: dict[str, Any]
    dest: Path
    authentic: bool
    errors: list[str] = field(default_factory=list)


def classify_failure(log: str, exit_code: int) -> str | None:
    """Map command output to evidence failure_category. None if the command passed."""
    if exit_code == 0:
        return None
    if any(marker in log for marker in _SYNTAX_MARKERS):
        return "syntax-error"
    if any(marker in log for marker in _IMPORT_MARKERS):
        return "import-error"
    if "AssertionError" in log or "assert " in log or "Failed:" in log:
        return AUTHENTIC_RED_CATEGORY
    return "fixture-error"


def _missing_import_hint(log: str) -> str:
    """A test that imports what does not exist yet at module level never gets to run.

    gemma-4-31b M02 (2026-09-26) wrote `from ratelimit.stats import StatsStore` at the top
    of a Red test, was told nine times that the test "could not run", and answered by
    creating the module in Declare - 25 refusals by the leash for editing product code.
    """
    if not any(marker in log for marker in _IMPORT_MARKERS):
        return ""
    return (
        ". A name the test imports at the top of its module does not exist yet, so the file "
        "cannot even be loaded, and a test that cannot load is not Red. Import it inside "
        "the test function instead: the test then runs and fails there. Do not create the "
        "module in this phase - product code is written in Implement"
    )


def _why_not_behavioral(log: str) -> str:
    """The line the classifier read, so a refusal can be acted on.

    52 of the 89 evidence refusals in the runs of 2026-09-23 were this one,
    and the record kept only the verdict: the log of a refused attempt is
    never stored, so neither the Worker nor a later reader could tell an
    erroring test from a passing one. The Core saw the output; it can say
    what it saw.
    """
    lines = [line.strip() for line in (log or "").splitlines() if line.strip()]
    if not lines:
        return "the command printed nothing to read"
    culprit = next(
        (line for line in reversed(lines) if "Error" in line or "error" in line),
        lines[-1],
    )
    return (
        "no AssertionError in the output, so the test did not fail on a value; "
        f"last error line: {culprit[:160]}"
    )


def _posix_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        rel = raw.replace("\\", "/").lstrip("/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def _load_change_id(change_path: Path) -> str:
    change_file = change_path / "change.yaml"
    if not change_file.is_file():
        raise EvidenceRunError(f"Missing required change.yaml in {change_path}")
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8"))
    except Exception as ex:
        raise EvidenceRunError(f"Failed to parse change.yaml: {ex}") from ex
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise EvidenceRunError("change.yaml must contain string id")
    return data["id"]


# Windows runs a `.cmd`/`.bat` runner through cmd.exe, which CreateProcess does not find by its
# bare name (Maven is `mvn.cmd`, Gradle `gradle.bat`/`gradlew.bat`).
BATCH_SUFFIXES = frozenset({".cmd", ".bat"})
# cmd.exe reads these in a batch file's arguments as its own (chaining, redirection, escapes,
# variables), so an argument holding one would run more than the test command.
CMD_METACHARACTERS = frozenset("&|<>^%")


def _on_windows() -> bool:
    return os.name == "nt"


def resolve_runner(argv: list[str], repo_root: Path) -> list[str]:
    """*argv* with a Windows batch runner replaced by the script it names.

    Fuse-Back on J01 (2026-10-08, Windows 11, Maven 3.9.12): `-- mvn -B test` ran nothing - Maven
    on Windows is `mvn.cmd`, CreateProcess does not find it by `mvn` - and Red was recorded
    `fixture-error` with `[WinError 2]`; writing `mvn.cmd` in the product breaks Linux and CI.
    Only a `.cmd`/`.bat` that `shutil.which` finds (PATHEXT) is substituted: anything else runs
    as given, because CreateProcess looks in the running interpreter's own directory first and a
    PATH lookup would swap the venv's `python` for another one. A runner with a path
    (`./gradlew`) is looked for in the product. Elsewhere than Windows the argv runs as given.
    """
    if not argv or not _on_windows():
        return list(argv)
    program = str(argv[0])
    target = program
    if "/" in program or "\\" in program:
        path = Path(program)
        target = str(path if path.is_absolute() else repo_root / path)
    found = shutil.which(target)
    if not found or Path(found).suffix.lower() not in BATCH_SUFFIXES:
        return list(argv)
    unsafe = [arg for arg in argv[1:] if CMD_METACHARACTERS & set(str(arg))]
    if unsafe:
        raise EvidenceRunError(
            f"'{program}' is the batch file {found}, which Windows runs through cmd.exe, and cmd.exe "
            f"reads & | < > ^ % in its arguments as its own: {', '.join(repr(a) for a in unsafe)}. "
            "Pass the test command without them; nothing was run or recorded"
        )
    return [found, *argv[1:]]


def _runner_not_found(program: str, ex: OSError) -> str:
    return f"runner `{program}` not found on PATH ({ex})"


def decode_output(raw: object) -> str:
    """A child's output as text: UTF-8 when it is valid UTF-8, else the locale's encoding.

    Audit 2026-11-16 (df-evidence #14): on a Russian Windows a child writes its pipe in the ANSI
    code page (cp1251) and the Core decoded it as UTF-8 with `replace`, so a Cyrillic message in a
    record's summary was mojibake. Text in a legacy code page is almost never valid UTF-8, so
    trying UTF-8 first keeps runners that write UTF-8 (pytest under PYTHONUTF8, Maven with
    `-Dfile.encoding=UTF-8`) as they are.
    """
    if raw is None:
        return ""
    if not isinstance(raw, bytes):
        return str(raw)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    import locale

    try:
        return raw.decode(locale.getpreferredencoding(False) or "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


# After the timeout kills the run, how long the Core still waits for its output pipes to close.
_DRAIN_SECONDS = 15


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill *proc* and every process it started.

    Audit 2026-11-16 (df-evidence #9): `subprocess.run(timeout=...)` killed only the program it
    started. Maven on Windows is `mvn.cmd`, so that was cmd.exe; java, its child, held the output
    pipes open, a 10 s timeout took 49.6 s, and a hanging test hung `deltafuse evidence`.
    """
    try:
        if _on_windows():
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=_DRAIN_SECONDS,
            )
        else:
            import signal

            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _launch(
    argv: list[str], *, cwd: Path, timeout: int, env: dict[str, str] | None = None
) -> tuple[int, bytes, bytes, bool]:
    """Run a test command: (exit code, stdout, stderr, timed out). FileNotFoundError when the
    program does not exist. On timeout the whole process tree is killed (`_kill_tree`)."""
    popen_kwargs: dict[str, Any] = {}
    if not _on_windows():
        popen_kwargs["start_new_session"] = True  # its own process group, killed as one
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        **popen_kwargs,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return int(proc.returncode), out or b"", err or b"", False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:
            out, err = b"", b""  # a grandchild outlived the kill and still holds the pipes
        return 124, out or b"", err or b"", True


def _contract_errors_now(change_path: Path, phase: str, dest: Path, route: str) -> list[str]:
    """The gate's changed_paths check on this record, now rather than at the gate.

    Fuse-Back shopkit (2026-10-08): evidence said "authentic" and the `declaring` gate refused the
    record a step later, when it could no longer be retaken.
    """
    if phase not in CONTRACT_GATES:
        return []
    contract = CONTRACT_GATES[phase][0]
    # Selected by file, not by the message text: the forbidden_paths and docs/ops messages name
    # the record without a colon after it, and a text filter dropped both at record time.
    return [
        msg + (
            " - the specification changed after the `specified` gate accepted it, and "
            f"{contract.capitalize()} does not write the specification"
            if "'docs/spec/" in msg else ""
        )
        for msg in _validate_evidence_changed_paths_contract(
            change_path, phase, route=route, only_file=dest.name
        )
    ]


def _sanitize_command(argv: list[str]) -> str:
    try:
        return shlex.join(argv)
    except Exception:
        return " ".join(argv)


def _red_failed_tests(change_path: Path, task: str | None) -> list[str]:
    """The tests the Red record of this task says failed."""
    if not task:
        return []
    tests = _load_record(change_path / "evidence" / "red" / f"{task}.yaml").get("tests")
    failed = tests.get("failed") if isinstance(tests, dict) else None
    return [str(name) for name in failed or [] if str(name).strip()]


def _isolated_oracle_run(
    change_path: Path, task: str | None, argv: list[str], repo_root: Path, timeout: int
) -> dict[str, Any] | None:
    """Run the frozen Red tests alone and say which of them did not pass.

    The Worker's own command decides what else runs next to the oracle, so it
    cannot be the only evidence that the product passes it (core/oracle.py,
    `isolation_plan`). The run is Green's pytest command with its test
    selection replaced by the frozen tests and `-p` dropped; PYTEST_ADDOPTS and
    PYTEST_PLUGINS, which load code the same way, are cleared.
    """
    if not task:
        return None
    frozen = _load_record(change_path / "evidence" / "red" / f"{task}.yaml").get("red_oracle_tests")
    if not isinstance(frozen, dict) or frozen.get("version") is None:
        return None
    plan = isolation_plan(argv, frozen, _red_failed_tests(change_path, task), repo_root)
    if plan is None:
        return None
    iso_argv, expected = plan
    junit_path: Path | None = None
    run_argv = list(iso_argv)
    if wants_junit_flag(iso_argv):
        report_dir = repo_root / ".deltafuse" / "tmp"
        report_dir.mkdir(parents=True, exist_ok=True)
        junit_path = report_dir / f"junit-green-isolated-{task}.xml"
        junit_path.unlink(missing_ok=True)
        run_argv.append(f"--junitxml={junit_path}")
    env = {k: v for k, v in os.environ.items() if k not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    started_at = time.time()
    try:
        exit_code = _launch(resolve_runner(run_argv, repo_root), cwd=repo_root, timeout=timeout, env=env)[0]
    except FileNotFoundError:
        exit_code = 127
    report = read_report(iso_argv, repo_root, junit_path=junit_path, newer_than=started_at)
    not_passing = green_covers_red(expected, report) if report is not None else list(expected)
    return {
        "command": _sanitize_command(iso_argv),
        "exit_code": exit_code,
        "not_passing": not_passing,
    }


def _lock_pin(product_root: Path) -> str:
    lock = Path(product_root) / ".deltafuse" / "lock.yaml"
    if not lock.is_file():
        return ""
    try:
        data = yaml.safe_load(lock.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    framework = data.get("framework")
    if not isinstance(framework, dict):
        return ""
    pin = framework.get("content_hash")
    return pin if isinstance(pin, str) else ""


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%dT%H:%M:%SZ")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    return value


def stamp_digest(payload: dict[str, Any], product_root: Path) -> str:
    body = {key: payload[key] for key in payload if key not in STAMP_KEYS}
    material = {"pin": _lock_pin(product_root), "evidence": _jsonable(body)}
    raw = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _as_yaml_reads_it(payload: dict[str, Any]) -> dict[str, Any]:
    """*payload* as a reader of the written record gets it back.

    Audit 2026-11-17 (FE-14): the stamp was computed over the payload in memory, and YAML does
    not return every string as written - U+0085 (NEL) in a runner's output is a line break to it -
    so the Core refused a record it had just stamped. The stamp is taken over the round-tripped
    payload, whatever field the character is in and however the record is dumped afterwards.
    """
    current = payload
    for _ in range(3):  # one pass settles it; a second confirms
        try:
            back = yaml.safe_load(yaml.safe_dump(current, sort_keys=False, allow_unicode=True))
        except yaml.YAMLError:
            return current
        if not isinstance(back, dict) or back == current:
            return current
        current = back
    return current


def stamp_evidence(payload: dict[str, Any], product_root: Path) -> dict[str, Any]:
    """Return a copy of *payload* with the kernel evidence stamp."""
    out = _as_yaml_reads_it({key: value for key, value in payload.items() if key not in STAMP_KEYS})
    out["recorded_by"] = RECORDED_BY
    out["recorded_sha256"] = stamp_digest(out, product_root)
    return out


def evidence_stamp_error(payload: dict[str, Any], product_root: Path) -> str | None:
    """None when the kernel stamp matches the payload."""
    if not isinstance(payload, dict):
        return "evidence is not a mapping"
    if payload.get("recorded_by") != RECORDED_BY:
        return "evidence is not stamped by deltafuse evidence"
    want = stamp_digest(payload, product_root)
    if payload.get("recorded_sha256") != want:
        return "evidence stamp does not match the recorded payload"
    return None


def write_stamped_evidence(
    path: Path,
    payload: dict[str, Any],
    product_root: Path,
    lock_timeout: float = 5.0,
) -> dict[str, Any]:
    """Stamp *payload* and write YAML under ProductMutationLock using atomic storage."""
    from deltafuse.core.artifact_registry import ArtifactRegistry
    from deltafuse.core.artifact_lock import ProductMutationLock
    from deltafuse.core.artifact_storage import atomic_create, atomic_replace

    registry = ArtifactRegistry()
    val_res = registry.validate_storage_schema("evidence", payload)
    if not val_res.valid:
        diag_msgs = [f"{d.path}: {d.message}" for d in val_res.diagnostics]
        raise EvidenceRunError(f"Evidence storage schema validation failed: {'; '.join(diag_msgs)}")

    stamped = stamp_evidence(payload, product_root)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    yaml_bytes = yaml.safe_dump(stamped, sort_keys=False, allow_unicode=True).encode("utf-8")

    with ProductMutationLock(product_root, timeout=lock_timeout):
        if dest.is_file():
            atomic_replace(dest, yaml_bytes)
        else:
            atomic_create(dest, yaml_bytes)

    return stamped



def _core_computed_changed_paths(repo_root: Path, change_path: Path | None = None) -> list[str]:
    """Core-derived dirty paths the Worker is accountable for.

    Worker lists are an expected subset of this set, so it must hold only the
    Worker's own changes. q0 run 20260921T081038Z: the raw git diff also held
    the Core's journals (`.deltafuse/**`), interpreter caches (`__pycache__`)
    and the evidence file this very command had just written, and the Worker
    was told to list them - the same class of defect the leash had.
    """
    try:
        paths = git_dirty_paths(repo_root)
    except LeashError:
        # No git repository (bench sandbox, fresh install): nothing to derive.
        return []
    accepted: set[str] = set()
    if change_path is not None:
        # Specify's output, uncommitted and untouched since the `specified` gate accepted it,
        # is not this phase's change (core/spec_baseline.py; Fuse-Back shopkit 2026-10-08).
        from deltafuse.core.spec_baseline import unchanged_since_specified

        accepted = unchanged_since_specified(repo_root, _load_change_id(change_path))
    out: list[str] = []
    for raw in paths:
        rel = posix_relpath(raw)
        parts = rel.split("/")
        if is_exempt_path(rel):
            continue  # .deltafuse/**, interpreter caches, the other leash exemptions
        if rel in accepted:
            continue
        if parts[:2] == ["docs", "changes"]:
            # The Change's own bookkeeping, not a product change: its evidence
            # (written by this command), task files `state` rewrites, coverage.
            # q0 run M03 20260921T215701Z asked the Worker to list them.
            continue
        out.append(raw)
    return out

DECLARE_CHANGE_STATUSES = frozenset({"decomposed", "declaring"})


def _task_status(change_path: Path, task: str) -> tuple[str, Any] | None:
    """(task id, status) of *task*; None when the task is unknown or unreadable, which is
    refused where it always was."""
    from deltafuse.core.frontmatter import parse_frontmatter
    from deltafuse.core.transitions import _artifact_file

    try:
        task_file, task_id = _artifact_file(change_path / "tasks", task, "task")
        meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return task_id, (meta.get("status") if isinstance(meta, dict) else None)


def _task_allowed_paths(change_path: Path, task: str) -> list[str]:
    """The task's declared allowed_paths; empty when the task file cannot be read."""
    from deltafuse.core.frontmatter import parse_frontmatter
    from deltafuse.core.transitions import _artifact_file

    try:
        task_file, _ = _artifact_file(change_path / "tasks", task, "task")
        meta, _ = parse_frontmatter(task_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    allowed = meta.get("allowed_paths") if isinstance(meta, dict) else None
    return [str(p) for p in allowed or [] if isinstance(p, str)]


def _refuse_red_after_declare(change_path: Path, task: str) -> None:
    """Red belongs to Declare; past it, retaking Red would re-freeze the oracle.

    Gemma 31B shakedown cls-g31s5-m02 (2026-10-05): during Implement, with its Green refused
    ("Green did not turn the Red tests green"), the Worker recorded Red for TASK-001 again,
    three times, each accepted as authentic. A Red retaken there freezes whatever the tests
    are at that moment, so the frozen-oracle check no longer guards the declared one.
    """
    found = _task_status(change_path, task)
    if found is None:
        return
    task_id, status = found
    if status == "declared":
        try:
            change = yaml.safe_load((change_path / "change.yaml").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a broken change.yaml is reported elsewhere
            change = None
        if isinstance(change, dict) and change.get("status") in DECLARE_CHANGE_STATUSES:
            return
    if status in RED_TAKEN_STATUSES:
        raise EvidenceRunError(
            f"{task_id} is '{status}': its Red was recorded in Declare and froze the declared "
            "oracle, so Red is not taken again - that would freeze the tests as they are now. "
            "In Implement record green and regression; if the declared oracle itself is wrong, "
            "record Green against it as declared, then mark the task blocked (`deltafuse state "
            f"<change-dir> --task {task_id} --status blocked`), say why, and stop. Nothing was run "
            "or recorded"
        )


def _refuse_red_over_a_siblings_oracle(change_path: Path, task: str, repo_root: Path) -> None:
    """A test another task's Red froze is that task's oracle: this Red may not change it.

    ref-m02-366-1 (2026-10-11): TASK-003, reopened and declared again, rewrote
    `test_interleaved_admits_never_block`, which TASK-002's Red had already frozen. Two Reds then
    froze two bodies of one test, no file could satisfy both, and the run went round Implement
    until it was stopped. The conflict is refused here, while a new test can still be written.
    """
    from deltafuse.core.oracle import red_oracle_changes

    closed = {
        str(meta.get("id") or tf.stem)
        for tf, meta in _frontmatters(change_path / "tasks")
        if meta.get("status") == "cancelled"
    }
    for record in sorted((change_path / "evidence" / "red").glob("*.yaml")):
        sibling = record.stem
        if sibling == task or sibling in closed:
            continue
        frozen = _load_record(record).get("red_oracle_tests")
        if not isinstance(frozen, dict):
            continue
        changes = red_oracle_changes(repo_root, frozen)
        if changes:
            raise EvidenceRunError(
                f"{sibling}'s Red froze its oracle, and the tree no longer matches it: "
                f"{'; '.join(changes)}. A test another task's Red froze is that task's oracle - "
                f"restore it as it was frozen and write a new test for {task}; "
                "nothing was run or recorded"
            )


def sibling_red_tests(change_path: Path, task: str) -> dict[str, str]:
    """Test id -> the other task of this Change whose Red record names it as failing.

    Audit 2026-11-17 (FE-1): a test another task's Red recorded is that task's test. Declare runs
    for every task before Implement, so an earlier task's Red test is still failing, and still
    uncommitted, when the next task takes its Red; read as the next task's own, it made that
    Red authentic while the task's own test already passed. A cancelled task holds no test.
    """
    cancelled = {
        str(meta.get("id") or tf.stem)
        for tf, meta in _frontmatters(change_path / "tasks")
        if meta.get("status") == "cancelled"
    }
    taken: dict[str, str] = {}
    for record in sorted((change_path / "evidence" / "red").glob("*.yaml")):
        sibling = record.stem
        if sibling == task or sibling in cancelled:
            continue
        tests = _load_record(record).get("tests")
        for name in (tests.get("failed") if isinstance(tests, dict) else None) or []:
            taken.setdefault(str(name), sibling)
    return taken


def _refuse_green_for_a_closed_task(change_path: Path, task: str) -> None:
    """A superseded or cancelled task has no Green: it is not implemented.

    ref-m03-346 (2026-10-07): a Green recorded for a task superseded on an already-green Red
    was accepted here and then refused by the implemented gate, with no step left to clear it.
    """
    found = _task_status(change_path, task)
    if found is None:
        return
    task_id, status = found
    if status in _TASKS_CLOSED:
        raise EvidenceRunError(
            f"{task_id} is '{status}': it is not implemented, so it has no Green - "
            + ("its Red already passed and its test stays as regression. " if status == "superseded" else "")
            + "Nothing was run or recorded; go on with the next task `deltafuse next` names"
        )


def run_evidence(
    change_dir: Path | str,
    *,
    phase: str,
    task: str | None = None,
    argv: list[str],
    changed_paths: list[str] | None = None,
    timeout: int | None = None,
) -> EvidenceOutcome:
    """Execute *argv* at the product root and write evidence/<phase>/<task|run>.yaml."""
    if phase not in {"red", "green", "regression", "verification"}:
        raise EvidenceRunError(f"Unsupported evidence phase '{phase}'")
    if not argv:
        raise EvidenceRunError("Command argv is required after '--'")
    if str(argv[0]).startswith("-"):
        # gemma-334-probe M01: `-- --changed-path X -- pytest` ran `--changed-path`
        # as a program, recorded exit 127 as a `fixture-error`, and the Worker
        # spent its attempts editing product code to change a category that
        # was its own typo.
        raise EvidenceRunError(
            f"'{argv[0]}' is an option of `deltafuse evidence`, not a command: options go "
            "before '--', and only the test command after it "
            "(`deltafuse evidence <change-dir> --phase red --task <id> [--changed-path P] -- pytest tests/...`); "
            "nothing was run or recorded"
        )

    if phase == "verification":
        if task is not None and task != "null" and task != "":
            raise EvidenceRunError(f"Verification phase requires task=None, got '{task}'")
        task = None
    else:
        if not task:
            raise EvidenceRunError(f"Evidence phase '{phase}' requires task ID (e.g. TASK-001)")

    change_path = Path(change_dir).resolve()
    if not change_path.is_dir():
        raise EvidenceRunError(f"Change package directory not found: {change_path}")

    if phase == "red":
        _refuse_red_after_declare(change_path, str(task))
    if phase == "green":
        _refuse_green_for_a_closed_task(change_path, str(task))

    repo_root = find_repo_root(change_path)
    if timeout is None:
        timeout = load_evidence_timeout(repo_root)
    if phase == "red":
        _refuse_red_over_a_siblings_oracle(change_path, str(task), repo_root)
    change_id = _load_change_id(change_path)
    route, route_errs = load_change_route(change_path)
    rel_paths = _posix_paths(changed_paths or [])
    if not rel_paths:
        # The Core computes the changed set from git anyway and refused a list
        # that missed any of it; with no list it records its own (roadmap item
        # 4: box B -> box A). A list the Worker gives is still checked.
        # Verification too: it recorded none and then refused itself for not
        # listing the dirty set (audit 2026-11-16, df-gates #10).
        rel_paths = _posix_paths(_core_computed_changed_paths(repo_root, change_path))

    _as_text = decode_output

    timed_out = False
    # pytest writes a machine-readable report only when asked; the Core asks,
    # so the Worker's choice of `--tb=` stops deciding how its evidence reads.
    report_dir = repo_root / ".deltafuse" / "tmp"
    junit_path: Path | None = None
    run_argv = list(argv)
    if wants_junit_flag(argv):
        report_dir.mkdir(parents=True, exist_ok=True)
        junit_path = report_dir / f"junit-{phase}-{task or 'run'}.xml"
        junit_path.unlink(missing_ok=True)
        run_argv = [*argv, f"--junitxml={junit_path}"]
    elif runner_family(argv) == "pytest" and worker_junit_path(argv):
        # The Worker named the report itself: read that one, if this run wrote it.
        junit_path = repo_root / str(worker_junit_path(argv))
    launch_argv = resolve_runner(run_argv, repo_root)
    started_at = time.time()
    try:
        exit_code, out, err, timed_out = _launch(launch_argv, cwd=repo_root, timeout=timeout)
        log = (_as_text(out) + _as_text(err)).strip()
        if timed_out and not log:
            log = f"command timed out after {timeout}s"
    except FileNotFoundError as ex:
        exit_code = 127
        log = _runner_not_found(str(argv[0]), ex)

    report = read_report(argv, repo_root, junit_path=junit_path, newer_than=started_at)
    category = classify_failure(log, exit_code)
    # Red is judged on the task's own tests, not on the whole report (`task_test_ids`).
    task_report = report
    red_why: str | None = None  # why the runner's report does not make this an authentic Red
    taken: dict[str, str] = {}
    if phase == "red" and report is not None:
        taken = sibling_red_tests(change_path, str(task))
        named, named_by = task_test_ids(report, rel_paths, argv, repo_root, taken=taken)
        task_report = restricted(report, named or [])
        if named is None:
            category = UNNAMED_RED_CATEGORY
            red_why = (
                "Red does not say which tests are the task's: no test file is among its changed_paths "
                "and the command names no test file or class (`pytest tests/test_x.py`, "
                "`mvn test -Dtest=CalcTest`), so a failure (or a pass) anywhere in the suite would "
                "read as this task's Red. Name the task's tests and record Red again"
            )
    if phase == "red" and exit_code != 0 and report is not None and red_why is None:
        # The gate reads this field, and the Core has just judged Red by the
        # runner's own report. The two must not disagree: in the runs of
        # 2026-09-25/26, 23 of 44 Red records whose report said "the tests ran
        # and failed" were still recorded `fixture-error` (the log had no
        # `assert `), and the `declaring` gate refused them.
        ok, why = red_is_authentic(task_report)
        others = [t for t in report.ids(FAILED) + report.ids(NOT_RUN) if t not in task_report.outcomes]
        if ok:
            category = AUTHENTIC_RED_CATEGORY
        elif not task_report.ids(FAILED) and not task_report.ids(NOT_RUN) and others:
            # Audit 2026-11-16 (df-evidence #1): the run failed, but on tests that are not the
            # task's, while the task's own tests passed or did not run.
            category = NOT_THE_TASKS_RED_CATEGORY
            red_why = (
                f"the task's own tests - {named_by} - did not fail "
                f"({'passed: ' + ', '.join(task_report.ids(PASSED)[:5]) if task_report.ids(PASSED) else 'none of them ran'}); "
                f"the run failed on other tests ({', '.join(others[:5])}), and a failure of a test "
                "that is not the task's is not its Red"
            )
            held = {t: taken[t] for t in others if t in taken}
            if held:
                owners = sorted(set(held.values()))
                first = owners[0]
                red_why += (
                    f". {', '.join(list(held)[:5])} failed in {first}'s Red, so "
                    + ("it is" if len(held) == 1 else "they are")
                    + f" {first}'s Red test" + ("" if len(held) == 1 else "s")
                    + f": write this task's own failing test. If the test is this task's and {first}'s "
                    f"record took it by mistake, record {first}'s Red again naming only its own tests "
                    f"(`deltafuse evidence <change-dir> --phase red --task {first} -- <command naming "
                    f"{first}'s test file>`), then record this Red"
                )
        else:
            red_why = f"{why}{_missing_import_hint(log)}"
            if category == AUTHENTIC_RED_CATEGORY:
                # The log mentioned an assertion but nothing ran, or a test could not
                # run: not a behavioural failure however the log reads.
                category = "fixture-error"
    own_code = None
    if phase == "red" and exit_code != 0 and report is not None and category == AUTHENTIC_RED_CATEGORY:
        # The gate reads the category, so a test no product code can pass is not
        # recorded as a behavioural failure (ref-m02-339, core/red_cause.py).
        own_code = own_code_error(task_report, repo_root)
        if own_code:
            category = OWN_CODE_RED_CATEGORY
        else:
            # Audit 2026-11-16 (df-evidence #7): a missing data file or package is not Red.
            own_code = environment_error(task_report, repo_root, _task_allowed_paths(change_path, str(task)))
            if own_code:
                category = ENVIRONMENT_RED_CATEGORY
    summary = (log[-800:] if log else ("timed out" if timed_out else "no output"))
    private_errors: list[str] = []
    if phase == "red" and route == "code":
        private_errors = scan_changed_paths_for_private_test_access(repo_root, rel_paths)

    if timed_out:
        result = "blocked"
    elif phase == "red":
        result = "already-green" if exit_code == 0 else "expected-failure"
    else:
        result = "passed" if exit_code == 0 else "failed"
    if result == "already-green" and task_report is not None and not task_report.ids(PASSED):
        # Audit 2026-11-16 (df-evidence #10): every test of the task skipped (or xfailed), or
        # none of them ran, and the run still exited 0. Nothing passed, so nothing shows the
        # behaviour is already there - and an already-green Red lets the task be superseded,
        # leaving no test of it at all.
        result = "blocked"
        skipped = task_report.ids(SKIPPED)
        red_why = red_why or (
            "none of the task's tests passed or failed - "
            + (f"they were skipped or expected to fail (xfail): {', '.join(skipped[:5])}" if skipped
               else "the runner's report names none of them")
            + "; a Red that ran nothing shows neither that the behaviour is missing nor that it is "
            "already there. Make the task's tests run, and record Red again"
        )

    payload: dict[str, Any] = {
        "schema_version": 3,
        "change": change_id,
        "task": task,
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": _sanitize_command(argv),
        "exit_code": exit_code,
        "result": result,
        "failure_category": category,
        "summary": summary,
        "changed_paths": rel_paths,
        "spec_status": "unchanged",
    }
    if report is not None:
        payload["tests"] = {
            "source": report.source,
            # A Red record's failures are its oracle: the task's own tests, not every test
            # that failed in the run (another task's, or one broken before the Change).
            "failed": (task_report if phase == "red" else report).ids(FAILED),
            "passed": report.ids(PASSED),
            "not_run": (task_report if phase == "red" else report).ids(NOT_RUN),
            "skipped": report.ids(SKIPPED),
        }
    isolation = None
    if phase == "green" and route == "code" and exit_code == 0 and not timed_out:
        isolation = _isolated_oracle_run(change_path, task, argv, repo_root, timeout)
        if isolation is not None:
            payload["oracle_isolation"] = isolation
    if phase in {"green", "regression", "verification"}:
        payload["base_revision"] = compute_product_baseline_revision(repo_root)
    if phase == "red":
        # Freezes the declared oracle at the moment Red is taken: the
        # implemented gate recomputes it and refuses a Green recorded over a
        # test rewritten during Implement. With the runner's report the Core
        # knows which tests are the oracle and freezes those; without one it
        # can only freeze the declared files whole, as 3.3.5 first did.
        red_failed = task_report.ids(FAILED) if task_report is not None else []
        if red_failed:
            # The files the failed tests live in, also when Declare did not write them: a Red
            # over a committed test froze nothing, and Implement weakened that test (audit
            # 2026-11-16, df-evidence #2).
            frozen = freeze_red_oracle(
                repo_root, rel_paths, red_failed,
                test_files=task_test_files(report, rel_paths, argv, repo_root),
            )
            if frozen:
                payload["red_oracle_tests"] = frozen
        else:
            oracle = compute_red_oracle_digest(repo_root, rel_paths)
            if oracle:
                payload["red_oracle"] = oracle

    if phase == "verification":
        # q4 decision D, phase 1: the code the Change touched against the
        # capabilities routing named. Recorded, not judged (T9 in the bench).
        from deltafuse.core.ownership import under_routing

        payload["ownership"] = under_routing(repo_root, change_path)
        dest = change_path / "evidence" / "verification" / "run.yaml"
    else:
        dest = change_path / "evidence" / phase / f"{task}.yaml"

    payload = write_stamped_evidence(dest, payload, repo_root)

    errors = list(route_errs)
    runner_ok = runner_is_authorized(argv, route=route, product_root=repo_root)
    if not runner_ok:
        errors.append(
            f"evidence: command {argv[:3]} is not an authorized runner for route '{route}'; "
            "configure workflow.test_commands in .deltafuse/config.yaml (DF3-006/B-04)"
        )
    report_less = report_less_runner_error(argv, route=route, product_root=repo_root)
    if report_less:
        errors.append(f"evidence: {report_less}")
    computed = _core_computed_changed_paths(repo_root, change_path)
    if computed:
        worker_paths = set(rel_paths)
        missing = sorted(p for p in computed if p not in worker_paths)
        if missing:
            errors.append(
                "evidence: changed_paths must include the Core-computed dirty set; "
                f"missing {missing}"
            )
    errors.extend(private_errors)
    errors.extend(_contract_errors_now(change_path, phase, dest, route))
    if phase == "red" and route == "code" and result == "blocked" and red_why:
        errors.append(f"Red is not authentic: {red_why}")
    if phase == "red" and route == "code" and result == "expected-failure":
        if report is not None:
            # The runner's own report, read through its ecosystem's meaning of
            # `<error>`: pytest says the test never ran, Surefire says it ran
            # and threw. The rule is written in neutral words for that reason.
            if red_why:
                errors.append(f"Red is not authentic: {red_why}")
            elif own_code:
                errors.append(own_code)
        elif category != AUTHENTIC_RED_CATEGORY:
            # No machine-readable report from this runner: the old heuristic,
            # marked as such in the record so a weaker verdict is visible.
            errors.append(
                f"Red failure_category is '{category}', not '{AUTHENTIC_RED_CATEGORY}': "
                f"{_why_not_behavioral(log)}"
            )
    if phase == "green":
        # The implemented gate's own judgement of this Green, now rather than two steps later:
        # the Worker that just rewrote the oracle, or recorded Green over an already-green or
        # missing Red, hears it while it can still act.
        red_file = change_path / "evidence" / "red" / f"{task}.yaml"
        errors.extend(
            f"evidence: {e}"
            for e in green_record_errors(red_file, dest, repo_root, route=route, label=f"this Green ({task})")
        )
    if phase != "red" and result != "passed":
        errors.append(f"{phase} command exited {exit_code}, expected 0")
    if phase in {"green", "regression", "verification"} and route == "code" and result == "passed":
        errors.extend(no_test_error(phase, argv, payload.get("tests"), log))  # the full log, not the summary
    if phase in {"regression", "verification"} and route == "code":
        # Every test of the whole suite, whatever the exit code (audit 2026-11-16, df-evidence #4).
        errors.extend(suite_errors(phase, argv, payload.get("tests"), repo_root))
    if timed_out:
        errors.append(f"command timed out after {timeout}s")

    # Authentic means nothing above refused the record: every way a run can fail to be
    # evidence appends its reason to `errors` (a refusal with no explanation would leave
    # the Worker guessing - F4), so the verdict is the empty list, not a second rulebook.
    authentic = not errors

    return EvidenceOutcome(
        payload=payload,
        dest=dest,
        authentic=authentic,
        errors=errors,
    )
