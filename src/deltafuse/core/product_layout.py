"""One definition of a product's layout: where its code is, where its tests are, what is neither.

Audit 2026-11-17 (S2; FE-2, FE-4, FE-10): the Red oracle freeze knew `tests/**` and `src/test/**`,
the stale-evidence hash knew `docs/spec/**` and a literal `src/**`, the context budget had a list
of directories of its own, and each sat beside `workflow.code_roots`, which the leash and the
write contracts follow. A product that keeps its code in `app/**` or `services/calc/src/**` froze
no oracle and its evidence never went stale. Every check that asks "is this product code", "is
this a test", "is this a cache or a build product" asks here.

* **code roots** - `workflow.code_roots` of `.deltafuse/config.yaml`, else `src/**` and `tests/**`.
  A root holds code and tests alike (`svc/src/**`).
* **tests** - a file is on the test side by where it is (a directory named `tests`, `test` or
  `__tests__`, a `src/<set>/` source set whose name says test: `src/test`, `src/integrationTest`,
  `src/testFixtures`) or by what it is called (`test_x.py`, `x_test.py`, `conftest.py`,
  `CalcTest.java`, `CalcIT.kt`, `x.test.ts`, `x_test.go`). The rule does not depend on the code
  roots: a failing test is frozen wherever it lives.
* **exclusions** - version control, the Core's own directory, interpreter and tool caches,
  virtual environments, and a build directory beside the build file that fills it (`target/`
  beside `pom.xml`, `build/` beside a Gradle build file).

Content hashes are taken over line-ending-normalised bytes (`content_sha256`): git with
`core.autocrlf` rewrites a text file's line endings on checkout without changing its content.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from deltafuse.core.config import config_section

DEFAULT_CODE_ROOTS = ("src/**", "tests/**")
SPEC_ROOT = "docs/spec"

# Directories that are never product content, wherever they are.
EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".deltafuse",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".nox",
    ".venv", "venv", "node_modules", "site-packages", ".gradle", ".idea", ".vscode",
})
EXCLUDED_DIR_SUFFIXES = (".egg-info",)
EXCLUDED_FILE_SUFFIXES = (".pyc", ".pyo", ".class")
# A build directory is excluded only beside the build file that fills it: `build` and `target`
# are ordinary names for a package or a folder of the product too.
BUILD_DIRS: dict[str, tuple[str, ...]] = {
    "target": ("pom.xml",),
    "build": ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"),
}

# The Core's own records of work: never product code, even under a code root of `**`.
BOOKKEEPING_PREFIXES = ("docs/changes/", "docs/archive/", "docs/intake/")

TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__"})
JVM_SOURCE_SUFFIXES = (".java", ".kt", ".groovy", ".scala")
_JVM_TEST_STEM_ENDS = ("Test", "Tests", "TestCase", "IT", "ITCase", "Spec")
_JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def posix_relpath(path: str) -> str:
    """Repo-relative POSIX form: drop leading './' and '/' only.

    `str.lstrip("./")` strips a character set, not a prefix: it turned
    '.deltafuse/x' into 'deltafuse/x', so no dot-directory ever matched a glob
    such as '.deltafuse/**'.
    """
    rel = Path(path).as_posix()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.lstrip("/")


def configured_code_roots(product_root: Path | str | None) -> tuple[str, ...] | None:
    """`workflow.code_roots` from the product's config, or None when it sets none."""
    if product_root is None:
        return None
    roots = config_section(product_root, "workflow", tolerate=(OSError, yaml.YAMLError)).get("code_roots")
    if not isinstance(roots, list):
        return None
    clean = [posix_relpath(r.strip()) for r in roots if isinstance(r, str) and r.strip()]
    return tuple(dict.fromkeys(clean)) or None


def normalize_line_endings(data: bytes) -> bytes:
    """CRLF -> LF for text; bytes with a NUL are binary and stay untouched."""
    if b"\x00" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def content_sha256(path: Path) -> str:
    """SHA-256 of a file's content, the same for a CRLF and an LF checkout of it."""
    return hashlib.sha256(normalize_line_endings(Path(path).read_bytes())).hexdigest().lower()


def is_test_source_name(name: str) -> bool:
    """A file name a test runner reads tests from, whatever directory it is in."""
    if name.endswith(".py"):
        return name.startswith("test_") or name.endswith("_test.py")
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        return False
    suffix = "." + suffix
    if suffix in JVM_SOURCE_SUFFIXES:
        return stem.endswith(_JVM_TEST_STEM_ENDS) or (stem.startswith("Test") and stem[4:5].isupper())
    if suffix in _JS_SUFFIXES:
        return stem.endswith((".test", ".spec"))
    if suffix == ".go":
        return stem.endswith("_test")
    return False


def _in_test_directory(parts: list[str]) -> bool:
    """*parts* are the directories of a path: one of them is a test directory."""
    for i, part in enumerate(parts):
        if part.lower() in TEST_DIR_NAMES:
            return True
        if i and parts[i - 1] == "src" and "test" in part.lower():
            return True  # a Gradle/Maven source set: src/test, src/integrationTest, src/testFixtures
    return False


@dataclass(frozen=True)
class ProductLayout:
    """Where one product keeps its code and tests. Build it with `product_layout(root)`."""

    root: Path | None
    code_roots: tuple[str, ...] = DEFAULT_CODE_ROOTS
    configured: bool = False

    # --- one path -------------------------------------------------------------------------

    def is_excluded(self, rel: str) -> bool:
        """A cache, a virtual environment, version control, the Core's directory, a build product."""
        rel = posix_relpath(str(rel).replace("\\", "/"))
        parts = rel.split("/")
        if parts[-1].endswith(EXCLUDED_FILE_SUFFIXES):
            return True
        for i, part in enumerate(parts[:-1]):
            if part in EXCLUDED_DIRS or part.endswith(EXCLUDED_DIR_SUFFIXES):
                return True
            if part in BUILD_DIRS and self._is_build_dir(parts[:i], part):
                return True
        return False

    def _is_build_dir(self, parent: list[str], name: str) -> bool:
        if self.root is None:
            return False
        base = self.root.joinpath(*parent)
        return any((base / build_file).is_file() for build_file in BUILD_DIRS[name])

    def is_code(self, rel: str) -> bool:
        """Under a code root and not excluded: product code or a test."""
        rel = posix_relpath(str(rel).replace("\\", "/"))
        if not rel or self.is_excluded(rel) or rel.startswith(BOOKKEEPING_PREFIXES):
            return False
        return any(fnmatch.fnmatch(rel, root.replace("\\", "/")) for root in self.code_roots)

    def is_test(self, rel: str) -> bool:
        """On the test side: a test, or what tests are made of (a conftest, a fixture, test data)."""
        rel = posix_relpath(str(rel).replace("\\", "/"))
        if not rel or self.is_excluded(rel):
            return False
        parts = rel.split("/")
        name = parts[-1]
        return _in_test_directory(parts[:-1]) or name == "conftest.py" or is_test_source_name(name)

    def is_test_source(self, rel: str) -> bool:
        """A file a runner reads tests from: by its name anywhere, or JVM source in a test directory."""
        rel = posix_relpath(str(rel).replace("\\", "/"))
        if not rel or self.is_excluded(rel):
            return False
        parts = rel.split("/")
        name = parts[-1]
        if is_test_source_name(name):
            return True
        return name.endswith(JVM_SOURCE_SUFFIXES) and _in_test_directory(parts[:-1])

    # --- lists ----------------------------------------------------------------------------

    def test_side(self, paths: Iterable[object]) -> list[str]:
        """The paths among *paths* that are on the test side, POSIX, sorted, unique."""
        out: set[str] = set()
        for raw in paths:
            if not isinstance(raw, str):
                continue
            rel = posix_relpath(raw.replace("\\", "/"))
            if rel and self.is_test(rel):
                out.add(rel)
        return sorted(out)

    def walk(self, top: str = "") -> Iterable[str]:
        """Every file under *top* (a directory relative to the root) that is not excluded, POSIX."""
        if self.root is None:
            return
        base = self.root / top if top else self.root
        if base.is_file():
            rel = base.relative_to(self.root).as_posix()
            if not self.is_excluded(rel):
                yield rel
            return
        for dirpath, dirnames, filenames in os.walk(base):
            here = Path(dirpath).relative_to(self.root).as_posix()
            prefix = "" if here == "." else here + "/"
            dirnames[:] = sorted(d for d in dirnames if not self.is_excluded(f"{prefix}{d}/x"))
            for name in sorted(filenames):
                rel = prefix + name
                if not self.is_excluded(rel):
                    yield rel

    def glob(self, pattern: str) -> list[str]:
        """Existing files a glob of the product lists (`fnmatch`, as the write contracts match),
        not excluded, POSIX, sorted. The walk starts at the pattern's literal directories."""
        pattern = posix_relpath(pattern.replace("\\", "/"))
        literal: list[str] = []
        for part in pattern.split("/"):
            if any(ch in part for ch in "*?["):
                break
            literal.append(part)
        return sorted(rel for rel in self.walk("/".join(literal)) if rel == pattern or fnmatch.fnmatch(rel, pattern))

    def code_files(self) -> list[str]:
        """Every file under the code roots: product code and tests, POSIX, sorted, unique."""
        found: set[str] = set()
        for root in self.code_roots:
            found.update(rel for rel in self.glob(root) if not rel.startswith(BOOKKEEPING_PREFIXES))
        return sorted(found)

    def spec_files(self) -> list[str]:
        """Every file of the live specification (`docs/spec/**`)."""
        return sorted(self.walk(SPEC_ROOT)) if self.root is not None and (self.root / SPEC_ROOT).is_dir() else []

    def describe(self) -> str:
        """The hashed tree in words, for a gate message."""
        return f"{SPEC_ROOT}/** and the code roots ({', '.join(self.code_roots)})"


def product_layout(product_root: Path | str | None) -> ProductLayout:
    """The layout of the product at *product_root* (`workflow.code_roots`, else the defaults)."""
    root = Path(product_root) if product_root is not None else None
    roots = configured_code_roots(root)
    return ProductLayout(root=root, code_roots=roots or DEFAULT_CODE_ROOTS, configured=bool(roots))
