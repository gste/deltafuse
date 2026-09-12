"""Durable wheel build evidence (QF-010).

This is an explicit, maintainer-run command — tests never call it with a
repository output directory:

    python scripts/wheel_evidence.py --output-dir bench/builds [--force]

Pipeline: clean-tree guard -> `pip wheel --no-deps` -> wheel smoke in a clean
temp venv (CLI / init / validate-config, same checks as the wheel smoke
test) -> schema-validated, atomically written
`<output-dir>/<wheel-stem>-build-manifest.json` with reproducible provenance
(commit, tree_clean, wheel sha256, build frontend/backend, python/platform,
UTC timestamp, exact commands with return codes). An existing evidence file
is never silently overwritten without --force.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import venv
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schemas" / "wheel-evidence.schema.json"
SCHEMA_VERSION = 1


def tree_dirty(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(repo)
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=900, **kwargs)


def _validate(evidence: dict) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(evidence)


def _expected_stem(repo: Path) -> str:
    """Wheel stem is predictable from the version, so an existing evidence
    file is detected BEFORE the (expensive) build."""
    for line in (repo / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version ="):
            version = line.split("=", 1)[1].strip().strip('"').strip("'")
            return f"deltafuse-{version}-py3-none-any"
    raise SystemExit("cannot determine package version from pyproject.toml")


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing evidence file for this wheel")
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    commands: list[dict] = []

    dirty = tree_dirty(repo)
    if dirty:
        print("refusing: working tree is not clean: " + "; ".join(dirty[:5]), file=sys.stderr)
        return 3
    commit_proc = _run(["git", "rev-parse", "HEAD"], cwd=str(repo))
    commit = commit_proc.stdout.strip()
    if commit_proc.returncode != 0 or len(commit) != 40:
        print("refusing: cannot determine HEAD commit", file=sys.stderr)
        return 3

    stem = _expected_stem(repo)
    target = out_dir / f"{stem}-build-manifest.json"
    if target.exists() and not args.force:
        print(
            f"refusing: {target} exists; pass --force to overwrite deliberately",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dist = tmp_path / "dist"

        def record(label: str, proc: subprocess.CompletedProcess) -> bool:
            commands.append({"command": " ".join(map(str, proc.args)), "rc": proc.returncode})
            if proc.returncode != 0:
                print(f"{label} failed:\n{proc.stdout}{proc.stderr}", file=sys.stderr)
                return False
            return True

        build = _run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(repo)]
        )
        if not record("pip wheel", build):
            return 1
        wheels = list(dist.glob("deltafuse-*.whl"))
        if not wheels:
            print("no wheel built", file=sys.stderr)
            return 1
        wheel = wheels[0]

        venv_dir = tmp_path / "venv"
        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "Scripts" / "python.exe"
        if not pip.is_file():
            pip = venv_dir / "bin" / "python"
        backend_version = _run(
            [str(pip), "-c", "import setuptools;print(setuptools.__version__)"]
        ).stdout.strip()
        pip_version = _run([str(pip), "-m", "pip", "--version"]).stdout.split()[1]

        install = _run([str(pip), "-I", "-m", "pip", "install", str(wheel)])
        if not record("venv pip install", install):
            return 1
        workdir = tmp_path / "clean"
        workdir.mkdir()
        for label, cmd, expect in (
            ("CLI smoke", [str(pip), "-m", "deltafuse", "--help"], 0),
            ("init smoke", [str(pip), "-m", "deltafuse", "init", str(workdir / "product")], 0),
            ("validate-config", [str(pip), "-m", "deltafuse", "validate-config", str(workdir / "product")], 0),
        ):
            proc = _run(cmd, cwd=str(workdir))
            ok = record(label, proc)
            if label == "CLI smoke" and ok and "usage:" not in (proc.stdout + proc.stderr).lower():
                print("CLI smoke: no usage output", file=sys.stderr)
                return 1
            if not ok:
                return 1
        lock = workdir / "product" / ".deltafuse" / "lock.yaml"
        if not lock.is_file() or "schema_version: 3" not in lock.read_text(encoding="utf-8"):
            print("init smoke: lock contract v3 missing", file=sys.stderr)
            return 1

        evidence = {
            "schema_version": SCHEMA_VERSION,
            "commit": commit,
            "tree_clean": True,
            "wheel": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "wheel_size_bytes": wheel.stat().st_size,
            "build_frontend": f"pip wheel {pip_version}",
            "build_backend": f"setuptools {backend_version}",
            "python": f"{sys.version.split()[0]} ({sys.implementation.name})",
            "platform": sys.platform,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commands": commands,
        }
        try:
            _validate(evidence)
        except Exception as ex:
            print(f"evidence failed schema validation: {ex}", file=sys.stderr)
            return 1
        _atomic_write_json(target, evidence)
    print(f"evidence written: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
