"""Integration tests for Core execution evidence and verification phase (AW-12).

Validates verification phase evidence execution (task=null, run.yaml),
Core stamp verification, authorization, and baseline binding.
"""

import json
from pathlib import Path
import subprocess
import sys
import pytest
import yaml

from deltafuse.core.evidence import run_evidence, EvidenceRunError, evidence_stamp_error
from deltafuse.core.installer import install
from deltafuse.core.fsm import check_gate
from tests.fixtures.change_builder import MockChangeBuilder


def _decomposed_change(tmp_path: Path, repo_root: Path, change_id: str = "CHG-120") -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    return (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Verification Integration")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )


def test_verification_phase_with_task_param_rejected(tmp_path: Path, repo_root: Path):
    builder = _decomposed_change(tmp_path, repo_root, "CHG-121")
    with pytest.raises(EvidenceRunError) as exc_info:
        run_evidence(
            builder.change_dir,
            phase="verification",
            task="TASK-001",  # Invalid for verification phase!
            argv=[sys.executable, "-c", "import sys; sys.exit(0)"],
        )
    assert "verification" in str(exc_info.value).lower() or "task" in str(exc_info.value).lower()


def test_verification_phase_writes_run_yaml(tmp_path: Path, repo_root: Path):
    builder = _decomposed_change(tmp_path, repo_root, "CHG-122")

    # Verification expects task=None and writes to evidence/verification/run.yaml
    runner_script = tmp_path / "tests" / "test_verification.py"
    runner_script.parent.mkdir(parents=True, exist_ok=True)
    runner_script.write_text("print('All verification tests passed')\n", encoding="utf-8")

    outcome = run_evidence(
        builder.change_dir,
        phase="verification",
        task=None,
        argv=[sys.executable, str(runner_script)],
    )

    dest = builder.change_dir / "evidence" / "verification" / "run.yaml"
    assert dest.is_file()
    assert outcome.dest == dest

    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["phase"] == "verification"
    assert data["task"] is None
    assert "base_revision" in data
    assert data["recorded_by"] == "deltafuse-evidence"
    assert evidence_stamp_error(data, tmp_path) is None


def test_cli_evidence_verification_subprocess(tmp_path: Path, repo_root: Path):
    builder = _decomposed_change(tmp_path, repo_root, "CHG-123")
    runner_script = tmp_path / "tests" / "test_verification_cli.py"
    runner_script.parent.mkdir(parents=True, exist_ok=True)
    runner_script.write_text("print('CLI Verification OK')\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "evidence", str(builder.change_dir),
        "--phase", "verification",
        "--", sys.executable, str(runner_script)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    run_yaml = builder.change_dir / "evidence" / "verification" / "run.yaml"
    assert run_yaml.is_file()


def _pytest_product(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    """A decomposed Change whose product has a real pytest suite."""
    builder = _decomposed_change(tmp_path, repo_root, change_id)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "limiter.py").write_text(
        "class Limiter:\n    def __init__(self):\n        pass\n", encoding="utf-8"
    )
    return builder


def test_red_is_read_from_the_runners_own_report(tmp_path: Path, repo_root: Path):
    """The Core asks pytest for a report and judges Red by what it says.

    Before 3.3.3 the verdict came from scanning the log for `assert`, so the
    same TypeError passed with a full traceback and was refused with
    `--tb=short` (52 of 89 evidence refusals on 2026-09-23). Both forms must
    now read the same.
    """
    builder = _pytest_product(tmp_path, repo_root, "CHG-140")
    (tmp_path / "tests" / "test_penalty.py").write_text(
        "import sys\n"
        "sys.path.insert(0, 'src')\n"
        "from limiter import Limiter\n"
        "\n"
        "def test_penalty_seconds_is_accepted():\n"
        "    limiter = Limiter(penalty_seconds=10.0)\n"
        "    assert limiter is not None\n",
        encoding="utf-8",
    )

    for flags in ([], ["--tb=short", "-q"]):
        outcome = run_evidence(
            builder.change_dir,
            phase="red",
            task="TASK-001",
            argv=[sys.executable, "-m", "pytest", "tests/test_penalty.py", *flags],
            changed_paths=["tests/test_penalty.py"],
        )
        # A TypeError from the product is a test that ran and did not pass.
        assert outcome.authentic, (flags, outcome.errors, outcome.payload.get("summary"))
        tests = outcome.payload["tests"]
        assert tests["source"] == "junitxml"
        assert any("test_penalty_seconds_is_accepted" in name for name in tests["failed"])
        assert tests["not_run"] == []


def test_a_test_that_cannot_run_is_not_red(tmp_path: Path, repo_root: Path):
    builder = _pytest_product(tmp_path, repo_root, "CHG-141")
    (tmp_path / "tests" / "test_broken.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.fixture\n"
        "def clock():\n"
        "    raise RuntimeError('fixture is broken')\n"
        "\n"
        "def test_needs_clock(clock):\n"
        "    assert clock\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir,
        phase="red",
        task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_broken.py"],
        changed_paths=["tests/test_broken.py"],
    )
    assert not outcome.authentic
    assert any("could not run" in e for e in outcome.errors), outcome.errors
    assert outcome.payload["tests"]["not_run"]


def test_green_must_pass_the_tests_red_listed(tmp_path: Path, repo_root: Path):
    builder = _pytest_product(tmp_path, repo_root, "CHG-142")
    (tmp_path / "tests" / "test_penalty.py").write_text(
        "import sys\n"
        "sys.path.insert(0, 'src')\n"
        "from limiter import Limiter\n"
        "\n"
        "def test_penalty_seconds_is_accepted():\n"
        "    assert Limiter(penalty_seconds=10.0) is not None\n",
        encoding="utf-8",
    )
    red = run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_penalty.py"],
        changed_paths=["tests/test_penalty.py"],
    )
    assert red.authentic

    # Green on a different test does not close the task.
    (tmp_path / "tests" / "test_other.py").write_text(
        "def test_unrelated():\n    assert True\n", encoding="utf-8"
    )
    green = run_evidence(
        builder.change_dir, phase="green", task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_other.py"],
        changed_paths=["tests/test_other.py"],
    )
    assert any("did not turn the Red tests green" in e for e in green.errors), green.errors

    # The same test, once the product implements it, does.
    (tmp_path / "src" / "limiter.py").write_text(
        "class Limiter:\n    def __init__(self, penalty_seconds=0.0):\n"
        "        self.penalty_seconds = penalty_seconds\n",
        encoding="utf-8",
    )
    green = run_evidence(
        builder.change_dir, phase="green", task="TASK-001",
        argv=[sys.executable, "-m", "pytest", "tests/test_penalty.py"],
        changed_paths=["src/limiter.py"],
    )
    assert not [e for e in green.errors if "did not turn the Red tests green" in e], green.errors
