"""A real product walked through the lifecycle by the CLI, for leash and Writer tests.

The second audit (2026-11-17, df-leash) reproduced every finding on a product built by the real
commands in a real git repository: the Writer writes the structure, the Core the statuses, and
each step is committed. `walk` builds it once per test session and keeps a copy of the tree at
each stage; a test takes its own copy with `product_at`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core.installer import install

CHANGE = "CHG-701-writer-walk"
STAGES = ("init", "intake", "analyzed", "specified", "decomposed", "declared", "implemented", "converged")
ORACLE = (
    "from pathlib import Path\n"
    "assert 'BANNER' in Path('src/app.py').read_text(encoding='utf-8') "
    "if Path('src/app.py').is_file() else False, 'no banner'\n"
)
TASK_FIELDS = {
    "slice": "SLICE-01", "title": "Print the banner", "kind": "feature", "depends_on": [],
    "requirement_delta": "added", "spec_refs": ["docs/spec/core.md#REQ-02"], "design_ref": None,
    "allowed_paths": ["src/app.py", "tests/test_banner.py"], "forbidden_paths": [],
}
REPO_ROOT = Path(__file__).resolve().parents[2]
_WALK: Path | None = None


def env() -> dict[str, str]:
    out = dict(os.environ)
    out["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT)])
    out["DELTAFUSE_PYTHON"] = Path(sys.executable).as_posix()
    out["GIT_AUTHOR_NAME"] = out["GIT_COMMITTER_NAME"] = "w"
    out["GIT_AUTHOR_EMAIL"] = out["GIT_COMMITTER_EMAIL"] = "w@x"
    out.pop("DELTAFUSE_LEASH_INDEX", None)
    return out


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env())
    if check and proc.returncode != 0:
        raise AssertionError(f"git {args}: {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    return proc


def cli(*argv: str, check: bool = True) -> tuple[int, str]:
    """`deltafuse <argv>` in this process; (exit code, stdout + stderr)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = main([str(a) for a in argv])
        except SystemExit as ex:  # argparse
            code = int(ex.code or 0)
    if check and code != 0:
        raise AssertionError(f"deltafuse {' '.join(map(str, argv))} exited {code}:\n{out.getvalue()}")
    return code, out.getvalue()


def write(root: Path, kind: str, envelope: dict, *, change: Path | None = None, check: bool = True) -> tuple[int, str]:
    tmp = root / ".deltafuse" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    source = tmp / f"{kind}.json"
    source.write_text(json.dumps(envelope), encoding="utf-8")
    return cli("artifact", "write", "--kind", kind, "--change", change or root / "docs" / "changes" / CHANGE,
               "--input", source, "--json", check=check)


def leash(root: Path, *args: str) -> tuple[int, dict]:
    code, out = cli("leash", root, "--json", *args, check=False)
    try:
        return code, json.loads(out[out.index("{"):out.rindex("}") + 1])
    except ValueError:
        return code, {"raw": out}


def commit(root: Path, label: str, *, verify: bool = False) -> subprocess.CompletedProcess:
    """`git add -A` and commit; with ``verify`` the pre-commit hook judges it (no exception on refusal)."""
    git(root, "add", "-A")
    args = ["commit", "-q", "--allow-empty", "-m", label] + ([] if verify else ["--no-verify"])
    return git(root, *args, check=not verify)


def put(root: Path, rel: str, text: str = "x = 1\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def set_workflow(root: Path, **values) -> None:
    cfg = root / ".deltafuse" / "config.yaml"
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    for key, value in values.items():
        if value is None:
            data["workflow"].pop(key, None)
        else:
            data["workflow"][key] = value
    cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def rmtree(path: Path) -> None:
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if Path(path).exists():
        shutil.rmtree(path, onerror=onerror)


def build(root: Path, snapshots: Path | None = None) -> None:
    """Walk CHG-701 from init to converged in ``root``; copy the tree to ``snapshots/<stage>`` at each stage."""
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "core.autocrlf", "false")
    install(target_dir=root, framework_root=REPO_ROOT)
    set_workflow(root, leash="enforce")
    install(target_dir=root, framework_root=REPO_ROOT)  # the hook, now that the mode is enforce
    put(root, "docs/spec/core.md", "# Core\n\n## REQ-01\n\nThe system MUST start.\n")
    put(root, "docs/spec/_capabilities.yaml", yaml.safe_dump({
        "schema_version": 3,
        "domains": {"system": {"summary": "Core system", "capabilities": {
            "core": {"summary": "Core capability", "spec": ["docs/spec/core.md"], "code_roots": ["src"]},
        }}},
    }, sort_keys=False))
    put(root, "src/existing.py", "X = 1\n")
    gitignore = root / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "__pycache__/\n*.pyc\n.pytest_cache/\n",
                         encoding="utf-8", newline="\n")
    change = root / "docs" / "changes" / CHANGE
    run = [sys.executable, "tests/test_banner.py"]

    def done(stage: str) -> None:
        commit(root, stage)
        if snapshots is not None:
            shutil.copytree(root, snapshots / stage, symlinks=True)

    done("init")
    cli("new", root, CHANGE, "--title", "Writer walk")
    request = change / "request.md"
    request.write_text(
        request.read_text(encoding="utf-8")
        + "\nStart the system with a banner.\n\n## Provenance\n\nTest.\n\n## Claims\n\n"
        "- CR-001 (expectation): the system prints a banner on start.\n", encoding="utf-8")
    cli("advance", change, "--gate", "intake")
    done("intake")
    write(root, "routing", {"identity": "routing", "fields": {"route": "code", "claims": {
        "CR-001": {"summary": "Banner on start", "primary_capability": "system.core",
                   "related_capabilities": [], "policies": [], "confidence": "high"}}}})
    write(root, "slice", {"identity": "SLICE-01", "fields": {
        "title": "Banner", "primary_capability": "system.core", "claims": ["CR-001"],
        "spec_refs": ["docs/spec/core.md"]}, "body": "Print a banner on start. Unchanged: start-up itself."})
    cli("advance", change, "--gate", "analyzed")
    done("analyzed")
    spec = root / "docs" / "spec" / "core.md"
    spec.write_text(spec.read_text(encoding="utf-8")
                    + "\n## REQ-02\n\nWHEN the system starts THE SYSTEM SHALL print a banner.\n", encoding="utf-8")
    write(root, "spec-delta", {"identity": "spec-delta", "fields": {
        "slices": ["SLICE-01"], "added": ["docs/spec/core.md#REQ-02"], "modified": [], "removed": []},
        "body": "## SLICE-01\n\nAdds REQ-02: a banner on start."})
    cli("state", change, "--slice", "SLICE-01", "--status", "specified")
    cli("state", change, "--change", "--status", "specification-proposed")
    commit(root, "specify close")
    cli("decide", change, "--spec", "--status", "accepted")
    done("specified")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS,
                         "body": "Print the banner. Oracle: tests/test_banner.py."})
    cli("advance", change, "--gate", "decomposed")
    done("decomposed")
    put(root, "tests/test_banner.py", ORACLE)
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    cli("advance", change, "--gate", "declaring")
    done("declared")
    put(root, "src/app.py", "BANNER = 'hello'\n")
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    cli("advance", change, "--gate", "implemented")
    done("implemented")
    put(root, f"docs/changes/{CHANGE}/verification.md", "# Change Verification\n\n- Outcome: `converged`\n")
    cli("evidence", change, "--phase", "verification", "--", *run)
    cli("state", change, "--task", "TASK-001", "--status", "verified")
    cli("advance", change, "--gate", "converged")
    done("converged")


@pytest.fixture(scope="session")
def walk(tmp_path_factory) -> Path:
    """The directory of stage snapshots (``<stage>/`` for each of STAGES)."""
    global _WALK
    if _WALK is None:  # one walk per session, whichever test module asks first
        home = tmp_path_factory.mktemp("leash-walk")
        build(home / "work", home / "stages")
        _WALK = home / "stages"
    return _WALK


@pytest.fixture
def product_at(walk: Path, tmp_path: Path):
    """``product_at(stage)`` -> (product root, Change directory): a private copy of that stage."""
    def take(stage: str, name: str = "p") -> tuple[Path, Path]:
        root = tmp_path / name
        shutil.copytree(walk / stage, root, symlinks=True)
        return root, root / "docs" / "changes" / CHANGE

    return take
