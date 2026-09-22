"""E2E: the Worker's path after roadmap item 1, from intake to declare.

Every structural artifact is written by `deltafuse artifact write`, every status
by the Core, and after each step the leash judges the diff since the last
commit - exactly what the qualification runner does between Worker steps. The
builder fixture writes frontmatter by hand and skips real gates; this walk does
neither, so a dead end on the Writer path shows here before a paid run.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.installer import install
from deltafuse.core.queue import build_work_queue, select_next

CHANGE = "CHG-701-writer-walk"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=walk@test", "-c", "user.name=walk", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    )


def _cli(capsys, *argv: str) -> str:
    code = main(list(argv))
    out, err = capsys.readouterr()
    assert code == 0, f"deltafuse {' '.join(argv)} exited {code}:\n{out}\n{err}"
    return out


def _step_done(root: Path, capsys, label: str) -> None:
    """The runner's check between steps: leash on the step's diff, then commit."""
    code = main(["leash", str(root), "--json"])
    out, err = capsys.readouterr()
    data = json.loads(out if out.strip() else err)
    assert data["violations"] == [], f"{label}: {data['violations']}"
    assert code == 0, label
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", label)


def _write(capsys, tmp: Path, change: Path, kind: str, envelope: dict) -> None:
    source = tmp / f"{kind}.json"
    source.write_text(json.dumps(envelope), encoding="utf-8")
    _cli(capsys, "artifact", "write", "--kind", kind, "--change", str(change), "--input", str(source))


def _selected(root: Path):
    return select_next(build_work_queue(root))


def test_the_writer_path_reaches_declare_with_a_clean_leash(tmp_path: Path, repo_root: Path, capsys):
    root = tmp_path / "product"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    install(target_dir=root, framework_root=repo_root)
    (root / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec" / "core.md").write_text("# Core\n\n## REQ-01\n\nThe system MUST start.\n", encoding="utf-8")
    (root / "docs" / "spec" / "_capabilities.yaml").write_text(yaml.safe_dump({
        "schema_version": 3,
        "domains": {"system": {"summary": "Core system", "capabilities": {
            "core": {"summary": "Core capability", "spec": ["docs/spec/core.md"], "code_roots": ["src"]},
        }}},
    }, sort_keys=False), encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "baseline")
    change = root / "docs" / "changes" / CHANGE

    # Intake: the Core scaffolds, the Worker writes the request's prose.
    _cli(capsys, "new", str(root), CHANGE, "--title", "Writer walk")
    request = change / "request.md"
    request.write_text(
        request.read_text(encoding="utf-8")
        + "\nStart the system with a banner.\n\n## Provenance\n\nTest.\n\n## Claims\n\n"
        "- CR-001 (expectation): the system prints a banner on start.\n",
        encoding="utf-8",
    )
    _cli(capsys, "check-gate", str(change), "--gate", "intake")
    _cli(capsys, "advance", str(change), "--gate", "intake")
    _step_done(root, capsys, "intake")

    # Analyze: routing, one slice, coverage by the Core.
    assert _selected(root).skill == "analyze"
    _write(capsys, inputs, change, "routing", {"identity": "routing", "fields": {"route": "code", "claims": {
        "CR-001": {"summary": "Banner on start", "primary_capability": "system.core",
                   "related_capabilities": [], "policies": [], "confidence": "high"},
    }}})
    _step_done(root, capsys, "analyze routing")
    _write(capsys, inputs, change, "slice", {"identity": "SLICE-01", "fields": {
        "title": "Banner", "primary_capability": "system.core", "claims": ["CR-001"],
        "spec_refs": ["docs/spec/core.md"],
    }, "body": "Print a banner on start. Unchanged: start-up itself."})
    _step_done(root, capsys, "analyze slice")
    _cli(capsys, "coverage", str(change))
    _cli(capsys, "check-gate", str(change), "--gate", "analyzed")
    _cli(capsys, "advance", str(change), "--gate", "analyzed")
    _step_done(root, capsys, "analyze coverage")

    # Specify: live spec, the slice's delta, the Core's statuses, the human's click.
    assert _selected(root).skill == "specify"
    spec = root / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## REQ-02\n\nWHEN the system starts THE SYSTEM SHALL print a banner.\n", encoding="utf-8")
    _write(capsys, inputs, change, "spec-delta", {"identity": "spec-delta", "fields": {
        "slices": ["SLICE-01"], "added": ["docs/spec/core.md#REQ-02"], "modified": [], "removed": [],
    }, "body": "## SLICE-01\n\nAdds REQ-02: a banner on start."})
    _cli(capsys, "state", str(change), "--slice", "SLICE-01", "--status", "specified")
    _step_done(root, capsys, "specify slice")
    _cli(capsys, "state", str(change), "--change", "--status", "specification-proposed")
    _step_done(root, capsys, "specify close")
    _cli(capsys, "decide", str(change), "--spec", "--status", "accepted")
    _step_done(root, capsys, "human gate")

    # Decompose: one task through the Writer, the gate closed by the Core.
    assert _selected(root).skill == "decompose"
    _write(capsys, inputs, change, "task", {"identity": "TASK-001", "fields": {
        "slice": "SLICE-01", "title": "Print the banner", "kind": "feature", "depends_on": [],
        "requirement_delta": "added", "spec_refs": ["docs/spec/core.md#REQ-02"], "design_ref": None,
        "allowed_paths": ["src/app.py", "tests/test_banner.py"], "forbidden_paths": [],
    }, "body": "Print the banner. Oracle: tests/test_banner.py."})
    _cli(capsys, "check-gate", str(change), "--gate", "decomposed")
    _cli(capsys, "advance", str(change), "--gate", "decomposed")
    _step_done(root, capsys, "decompose")

    selected = _selected(root)
    assert (selected.skill, selected.task) == ("declare", "TASK-001")
