"""Audit 2026-11, FL-9: the declaring snapshot is the product before Implement, also after a rewind.

After a gap reopen the Core walks the `declaring` gate again, and it took a second snapshot of
the tasks' product files - by then the implemented code. A task blocked and reopened after that
was "put back as the declaring gate found it": nothing was restored, and the corrected oracle
passed on the code it was meant to drive.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from deltafuse.core.decide import apply_decision
from deltafuse.core.installer import install
from deltafuse.core.task_snapshot import declaring_snapshot
from deltafuse.core.transitions import advance_change, load_receipts, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt

BEFORE = "def limit():\n    return None\n"
AFTER = "def limit():\n    return 10\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _implemented_then_reopened_from_a_gap(tmp_path: Path, repo_root: Path, cid: str, tasks=None) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    code = tmp_path / "src" / "core.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_bytes(BEFORE.encode())
    builder = MockChangeBuilder(tmp_path, change_id=cid, title="Snap").step_intake().step_analyze().step_specify()
    builder.step_decompose(tasks=tasks).step_declare()
    change = builder.change_dir
    advance_change(change, "declaring")  # the Core's own gate: it copies src/core.py as it is
    assert declaring_snapshot(tmp_path, cid)["src/core.py"] == _sha(BEFORE)

    code.write_bytes(AFTER.encode())
    forge, builder._core_advance = builder._core_advance, lambda gate: None
    builder.step_implement()
    builder._core_advance = forge
    advance_change(change, "implemented")

    (change / "verification.md").write_text("# V\n\n- Outcome: spec-gap\n", encoding="utf-8")
    apply_decision(change, status="reopened", gap="spec-gap", note="a row is missing")
    advance_change(change, "analyzed")
    set_artifact_status(change, status="specified", slice_id="SLICE-01")
    set_artifact_status(change, status="specification-proposed", change_status=True)
    assert apply_decision(change, status="accepted", spec=True)["change_status"] == "declared"
    walked = [r for r in load_receipts(tmp_path, cid) if r.get("kind") == "transition" and r.get("gate") == "declaring"]
    assert len(walked) == 2  # the declaring gate was passed a second time
    return change


def test_the_second_declaring_gate_keeps_the_first_snapshot(tmp_path: Path, repo_root: Path):
    change = _implemented_then_reopened_from_a_gap(tmp_path, repo_root, "CHG-810")
    assert declaring_snapshot(tmp_path, "CHG-810")["src/core.py"] == _sha(BEFORE)

    # Implement again; the oracle proves wrong, the task is blocked, the human reopens it.
    record_green_attempt(change, "TASK-001")
    set_artifact_status(change, status="blocked", task_id="TASK-001")
    result = apply_decision(change, status="reopened", task="TASK-001", note="oracle wrong")
    assert "src/core.py" in result["written"]
    assert (tmp_path / "src" / "core.py").read_bytes() == BEFORE.encode()


def test_a_file_a_task_gained_after_the_first_gate_is_snapshotted_as_it_is(tmp_path: Path, repo_root: Path):
    """The other side of "keep the first": a path the first gate never saw has no earlier copy,
    so the second gate takes it."""
    tasks = [{"id": "TASK-001", "slice": "SLICE-01", "depends_on": [], "allowed_paths": ["src/core.py"]}]
    install(target_dir=tmp_path, framework_root=repo_root)
    code = tmp_path / "src" / "core.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_bytes(BEFORE.encode())
    builder = MockChangeBuilder(tmp_path, change_id="CHG-811", title="Snap").step_intake().step_analyze().step_specify()
    builder.step_decompose(tasks=tasks).step_declare()
    advance_change(builder.change_dir, "declaring")

    from deltafuse.core.task_snapshot import record_declaring_snapshot

    extra = tmp_path / "src" / "extra.py"
    extra.write_bytes(b"X = 1\n")
    task = builder.change_dir / "tasks" / "TASK-001.md"
    task.write_text(task.read_text(encoding="utf-8").replace("- src/core.py\n", "- src/core.py\n- src/extra.py\n"), encoding="utf-8")
    code.write_bytes(AFTER.encode())
    snapshot = record_declaring_snapshot(tmp_path, builder.change_dir, "CHG-811")
    assert snapshot == {"src/core.py": _sha(BEFORE), "src/extra.py": _sha("X = 1\n")}
