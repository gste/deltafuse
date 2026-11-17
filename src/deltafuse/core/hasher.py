"""Content hash calculation for DeltaFuse framework distribution."""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Iterable

from deltafuse.core.product_layout import content_sha256, normalize_line_endings, product_layout

__all__ = [
    "compute_file_sha256",
    "compute_framework_content_hash",
    "compute_product_baseline_revision",
    "compute_red_oracle_digest",
    "normalize_line_endings",
    "oracle_paths",
]


def oracle_paths(changed_paths: Iterable[str], repo_root: Path | str | None = None) -> list[str]:
    """The files on the test side among a Red record's changed_paths, sorted.

    What a test file is comes from the product's layout (core/product_layout.py), not from a list
    of directories kept here: until 3.3.14 only `tests/**` and `src/test/**` counted, so a product
    with `workflow.code_roots: [app/**, test/**]` froze no oracle at all (audit 2026-11-17, FE-2).
    """
    return product_layout(repo_root).test_side(changed_paths)


def compute_red_oracle_digest(repo_root: Path | str, changed_paths: Iterable[str]) -> str | None:
    """Content hash of the test files a Red record declared.

    The declared oracle is frozen once Red is recorded: Implement may add tests
    but must not change the one Red was taken against (implement/SKILL.md, and
    Green must pass "without changing its oracle"). Matching by test *name* alone
    let a Worker rewrite the assertion during Implement and still record an
    authentic Green over an untouched product. None when no test file is listed,
    so there is no oracle of Declare's own to freeze. A file deleted before Green
    hashes as absent, so deleting the oracle reads as a change too. The hash is of
    the content, not of the line endings a checkout gave it (FE-10).
    """
    root = Path(repo_root)
    records: list[str] = []
    for rel in oracle_paths(changed_paths, root):
        path = root / rel
        try:
            digest = content_sha256(path) if path.is_file() else ""
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
    Each file is hashed line-ending-normalized, so a CRLF and an LF checkout of
    the same tree pin the same hash.
    Matches the algorithm in scripts/init.ps1 and scripts/init.sh.
    """
    if framework_root is None:
        framework_root = Path(__file__).resolve().parent.parent.parent.parent
    else:
        framework_root = Path(framework_root).resolve()

    records: list[str] = []

    def add(name: str, path: Path) -> None:
        data = normalize_line_endings(path.read_bytes())
        records.append(f"{name}:{hashlib.sha256(data).hexdigest().lower()}")

    roots = ["docs", "process", "scripts", "tests", "src"]
    for root_name in roots:
        root_dir = framework_root / root_name
        if root_dir.is_dir():
            for file_path in root_dir.rglob("*"):
                if file_path.is_file():
                    # Skip __pycache__ or .pytest_cache if created in framework
                    if "__pycache__" in file_path.parts or ".pytest_cache" in file_path.parts:
                        continue
                    # and the build metadata pip writes into src/ on every editable install or
                    # wheel build, which moved a checkout's hash with no framework change
                    if any(part.endswith(".egg-info") for part in file_path.relative_to(framework_root).parts):
                        continue
                    add(file_path.relative_to(framework_root).as_posix().lower(), file_path)

    version_path = framework_root / "VERSION"
    if version_path.is_file():
        add("version", version_path)

    pyproject_path = framework_root / "pyproject.toml"
    if pyproject_path.is_file():
        add("pyproject", pyproject_path)

    payload = "\n".join(sorted(records)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()


def compute_product_baseline_revision(repo_root: Path | str) -> str:
    """SHA-256 of the live specification and of every file under the product's code roots.
    Used as evidence base_revision (F-006 / RM-006).

    Content hash, not git HEAD and not a timestamp: a merged spec/code tree must
    invalidate Green recorded against the previous tree. The tree is the layout's
    (core/product_layout.py): `docs/spec/**` and `workflow.code_roots` (else `src/**` and
    `tests/**`), without caches and build products. Until 3.3.14 it was `docs/spec/**` and a
    literal `src/**`, so the evidence of a product with its code elsewhere never went stale
    (audit 2026-11-17, FE-4); and it was taken over raw bytes, so a checkout that rewrote line
    endings moved it (FE-10).
    """
    root = Path(repo_root).resolve()
    layout = product_layout(root)
    records: list[str] = []
    for rel in sorted(set(layout.spec_files()) | set(layout.code_files())):
        try:
            records.append(f"{rel.lower()}:{content_sha256(root / rel)}")
        except OSError:
            continue
    records.sort()
    payload = "\n".join(records) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()
    return f"sha256:{digest}"
