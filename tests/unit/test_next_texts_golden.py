"""What `deltafuse next` tells the Worker and the human, pinned word for word.

Codebase audit 2026-10-21: many reasons and halt texts in core/queue.py had no test ("Every task
is declared", "predates later", every halt prompt), so simplifying the queue could change what
the model reads without any test noticing. This test records `next --json` and `next --human` for
the usual states of a Change and compares them with tests/golden/next_texts.json.

A deliberate change of wording: run with DELTAFUSE_UPDATE_GOLDEN=1, then review the diff of the
golden file - that diff is the change in what the Worker reads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from deltafuse.cli import main
from deltafuse.core.installer import install
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder, record_green_attempt
from tests.unit.test_queue import _write_proposed_dec

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "next_texts.json"


def _builder(root: Path, cid: str) -> MockChangeBuilder:
    return MockChangeBuilder(root, change_id=cid, title="Golden")


def _empty(root: Path) -> None:
    return None


def _intake_done(root: Path) -> None:
    _builder(root, "CHG-301").step_intake()


def _analyze_done(root: Path) -> None:
    _builder(root, "CHG-302").step_intake().step_analyze()


def _analyzed(root: Path) -> None:
    _builder(root, "CHG-303").step_intake().step_analyze()._core_advance("analyzed")


def _spec_proposed(root: Path) -> None:
    builder = _builder(root, "CHG-304").step_intake().step_analyze()
    builder._core_advance("analyzed")
    builder._update_change_yaml({"status": "specification-proposed"})


def _decision(root: Path) -> None:
    builder = _builder(root, "CHG-305").step_intake()
    builder._update_change_yaml({"status": "blocked-on-decision"})
    _write_proposed_dec(root, "CHG-305", title="Pick a store")


def _specified(root: Path) -> None:
    _builder(root, "CHG-306").step_intake().step_analyze().step_specify()


def _decomposed(root: Path) -> None:
    _builder(root, "CHG-307").step_intake().step_analyze().step_specify().step_decompose()


def _declared(root: Path) -> None:
    _builder(root, "CHG-308").step_intake().step_analyze().step_specify().step_decompose().step_declare()


def _implemented(root: Path) -> None:
    (
        _builder(root, "CHG-309").step_intake().step_analyze().step_specify().step_decompose()
        .step_declare().step_implement()
    )


def _verified(root: Path) -> None:
    (
        _builder(root, "CHG-310").step_intake().step_analyze().step_specify().step_decompose()
        .step_declare().step_implement().step_verify()
    )


def _blocked(root: Path) -> None:
    builder = _builder(root, "CHG-311").step_intake().step_analyze().step_specify().step_decompose()
    record_green_attempt(builder.change_dir, "TASK-001")
    set_artifact_status(builder.change_dir, status="blocked", task_id="TASK-001")


def _gap(root: Path) -> None:
    builder = (
        _builder(root, "CHG-312").step_intake().step_analyze().step_specify().step_decompose()
        .step_declare().step_implement()
    )
    (builder.change_dir / "verification.md").write_text(
        "# Verification\n\n- Outcome: spec-gap\n\nThe catalogue row is missing.\n", encoding="utf-8"
    )


def _no_route_gap(root: Path) -> None:
    builder = (
        _builder(root, "CHG-313").step_intake().step_analyze().step_specify().step_decompose()
        .step_declare().step_implement()
    )
    (builder.change_dir / "verification.md").write_text(
        "# Verification\n\n- Outcome: test-gap\n\nA claim has no test.\n", encoding="utf-8"
    )


SCENARIOS: dict[str, Callable[[Path], None]] = {
    "empty": _empty,
    "intake-done": _intake_done,
    "analyze-done": _analyze_done,
    "analyzed": _analyzed,
    "spec-proposed": _spec_proposed,
    "decision": _decision,
    "specified": _specified,
    "decomposed": _decomposed,
    "declared": _declared,
    "implemented": _implemented,
    "verified": _verified,
    "blocked-task": _blocked,
    "spec-gap": _gap,
    "gap-without-route": _no_route_gap,
}


def _normalize(value: object, root: Path) -> object:
    """The temporary product root as `<root>`, and `/` for every path separator."""
    if isinstance(value, dict):
        return {k: _normalize(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v, root) for v in value]
    if not isinstance(value, str):
        return value
    for form in (str(root), root.as_posix()):
        value = value.replace(form, "<root>")
    return value.replace("\\", "/")


def _texts(root: Path, capsys) -> dict[str, object]:
    out: dict[str, object] = {}
    for mode in ("--json", "--human"):
        ret = main(["next", str(root), mode])
        text, _ = capsys.readouterr()
        body = json.loads(text) if mode == "--json" else text.splitlines()
        out[mode.lstrip("-")] = {"exit": ret, "out": _normalize(body, root)}
    return out


def test_next_texts_match_the_golden_file(tmp_path: Path, repo_root: Path, capsys):
    got: dict[str, object] = {}
    for name, build in SCENARIOS.items():
        root = tmp_path / name
        root.mkdir()
        install(target_dir=root, framework_root=repo_root)
        build(root)
        got[name] = _texts(root, capsys)
    if os.environ.get("DELTAFUSE_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(got, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    assert GOLDEN.is_file(), f"{GOLDEN} is missing; create it with DELTAFUSE_UPDATE_GOLDEN=1"
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for name in SCENARIOS:
        assert got[name] == want.get(name), f"`deltafuse next` changed for state '{name}' - see the module docstring"
