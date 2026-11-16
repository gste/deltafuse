"""coverage.yaml is derived from the tasks and their evidence, every time, and the converged gate
checks each claim against the disk.

Audit 2026-11-16 (df-evidence #12, df-gates #3): a claim's `status` was never derived (it stayed
`pending`); `tasks` and `evidence` stuck after the first write - a task added later never
appeared, a cancelled task's evidence kept covering the claim - and "an explicit link wins" let a
hand edit link a claim with no task to another task's evidence, after which the Change converged.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.analyze import build_coverage_document, write_coverage
from deltafuse.core.fsm import coverage_claim_errors
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _two_slices(tmp_path: Path, repo_root: Path, change_id: str) -> MockChangeBuilder:
    """CR-001 in SLICE-01 with TASK-001; CR-002 in SLICE-02, which has no task."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id=change_id, title="Coverage").step_intake(
        claims=["CR-001", "CR-002"]
    ).step_analyze(slices=["SLICE-01", "SLICE-02"])
    for sl, claim in (("SLICE-01", "CR-001"), ("SLICE-02", "CR-002")):
        f = builder.change_dir / "slices" / f"{sl}.md"
        f.write_text(f.read_text(encoding="utf-8").replace("claims: [CR-001, CR-002]", f"claims: [{claim}]"),
                     encoding="utf-8")
    builder.step_specify().step_decompose([{"id": "TASK-001", "slice": "SLICE-01", "depends_on": []}])
    return builder


def _evidence(builder: MockChangeBuilder, task: str) -> None:
    for phase in ("red", "green", "regression"):
        folder = builder.change_dir / "evidence" / phase
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{task}.yaml").write_text("phase: x\n", encoding="utf-8")


def _set_status(builder: MockChangeBuilder, task: str, status: str) -> None:
    f = builder.change_dir / "tasks" / f"{task}.md"
    text = f.read_text(encoding="utf-8")
    current = next(line for line in text.splitlines() if line.startswith("status:"))
    f.write_text(text.replace(current, f"status: {status}", 1), encoding="utf-8")


def test_a_hand_link_does_not_cover_a_claim_without_a_task(tmp_path: Path, repo_root: Path):
    builder = _two_slices(tmp_path, repo_root, "CHG-260")
    _evidence(builder, "TASK-001")
    write_coverage(builder.change_dir)
    cov_file = builder.change_dir / "coverage.yaml"
    cov = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
    cov["claims"]["CR-002"]["evidence"] = {"green": "evidence/green/TASK-001.yaml",
                                          "regression": "evidence/regression/TASK-001.yaml"}
    cov["claims"]["CR-002"]["tasks"] = ["TASK-001"]
    cov_file.write_text(yaml.safe_dump(cov, sort_keys=False), encoding="utf-8")

    derived = build_coverage_document(builder.change_dir)
    assert derived["claims"]["CR-002"]["tasks"] == []
    assert derived["claims"]["CR-002"]["evidence"] == {}
    errors = coverage_claim_errors(builder.change_dir, "code")
    assert any("CR-002" in e and "no task" in e for e in errors), errors
    # The hand-written file itself is checked against the disk the same way.
    errors = coverage_claim_errors(builder.change_dir, "code", document=cov)
    assert any("CR-002" in e and "TASK-001" in e for e in errors), errors


def test_tasks_and_evidence_follow_the_tasks_now(tmp_path: Path, repo_root: Path):
    builder = _two_slices(tmp_path, repo_root, "CHG-261")
    _evidence(builder, "TASK-001")
    write_coverage(builder.change_dir)
    _set_status(builder, "TASK-001", "cancelled")
    t1 = (builder.change_dir / "tasks" / "TASK-001.md").read_text(encoding="utf-8")
    (builder.change_dir / "tasks" / "TASK-002.md").write_text(
        t1.replace("TASK-001", "TASK-002").replace("status: cancelled", "status: pending"), encoding="utf-8"
    )
    claim = build_coverage_document(builder.change_dir)["claims"]["CR-001"]
    assert claim["tasks"] == ["TASK-002"]
    assert "green" not in claim["evidence"]


def test_a_claims_status_is_derived_from_its_tasks(tmp_path: Path, repo_root: Path):
    builder = _two_slices(tmp_path, repo_root, "CHG-262")
    doc = build_coverage_document(builder.change_dir)
    assert doc["claims"]["CR-001"]["status"] == "decomposed"
    assert doc["claims"]["CR-002"]["status"] == "pending"
    _set_status(builder, "TASK-001", "implemented")
    assert build_coverage_document(builder.change_dir)["claims"]["CR-001"]["status"] == "implemented"
