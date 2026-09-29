"""F4 follow-up: the Red oracle is frozen per failed test, not per file.

The first freeze hashed the whole test file Red declared, so any edit of that
file read as a rewritten oracle - including the regression test Implement is
told it may add, and the second task's Red written into the same file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from deltafuse.core.evidence import run_evidence
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

HEADER = (
    "import sys\n"
    "sys.path.insert(0, 'src')\n"
    "from limiter import cooldown\n"
)

RED_TEST = (
    "\n\ndef test_cooldown_is_at_least_thirty():\n"
    "    assert cooldown() >= 30\n"
)


def _pytest(*targets: str) -> list[str]:
    return [sys.executable, "-m", "pytest", *targets]


def _product(tmp_path: Path, repo_root: Path, change_id: str, tasks: list[str]) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id=change_id, title="Frozen oracle")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose([{"id": t, "slice": "SLICE-01", "depends_on": []} for t in tasks])
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "limiter.py").write_text(
        "def cooldown():\n    return 0\n\n\ndef burst():\n    return 0\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir(exist_ok=True)
    return builder


def _frozen(errors: list[str]) -> list[str]:
    return [e for e in errors if "frozen Red oracle" in e]


def _fix_product(tmp_path: Path) -> None:
    (tmp_path / "src" / "limiter.py").write_text(
        "def cooldown():\n    return 30\n\n\ndef burst():\n    return 5\n", encoding="utf-8"
    )


def test_a_regression_test_added_to_the_red_file_is_not_an_oracle_rewrite(
    tmp_path: Path, repo_root: Path
):
    builder = _product(tmp_path, repo_root, "CHG-160", ["TASK-001"])
    test_file = tmp_path / "tests" / "test_limiter.py"
    test_file.write_text(HEADER + RED_TEST, encoding="utf-8")
    red = run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=_pytest("tests/test_limiter.py"), changed_paths=["tests/test_limiter.py"],
    )
    assert red.authentic, red.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")

    # Implement: fix the product and add the regression test the skill allows.
    _fix_product(tmp_path)
    test_file.write_text(
        HEADER + RED_TEST
        + "\n\ndef test_cooldown_is_not_absurd():\n    assert cooldown() < 3600\n",
        encoding="utf-8",
    )
    green = run_evidence(
        builder.change_dir, phase="green", task="TASK-001",
        argv=_pytest("tests/test_limiter.py"),
        changed_paths=["tests/test_limiter.py", "src/limiter.py"],
    )
    assert green.authentic, green.errors
    assert _frozen(green.errors) == []

    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    assert _frozen(check_gate(builder.change_dir, "implemented")) == []


def test_two_tasks_declaring_into_one_test_file_do_not_freeze_each_other(
    tmp_path: Path, repo_root: Path
):
    builder = _product(tmp_path, repo_root, "CHG-161", ["TASK-001", "TASK-002"])
    test_file = tmp_path / "tests" / "test_limiter.py"

    test_file.write_text(HEADER + RED_TEST, encoding="utf-8")
    red1 = run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=_pytest("tests/test_limiter.py::test_cooldown_is_at_least_thirty"),
        changed_paths=["tests/test_limiter.py"],
    )
    assert red1.authentic, red1.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")

    # The second task's Declare writes its Red into the same file.
    test_file.write_text(
        HEADER.replace("import cooldown", "import burst, cooldown") + RED_TEST
        + "\n\ndef test_burst_is_five():\n    assert burst() == 5\n",
        encoding="utf-8",
    )
    red2 = run_evidence(
        builder.change_dir, phase="red", task="TASK-002",
        argv=_pytest("tests/test_limiter.py::test_burst_is_five"),
        changed_paths=["tests/test_limiter.py"],
    )
    assert red2.authentic, red2.errors
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-002")
    builder._core_advance("declaring")

    _fix_product(tmp_path)
    for task, target in (
        ("TASK-001", "tests/test_limiter.py::test_cooldown_is_at_least_thirty"),
        ("TASK-002", "tests/test_limiter.py::test_burst_is_five"),
    ):
        green = run_evidence(
            builder.change_dir, phase="green", task=task,
            argv=_pytest(target), changed_paths=["tests/test_limiter.py", "src/limiter.py"],
        )
        assert green.authentic, (task, green.errors)
        set_artifact_status(builder.change_dir, status="implemented", task_id=task)
    assert _frozen(check_gate(builder.change_dir, "implemented")) == []


def test_weakening_the_frozen_test_is_still_refused_and_names_it(tmp_path: Path, repo_root: Path):
    builder = _product(tmp_path, repo_root, "CHG-162", ["TASK-001"])
    test_file = tmp_path / "tests" / "test_limiter.py"
    test_file.write_text(HEADER + RED_TEST, encoding="utf-8")
    red = run_evidence(
        builder.change_dir, phase="red", task="TASK-001",
        argv=_pytest("tests/test_limiter.py"), changed_paths=["tests/test_limiter.py"],
    )
    assert red.authentic, red.errors
    assert "red_oracle" not in red.payload
    assert [t["test"] for t in red.payload["red_oracle_tests"]["tests"]] == [
        "test_cooldown_is_at_least_thirty"
    ]
    set_artifact_status(builder.change_dir, status="declared", task_id="TASK-001")
    builder._core_advance("declaring")

    test_file.write_text((HEADER + RED_TEST).replace(">= 30", ">= 0"), encoding="utf-8")
    green = run_evidence(
        builder.change_dir, phase="green", task="TASK-001",
        argv=_pytest("tests/test_limiter.py"), changed_paths=["tests/test_limiter.py"],
    )
    assert not green.authentic
    named = "tests/test_limiter.py::test_cooldown_is_at_least_thirty changed"
    assert any("frozen Red oracle" in e and named in e for e in green.errors), green.errors

    set_artifact_status(builder.change_dir, status="implemented", task_id="TASK-001")
    errs = _frozen(check_gate(builder.change_dir, "implemented"))
    assert errs and named in errs[0], errs
