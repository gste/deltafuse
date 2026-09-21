"""QF-019: build the canonical qualification command image.

This is an explicit, maintainer-run command — tests never build against a
repository output directory:

    python scripts/build_qual_image.py --output-dir bench/builds [--force]

Pipeline: clean-tree guard -> `pip wheel --no-deps` from the clean commit ->
container build from a context that contains ONLY the wheel (no checkout,
bench pack or judge-side script) -> measured image identity via runtime
inspect -> schema-validated, atomically written
`<output-dir>/qual-image-<version>-<commit8>-manifest.json` (commit, wheel
sha256, image_id digest, pinned base image and pytest version, commands).

The script prints the immutable digest reference to export as
DELTAFUSE_QUAL_IMAGE. A mutable tag is never accepted for a release
campaign. NOTE: the container executor this image was built for
(scripts/qualify_executor.py) was removed in 77dad7f; scripts/qualify.py
does not use it, so this image currently has no consumer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schemas" / "qual-image.schema.json"
CONTAINERFILE = Path(__file__).resolve().parent / "Containerfile.qual"
SCHEMA_VERSION = 1
DEFAULT_BASE_IMAGE = "python:3.12-slim-bookworm"
DEFAULT_PYTEST_PIN = "9.1.1"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=1800, **kwargs)


def tree_dirty(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(repo)
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def framework_commit(repo: Path) -> str:
    proc = _run(["git", "rev-parse", "HEAD"], cwd=str(repo))
    if proc.returncode != 0:
        raise SystemExit("refusing: cannot determine HEAD commit")
    sha = proc.stdout.strip()
    if len(sha) != 40:
        raise SystemExit(f"refusing: HEAD is not a full SHA: {sha!r}")
    return sha


def package_version(repo: Path) -> str:
    version_path = repo / "VERSION"
    if not version_path.is_file():
        raise SystemExit("cannot determine package version: VERSION is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise SystemExit(f"cannot determine package version: invalid VERSION {version!r}")
    return version


def _build_wheel(repo: Path, dist: Path, record) -> Path:
    """Build the framework wheel from the clean tree; returns the wheel path.

    `record(proc)` journals every command with its return code into the
    build manifest."""
    proc = _run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(repo)]
    )
    record(proc)
    if proc.returncode != 0:
        print(f"pip wheel failed:\n{proc.stdout}{proc.stderr}", file=sys.stderr)
        raise SystemExit(1)
    wheels = sorted(dist.glob("deltafuse-*.whl"))
    if not wheels:
        print("no wheel built", file=sys.stderr)
        raise SystemExit(1)
    return wheels[0]


def detect_runtime() -> str | None:
    for runtime in ("docker", "podman"):
        if shutil.which(runtime):
            return runtime
    return None


def validate_manifest(data: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(data)


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--runtime", default=None, help="docker or podman (auto-detected)")
    ap.add_argument("--base-image", default=DEFAULT_BASE_IMAGE)
    ap.add_argument("--pytest-pin", default=DEFAULT_PYTEST_PIN)
    ap.add_argument("--tag", default=None,
                    help="image tag to build (the release reference is the digest)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing manifest for this commit")
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime = args.runtime or detect_runtime()
    if not runtime:
        print("refusing: no container runtime (docker/podman) available", file=sys.stderr)
        return 3

    commands: list[dict] = []

    def record(proc: subprocess.CompletedProcess) -> bool:
        commands.append({"command": " ".join(map(str, proc.args)), "rc": proc.returncode})
        return proc.returncode == 0

    dirty = tree_dirty(repo)
    if dirty:
        print("refusing: working tree is not clean: " + "; ".join(dirty[:5]),
              file=sys.stderr)
        return 3
    commit = framework_commit(repo)
    version = package_version(repo)
    tag = args.tag or f"deltafuse/qual:{version}-{commit[:8]}"
    target = out_dir / f"qual-image-{version}-{commit[:8]}-manifest.json"
    if target.exists() and not args.force:
        print(f"refusing: {target} exists; pass --force to overwrite deliberately",
              file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Step 1: the wheel is built FIRST, from the clean commit; the image
        # build context receives only this wheel.
        wheel = _build_wheel(repo, tmp_path / "wheel", record)
        wheel_sha = hashlib.sha256(wheel.read_bytes()).hexdigest()

        # Step 2: image from the wheel + pinned tool dependencies only.
        context = tmp_path / "context"
        context.mkdir()
        shutil.copy2(wheel, context / wheel.name)
        build = _run([
            runtime, "build",
            "-f", str(CONTAINERFILE),
            "--build-arg", f"BASE_IMAGE={args.base_image}",
            "--build-arg", f"PYTEST_PIN={args.pytest_pin}",
            "-t", tag, str(context),
        ])
        if not record(build):
            print(f"image build failed:\n{build.stdout}{build.stderr}", file=sys.stderr)
            return 1

        # Step 3: the image identity is measured, never assumed from the tag.
        inspect = _run([runtime, "image", "inspect", "--format", "{{.Id}}", tag])
        image_id = inspect.stdout.strip().splitlines()[-1] if inspect.stdout.strip() else ""
        if not record(inspect) or not image_id.startswith("sha256:"):
            print(f"cannot measure image digest: {inspect.stderr}", file=sys.stderr)
            return 1

        pip_version = _run([sys.executable, "-m", "pip", "--version"]).stdout.split()[1]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "commit": commit,
            "tree_clean": True,
            "image_tag": tag,
            "image_id": image_id,
            "wheel": wheel.name,
            "wheel_sha256": wheel_sha,
            "wheel_size_bytes": wheel.stat().st_size,
            "base_image": args.base_image,
            "pytest_pin": args.pytest_pin,
            "containerfile": "scripts/Containerfile.qual",
            "python": f"{sys.version.split()[0]} ({sys.implementation.name})",
            "platform": sys.platform,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commands": commands,
        }
        try:
            validate_manifest(manifest)
        except Exception as ex:
            print(f"manifest failed schema validation: {ex}", file=sys.stderr)
            return 1
        _atomic_write_json(target, manifest)
    print(f"qual image manifest written: {target}")
    print(f"image tag: {tag}")
    print(f"export DELTAFUSE_QUAL_IMAGE={image_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
