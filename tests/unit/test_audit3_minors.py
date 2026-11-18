"""Round 2 open item 8 (O7), the minors.

- `deltafuse leash` in a repository with no commit exited 2; it is "not judged", exit 0.
- `deltafuse next` in text mode printed no hook warning (only --json and --human did).
- `next` on a converged Change that is not archived did not name `deltafuse archive`.
- The Writer accepted control characters in `allowed_paths` / `forbidden_paths`.
- The ownership record listed root files a task's allowed_paths covers (pom.xml) as unowned.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from deltafuse.cli import main
from deltafuse.core.installer import install
from deltafuse.core.layout import PathRefused, product_path_error, product_relpath
from deltafuse.core.ownership import under_routing
from tests.fixtures.change_builder import MockChangeBuilder
from tests.unit.test_ownership import CHANGE, _product, _touch


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


# --- leash with no commit -----------------------------------------------------------------------

def test_leash_with_no_commit_is_not_judged(tmp_path: Path, repo_root: Path, capsys):
    _git(tmp_path, "init", "-q")
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-351", title="Fresh").step_intake()
    assert main(["leash", str(tmp_path)]) == 0
    out, _ = capsys.readouterr()
    assert "not judged" in out and "git commit" in out
    assert main(["leash", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr()[0])
    assert payload["skipped"] is True and payload["violations"] == []


def test_advance_with_no_commit_still_records_the_leash_unchecked(tmp_path: Path, repo_root: Path):
    """The twin: `advance` keeps saying it could not check (checked: false), not "clean"."""
    from deltafuse.core.leash_run import leash_at_advance

    _git(tmp_path, "init", "-q")
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-352", title="Fresh").step_intake()
    result = leash_at_advance(builder.change_dir, tmp_path)
    assert result is not None and result["checked"] is False and "commit" in result["reason"]


# --- next in text mode prints the hook warning ----------------------------------------------------

def test_text_mode_next_prints_the_hook_warning(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)  # before git: no hook is installed
    _git(tmp_path, "init", "-q")
    MockChangeBuilder(tmp_path, change_id="CHG-353", title="No hook").step_intake()
    main(["next", str(tmp_path)])
    _, err = capsys.readouterr()
    assert "deltafuse: warning:" in err and "hook" in err


# --- next names the archive of a converged Change -------------------------------------------------

def test_next_names_the_archive_of_a_converged_change(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-354", title="Done").step_intake().step_analyze()
    builder.step_specify().step_decompose().step_declare().step_implement().step_verify()
    main(["next", str(tmp_path)])
    out, err = capsys.readouterr()
    rel = builder.change_dir.relative_to(tmp_path).as_posix()
    assert f"deltafuse archive {rel}" in out + err
    main(["next", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr()[0])
    assert any(f"deltafuse archive {rel}" in w for w in payload["warnings"]), payload["warnings"]


# --- control characters in a stored path ----------------------------------------------------------

@pytest.mark.parametrize("raw", ["src/a\x1b[31m.py", "src/a\tb.py", "src/\x00x.py", "src/a\x7f.py", "src/a\u0085b.py"])
def test_a_stored_path_with_a_control_character_is_refused(raw: str):
    assert product_path_error(raw) is not None
    with pytest.raises(PathRefused, match="control character"):
        product_relpath(raw, resolve=True)


def test_the_writer_refuses_a_task_path_with_a_control_character(tmp_path: Path, repo_root: Path):
    """The twin path: the Writer, which stores the task's allowed_paths."""
    from deltafuse.core.artifacts import ArtifactServiceError, _check_task_paths

    with pytest.raises(ArtifactServiceError, match="control character"):
        _check_task_paths({"allowed_paths": ["src/app.py"], "forbidden_paths": ["src/\x1b.py"]})


# --- ownership of a root file a task declared ------------------------------------------------------

def test_a_root_file_a_task_declares_is_not_unowned(tmp_path: Path):
    root = _product(tmp_path, {"app.limits": ["src/limits"]}, {"app.limits": []})
    tasks = root / CHANGE / "tasks"
    tasks.mkdir()
    (tasks / "TASK-001.md").write_text(
        "---\nid: TASK-001\nstatus: implemented\nallowed_paths: [pom.xml, src/limits/**]\n---\n", encoding="utf-8"
    )
    (tasks / "TASK-002.md").write_text(
        "---\nid: TASK-002\nstatus: cancelled\nallowed_paths: [README.md]\n---\n", encoding="utf-8"
    )
    _touch(root, "pom.xml")
    _touch(root, "README.md")
    record = under_routing(root, root / CHANGE)
    assert record["unowned"] == ["README.md"]  # a cancelled task declares nothing
    assert record["declared"] == ["pom.xml"]
