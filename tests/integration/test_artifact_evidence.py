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
