"""Content hash calculation for DeltaFuse framework distribution."""

from __future__ import annotations
import fnmatch
import hashlib
from pathlib import Path
from typing import Iterable


# Test roots whose files are the declared oracle. `tests/**` is the framework's
# own Declare write scope; `src/test/**` is the Maven/Gradle layout the JVM
# report reader supports (test_reports.py, bench case J01-cooldown-java).
ORACLE_GLOBS = ("tests/**", "*/tests/**", "src/test/**", "*/src/test/**")


def oracle_paths(changed_paths: Iterable[str]) -> list[str]:
    """The declared test files among a Red record's changed_paths, sorted."""
    out: set[str] = set()
    for raw in changed_paths:
        if not isinstance(raw, str):
            continue
        rel = raw.replace("\\", "/").lstrip("/")
        if not rel:
            continue
        if any(fnmatch.fnmatch(rel, pattern) for pattern in ORACLE_GLOBS):
            out.add(rel)
    return sorted(out)


def compute_red_oracle_digest(repo_root: Path | str, changed_paths: Iterable[str]) -> str | None:
    """Content hash of the test files a Red record declared.

    The declared oracle is frozen once Red is recorded: Implement may add tests
    but must not change the one Red was taken against (implement/SKILL.md, and
    Green must pass "without changing its oracle"). Matching by test *name* alone
    let a Worker rewrite the assertion during Implement and still record an
    authentic Green over an untouched product. None when no test file is listed,
    so there is no oracle of Declare's own to freeze. A file deleted before Green
    hashes as absent, so deleting the oracle reads as a change too.
    """
    root = Path(repo_root)
    records: list[str] = []
    for rel in oracle_paths(changed_paths):
        path = root / rel
        try:
            digest = compute_file_sha256(path) if path.is_file() else ""
        except OSError:
            digest = ""
        records.append(f"{rel.lower()}:{digest}")
    if not records:
        return None
    payload = "\n".join(records) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def compute_framework_content_hash(framework_root: Path | str | None = None) -> str:
    """
    Computes the canonical framework content hash across docs/, process/, scripts/,
    tests/, src/ and pyproject.toml. DF3-003 / SEC-02: the executable Core
    (src/deltafuse/**) and the declared entrypoints are part of the versioned
    manifest, so tampering with Core code changes the pinned hash.
    Matches the algorithm in scripts/init.ps1 and scripts/init.sh.
    """
    if framework_root is None:
        framework_root = Path(__file__).resolve().parent.parent.parent.parent
    else:
        framework_root = Path(framework_root).resolve()

    records: list[str] = []
    roots = ["docs", "process", "scripts", "tests", "src"]
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

    pyproject_path = framework_root / "pyproject.toml"
    if pyproject_path.is_file():
        pyproject_hash = compute_file_sha256(pyproject_path)
        records.append(f"pyproject:{pyproject_hash}")

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
