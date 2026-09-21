"""E2E: a Change from decomposed to converged, moved only by the Core.

The golden workflow closes declaring, implemented and converged through the
change builder, which appends receipts without the Core's checks. That is how
the dead ends q0 single runs found stayed hidden: `advance` could not close a
gate from the resting status, the gates asked for one task of many, and the
queue picked steps from task statuses alone. Here every status after
decomposed is moved by `deltafuse state` or `deltafuse advance`, every
evidence file is written by the evidence runner, and the queue is asked what
comes next at each point - the path a Worker walks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next
from deltafuse.core.transitions import advance_change, receipt_chain_errors, set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

TASKS = ("TASK-001", "TASK-002")


def _next(product: Path):
    return select_next(build_work_queue(product))


def _oracle(product: Path, task_id: str) -> str:
    """A public oracle: the task's feature flag in src/core.py."""
    name = task_id.lower().replace("-", "_")
    test = product / "tests" / f"test_{name}.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    flag = f"FEATURE_{task_id[-3:]} = True"
    test.write_text(
        "from pathlib import Path\n"
        f"assert {flag!r} in Path('src/core.py').read_text(encoding='utf-8'), "
        f"'{task_id} not implemented'\n",
        encoding="utf-8",
    )
    return test.relative_to(product).as_posix()


def _implement(product: Path, task_id: str) -> None:
    core = product / "src" / "core.py"
    core.parent.mkdir(parents=True, exist_ok=True)
    before = core.read_text(encoding="utf-8") if core.is_file() else ""
    core.write_text(before + f"FEATURE_{task_id[-3:]} = True\n", encoding="utf-8")


def test_change_reaches_converged_through_core_commands_only(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-990", title="Core only")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose(
            tasks=[
                {"id": "TASK-001", "slice": "SLICE-01", "depends_on": []},
                {"id": "TASK-002", "slice": "SLICE-01", "depends_on": ["TASK-001"]},
            ]
        )
    )
    change = builder.change_dir
    oracles = {task_id: _oracle(tmp_path, task_id) for task_id in TASKS}

    # Declare: each task gets its Red oracle, then the gate closes from decomposed.
    for task_id in TASKS:
        selected = _next(tmp_path)
        assert (selected.skill, selected.task) == ("declare", task_id)
        red = run_evidence(
            change,
            phase="red",
            task=task_id,
            argv=[sys.executable, oracles[task_id]],
            changed_paths=[oracles[task_id]],
        )
        assert red.authentic, red.payload
        set_artifact_status(change, status="declared", task_id=task_id)
    selected = _next(tmp_path)
    assert selected.skill == "declare" and "close the declaring gate" in selected.reason
    assert check_gate(change, "declaring") == []
    assert advance_change(change, "declaring")["to"] == "declared"

    # Implement: Green and Regression per task, then the gate closes from declared.
    for task_id in TASKS:
        selected = _next(tmp_path)
        assert (selected.skill, selected.task) == ("implement", task_id)
        _implement(tmp_path, task_id)
        for phase in ("green", "regression"):
            outcome = run_evidence(
                change,
                phase=phase,
                task=task_id,
                argv=[sys.executable, oracles[task_id]],
                changed_paths=["src/core.py"],
            )
            assert outcome.payload["result"] == "passed", outcome.payload
        set_artifact_status(change, status="implemented", task_id=task_id)

    # TASK-002 moved src/**, so TASK-001's evidence no longer proves its oracle on
    # the code the gate closes over: the queue sends the Worker to re-run it.
    selected = _next(tmp_path)
    assert (selected.skill, selected.task) == ("implement", "TASK-001")
    assert "re-run it on the current tree" in selected.reason
    assert any("re-run it on the current tree" in e for e in check_gate(change, "implemented"))
    for phase in ("green", "regression"):
        run_evidence(
            change,
            phase=phase,
            task="TASK-001",
            argv=[sys.executable, oracles["TASK-001"]],
            changed_paths=["src/core.py"],
        )
    selected = _next(tmp_path)
    assert selected.skill == "implement" and "close the implemented gate" in selected.reason
    assert check_gate(change, "implemented") == []
    assert advance_change(change, "implemented")["to"] == "implemented"

    # Verify: the Worker writes the report and maps the evidence, the Core closes.
    assert _next(tmp_path).skill == "verify"
    (change / "verification.md").write_text("# Verification\nBoth claims verified.\n", encoding="utf-8")
    run_evidence(change, phase="verification", task=None, argv=[sys.executable, oracles["TASK-002"]])
    coverage_file = change / "coverage.yaml"
    coverage = yaml.safe_load(coverage_file.read_text(encoding="utf-8"))
    for claim in coverage["claims"].values():
        claim.setdefault("evidence", {}).update(
            {"green": "evidence/green/TASK-001.yaml", "regression": "evidence/regression/TASK-001.yaml"}
        )
    coverage_file.write_text(yaml.safe_dump(coverage, sort_keys=False), encoding="utf-8")
    assert check_gate(change, "converged") == []
    assert advance_change(change, "converged")["to"] == "converged"

    assert receipt_chain_errors(tmp_path, change) == []
    remaining = _next(tmp_path)
    assert remaining is None or remaining.change_id != "CHG-990"
