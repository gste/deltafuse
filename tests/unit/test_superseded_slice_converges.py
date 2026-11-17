"""A slice whose only task found its requirement already met can converge.

Audit 2026-11-17 (FE-7): two claims in two slices; CR-001's task takes an already-green Red
(`requirement_delta: none`) and is superseded, as docs/workflow.md tells it to be. A superseded
task has no Green (the Core refuses one), so its claim never had the `green` and `regression`
mapping the `converged` gate asked of every claim: the Change could not converge, and cancelling
the task left "claim has no task". The proof of such a claim is the already-green Red of its
superseded task, whose tests the verification run must pass.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate, coverage_claim_errors
from deltafuse.core.installer import install
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder
from tests.fixtures.evidence_kit import only, pytest_argv, write

HEAD = "import sys\nsys.path.insert(0, 'src')\nimport limiter\n\n\n"
PATHS = ["tests/test_limiter.py", "src/limiter.py"]


def _two_slices(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    b = (MockChangeBuilder(tmp_path, change_id="CHG-910", title="Two slices")
         .step_intake(["CR-001", "CR-002"]).step_analyze(["SLICE-01", "SLICE-02"]))
    for sid, claim in (("SLICE-01", "CR-001"), ("SLICE-02", "CR-002")):
        f = b.change_dir / "slices" / f"{sid}.md"
        f.write_text(f.read_text(encoding="utf-8").replace("claims: [CR-001, CR-002]", f"claims: [{claim}]"), encoding="utf-8")
    b.step_specify().step_decompose([
        {"id": "TASK-001", "slice": "SLICE-01", "depends_on": [], "allowed_paths": ["tests/test_met.py"]},
        {"id": "TASK-002", "slice": "SLICE-02", "depends_on": [], "allowed_paths": ["src/limiter.py", "tests/test_limiter.py"]},
    ])
    t1 = b.change_dir / "tasks" / "TASK-001.md"
    t1.write_text(t1.read_text(encoding="utf-8").replace("requirement_delta: added", "requirement_delta: none"), encoding="utf-8")
    write(tmp_path / "src/limiter.py", "def cooldown():\n    return 0\n\n\ndef burst():\n    return 5\n")
    write(tmp_path / "tests/test_met.py", HEAD + "def test_burst():\n    assert limiter.burst() == 5\n")
    write(tmp_path / "tests/test_limiter.py", HEAD + "def test_cooldown():\n    assert limiter.cooldown() >= 30\n")
    return b


def _implement_task_2(b: MockChangeBuilder, tmp_path: Path) -> None:
    red2 = run_evidence(b.change_dir, phase="red", task="TASK-002", argv=pytest_argv("tests/test_limiter.py"),
                        changed_paths=["tests/test_limiter.py"])
    assert red2.authentic, red2.errors
    set_artifact_status(b.change_dir, status="declared", task_id="TASK-002")
    assert check_gate(b.change_dir, "declaring") == []
    b._core_advance("declaring")
    write(tmp_path / "src/limiter.py", "def cooldown():\n    return 30\n\n\ndef burst():\n    return 5\n")
    green = run_evidence(b.change_dir, phase="green", task="TASK-002", argv=pytest_argv("tests/test_limiter.py"), changed_paths=PATHS)
    reg = run_evidence(b.change_dir, phase="regression", task="TASK-002", argv=pytest_argv(), changed_paths=PATHS)
    assert green.authentic and reg.authentic, (green.errors, reg.errors)
    set_artifact_status(b.change_dir, status="implemented", task_id="TASK-002")
    assert check_gate(b.change_dir, "implemented") == []
    b._core_advance("implemented")


def _supersede_task_1(b: MockChangeBuilder) -> None:
    red1 = run_evidence(b.change_dir, phase="red", task="TASK-001", argv=pytest_argv("tests/test_met.py"),
                        changed_paths=["tests/test_met.py"])
    assert red1.payload["result"] == "already-green"
    set_artifact_status(b.change_dir, status="superseded", task_id="TASK-001")


def test_a_slice_whose_only_task_is_superseded_converges(tmp_path: Path, repo_root: Path):
    b = _two_slices(tmp_path, repo_root)
    _supersede_task_1(b)
    _implement_task_2(b, tmp_path)
    ver = run_evidence(b.change_dir, phase="verification", argv=pytest_argv(), changed_paths=PATHS)
    assert ver.authentic, ver.errors
    write(b.change_dir / "verification.md", "# Verification\n\n- Outcome: `converged`\n")
    assert coverage_claim_errors(b.change_dir, "code") == []
    assert check_gate(b.change_dir, "converged") == []
    coverage = yaml.safe_load((b.change_dir / "coverage.yaml").read_text(encoding="utf-8"))
    if isinstance(coverage, dict) and isinstance(coverage.get("claims"), dict) and "CR-001" in coverage["claims"]:
        assert coverage["claims"]["CR-001"].get("evidence", {}).get("red", "evidence/red/TASK-001.yaml") == "evidence/red/TASK-001.yaml"


def test_the_superseded_tasks_test_must_still_pass_in_verification(tmp_path: Path, repo_root: Path):
    """The bypass: the claim's only proof is that test - a verification that leaves it failing
    (or breaks it afterwards) does not converge."""
    b = _two_slices(tmp_path, repo_root)
    _supersede_task_1(b)
    _implement_task_2(b, tmp_path)
    # Implement broke the behaviour the superseded task's test pins.
    write(tmp_path / "src/limiter.py", "def cooldown():\n    return 30\n\n\ndef burst():\n    return 4\n")
    ver = run_evidence(b.change_dir, phase="verification", argv=pytest_argv(), changed_paths=PATHS)
    assert not ver.authentic
    write(b.change_dir / "verification.md", "# Verification\n\n- Outcome: `converged`\n")
    assert check_gate(b.change_dir, "converged")


def test_a_claim_whose_superseded_task_has_no_already_green_red_is_not_covered(tmp_path: Path, repo_root: Path):
    """The twin: `superseded` written by hand, with no Red (or a failing one) behind it."""
    b = _two_slices(tmp_path, repo_root)
    t1 = b.change_dir / "tasks" / "TASK-001.md"
    t1.write_text(t1.read_text(encoding="utf-8").replace("status: pending", "status: superseded"), encoding="utf-8")
    errors = coverage_claim_errors(b.change_dir, "code")
    assert only(errors, "CR-001"), errors
    assert only(errors, "already-green"), errors


def test_a_claim_with_a_cancelled_only_task_still_has_no_task(tmp_path: Path, repo_root: Path):
    """Cancelling is not meeting the requirement: the human decided the task is not done."""
    b = _two_slices(tmp_path, repo_root)
    t1 = b.change_dir / "tasks" / "TASK-001.md"
    t1.write_text(t1.read_text(encoding="utf-8").replace("status: pending", "status: cancelled"), encoding="utf-8")
    assert only(coverage_claim_errors(b.change_dir, "code"), "claim 'CR-001' has no task")
