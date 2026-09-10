import sys
from pathlib import Path

import yaml

from deltafuse.core.evidence import classify_failure, run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _run_file_cmd(*rel: str) -> list[str]:
    return [sys.executable, *rel]


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
    assert check_gate(builder.change_dir, "targeting") == []


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
    assert any("behavioral-mismatch" in e for e in check_gate(builder.change_dir, "targeting"))


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
    errs = check_gate(builder.change_dir, "targeting")
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
    errs = check_gate(builder.change_dir, "targeting")
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
    assert check_gate(builder.change_dir, "targeting") == []


def test_run_evidence_green_records_base_revision(tmp_path: Path, repo_root: Path):
    builder = _decomposed(tmp_path, repo_root, "CHG-025")
    status_before = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )["status"]
    outcome = run_evidence(
        builder.change_dir,
        phase="green",
        task="TASK-001",
        argv=[sys.executable, "-c", "raise SystemExit(0)"],
        changed_paths=["src/core.py"],
    )
    assert outcome.authentic
    assert outcome.payload["result"] == "passed"
    assert str(outcome.payload["base_revision"]).startswith("sha256:")
    status_after = yaml.safe_load(
        (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    )["status"]
    assert status_after == status_before
