import sys
from pathlib import Path

import yaml

from deltafuse.core.evidence import classify_failure, run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _run_file_cmd(*rel: str) -> list[str]:
    return [sys.executable, *rel]


def _declare(builder: MockChangeBuilder, task_id: str = "TASK-001") -> None:
    """The Worker declares the task through the Core; the declaring gate needs
    every task declared with its own Red evidence."""
    from deltafuse.core.transitions import set_artifact_status

    set_artifact_status(builder.change_dir, status="declared", task_id=task_id)


def _decomposed(tmp_path: Path, repo_root: Path, change_id: str = "CHG-020") -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Evidence runner")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def test_classify_failure_markers():
    assert classify_failure("AssertionError: x is False", 1) == "behavioral-mismatch"
    assert classify_failure("E       assert 1 == 2", 1) == "behavioral-mismatch"
    assert classify_failure("SyntaxError: invalid syntax", 1) == "syntax-error"
    assert classify_failure("ImportError: cannot import name 'x'", 1) == "import-error"
    assert classify_failure("ModuleNotFoundError: No module named 'x'", 1) == "import-error"
    assert classify_failure("OSError: boom", 1) == "fixture-error"
    assert classify_failure("", 0) is None


def test_run_evidence_red_behavioral(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-020")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "assert False, 'not implemented'\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    assert outcome.authentic
    assert outcome.payload["result"] == "expected-failure"
    assert outcome.payload["failure_category"] == "behavioral-mismatch"
    assert outcome.payload["exit_code"] != 0
    assert outcome.payload["recorded_by"] == "deltafuse-evidence"
    assert str(outcome.payload["recorded_sha256"]).startswith("sha256:")
    _declare(builder)
    assert check_gate(builder.change_dir, "declaring") == []


def test_run_evidence_red_syntax_not_authentic(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-021")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text("def test_broken(\n", encoding="utf-8")
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    assert not outcome.authentic
    assert outcome.payload["failure_category"] == "syntax-error"
    assert any("behavioral-mismatch" in e for e in check_gate(builder.change_dir, "declaring"))


def test_run_evidence_red_import_not_authentic(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-022")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "import definitely_missing_wk002_module\nassert True\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    assert not outcome.authentic
    assert outcome.payload["failure_category"] == "import-error"
    errs = check_gate(builder.change_dir, "declaring")
    assert any("behavioral-mismatch" in e for e in errs)


def test_run_evidence_red_private_not_authentic(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-023")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "limiter = type('L', (), {})()\n"
        "limiter._blocked_until = {'u': 0.0}\n"
        "assert False\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    assert not outcome.authentic
    assert any("private symbols" in e for e in outcome.errors)
    errs = check_gate(builder.change_dir, "declaring")
    assert any("private symbols" in e for e in errs)


def test_run_evidence_already_green(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-024")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text("assert True\n", encoding="utf-8")
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    assert outcome.authentic
    assert outcome.payload["result"] == "already-green"
    assert outcome.payload["exit_code"] == 0
    _declare(builder)
    assert check_gate(builder.change_dir, "declaring") == []


def test_run_evidence_green_records_base_revision(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-025")
    status_before = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )["status"]
    # DF3-006/B-04: green must come from a real runner script, not `python -c`.
    runner_file = tmp_path / "tests" / "test_task-001.py"
    runner_file.parent.mkdir(parents=True, exist_ok=True)
    runner_file.write_text("raise SystemExit(0)\n", encoding="utf-8")
    outcome = run_evidence(
        builder.change_dir,
        phase="green",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py", "src/core.py"],
    )
    assert outcome.authentic
    assert outcome.payload["result"] == "passed"
    assert str(outcome.payload["base_revision"]).startswith("sha256:")
    status_after = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )["status"]
    assert status_after == status_before


def test_handwritten_red_yaml_fails_targeting(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-040")
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 3,
        "change": "CHG-040",
        "task": "TASK-001",
        "phase": "red",
        "timestamp": "2026-09-05T12:00:00Z",
        "command": "pytest tests/test_task-001.py",
        "exit_code": 1,
        "result": "expected-failure",
        "failure_category": "behavioral-mismatch",
        "summary": "Hand-written without a kernel stamp",
        "changed_paths": ["tests/test_task-001.py"],
        "spec_status": "unchanged",
    }
    from deltafuse.core.schemas import default_registry

    assert default_registry.validate("evidence", payload) == []
    (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
    errs = check_gate(builder.change_dir, "declaring")
    assert any("not stamped by deltafuse evidence" in e for e in errs)


def test_tampered_evidence_stamp_fails_targeting(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-041")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text(
        "assert False, 'not implemented'\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=_run_file_cmd("tests/test_task-001.py"),
        changed_paths=["tests/test_task-001.py"],
    )
    _declare(builder)
    assert check_gate(builder.change_dir, "declaring") == []
    payload = dict(outcome.payload)
    payload["exit_code"] = 0
    payload["result"] = "already-green"
    payload["summary"] = "Edited by eye after the kernel stamp"
    outcome.dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    errs = check_gate(builder.change_dir, "declaring")
    assert any("stamp does not match the recorded payload" in e for e in errs)


def test_verification_phase_requires_task_none(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-050")
    import pytest
    from deltafuse.core.evidence import EvidenceRunError
    with pytest.raises(EvidenceRunError) as exc_info:
        run_evidence(
            builder.change_dir,
            phase="verification",
            task="TASK-001",
            argv=_run_file_cmd("tests/test_task-001.py"),
        )
    assert "verification" in str(exc_info.value).lower() or "task" in str(exc_info.value).lower()


def test_verification_phase_writes_run_yaml(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-051")
    runner_file = tmp_path / "tests" / "test_verif.py"
    runner_file.parent.mkdir(parents=True, exist_ok=True)
    runner_file.write_text("raise SystemExit(0)\n", encoding="utf-8")

    outcome = run_evidence(
        builder.change_dir,
        phase="verification",
        task=None,
        argv=_run_file_cmd("tests/test_verif.py"),
    )
    assert outcome.dest == builder.change_dir / "evidence" / "verification" / "run.yaml"
    assert outcome.dest.is_file()
    assert outcome.payload["phase"] == "verification"
    assert outcome.payload["task"] is None
    assert "base_revision" in outcome.payload




def test_core_changed_paths_hold_only_the_workers_changes(tmp_path: Path):
    """q0 run 20260921T081038Z: the Core-derived dirty set also held the Core's
    own journals, interpreter caches and the evidence file `deltafuse evidence`
    had just written, and the Worker was told to list them."""
    import subprocess

    from deltafuse.core.evidence import _core_computed_changed_paths

    def write(rel: str, text: str = "x\n") -> None:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write("src/core.py")
    write(".deltafuse/transitions.jsonl", "{}\n")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=e@test", "-c", "user.name=e", "-c", "commit.gpgsign=false",
         "commit", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    write("src/core.py", "y\n")
    write("tests/test_core.py")
    write(".deltafuse/transitions.jsonl", "{}\n{}\n")
    write("src/__pycache__/core.cpython-312.pyc")
    write("tests/.pytest_cache/v/cache/lastfailed", "{}\n")
    write("docs/changes/CHG-001-x/evidence/red/TASK-001.yaml", "phase: red\n")
    write("docs/changes/CHG-001-x/tasks/TASK-001.md")

    paths = sorted(p.replace("\\", "/") for p in _core_computed_changed_paths(tmp_path))
    assert paths == [
        "docs/changes/CHG-001-x/tasks/TASK-001.md",
        "src/core.py",
        "tests/test_core.py",
    ]
