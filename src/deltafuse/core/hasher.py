"""Content hash calculation for DeltaFuse framework distribution."""

from __future__ import annotations
import hashlib
from pathlib import Path


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def compute_framework_content_hash(framework_root: Path | str | None = None) -> str:
    """
    Computes the canonical framework content hash across docs/, process/, scripts/, tests/ and VERSION.
    Matches the algorithm in scripts/init.ps1 and scripts/init.sh.
    """
    if framework_root is None:
        framework_root = Path(__file__).resolve().parent.parent.parent.parent
    else:
        framework_root = Path(framework_root).resolve()

    records: list[str] = []
    roots = ["docs", "process", "scripts", "tests"]
    for root_name in roots:
        root_dir = framework_root / root_name
        if root_dir.is_dir():
            for file_path in root_dir.rglob("*"):
                if file_path.is_file():
                    # Skip __pycache__ or .pytest_cache if created in framework
                    if "__pycache__" in file_path.parts or ".pytest_cache" in file_path.parts:
                        continue
                    rel_path = file_path.relative_to(framework_root).as_posix().lower()
                    file_hash = compute_file_sha256(file_path)
                    records.append(f"{rel_path}:{file_hash}")

    version_path = framework_root / "VERSION"
    if version_path.is_file():
        version_hash = compute_file_sha256(version_path)
        records.append(f"version:{version_hash}")

    records.sort()
    payload = "\n".join(records) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()


_SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def compute_product_baseline_revision(repo_root: Path | str) -> str:
    """SHA-256 of docs/spec/** and src/**. Used as evidence base_revision (F-006 / RM-006).

    Content hash, not git HEAD and not a timestamp: a merged spec/code tree must
    invalidate Green recorded against the previous tree.
    """
    root = Path(repo_root).resolve()
    records: list[str] = []
    for root_name in ("docs/spec", "src"):
        tree = root / Path(root_name)
        if not tree.is_dir():
            continue
        for file_path in tree.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in _SKIP_PARTS for part in file_path.parts):
                continue
            rel_path = file_path.relative_to(root).as_posix().lower()
            records.append(f"{rel_path}:{compute_file_sha256(file_path)}")
    records.sort()
    payload = "\n".join(records) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()
    return f"sha256:{digest}"
