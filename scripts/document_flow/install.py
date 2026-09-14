"""Install the J03 public pack into a Worker sandbox, refusing judge material.

The installer verifies the case's ``public-inventory.json`` before anything
is copied: every entry must be a portable relative path inside the case, a
regular file (no symlink or Windows reparse point), free of judge-material
names (oracle, hidden, mutation, judge, secret), and matching its recorded
SHA-256. After the framework install, the installed product is re-verified:
every inventory file present with its exact hash, no judge-named files, and
no escaping links anywhere in the product tree.

Usage:
  python -m scripts.document_flow.install TARGET_DIR [--case-root DIR]
      [--framework-root DIR] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_ROOT = REPO_ROOT / "process" / "bench" / "cases" / "J03-document-flow"

JUDGE_NAME_PARTS = ("oracle", "hidden", "mutation", "judge", "secret")
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


class InstallRefused(Exception):
    """The requested installation would leak or corrupt; nothing was done."""


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _check_portable(rel: str) -> None:
    if not rel or rel.strip() != rel:
        raise InstallRefused(f"inventory path is not normalized: {rel!r}")
    if "\\" in rel or rel.startswith("/") or Path(rel).is_absolute() or ":" in rel:
        raise InstallRefused(f"inventory path is not portable: {rel!r}")
    parts = Path(rel).parts
    if any(part in ("..", ".") for part in parts) or "/./" in f"/{rel}":
        raise InstallRefused(f"inventory path escapes the case: {rel!r}")


def _check_no_judge_name(rel: str) -> None:
    lowered = rel.lower()
    for part in JUDGE_NAME_PARTS:
        for segment in Path(lowered).parts:
            if part in segment:
                raise InstallRefused(
                    f"inventory entry looks like judge material: {rel!r}")


def load_inventory(case_root: Path) -> dict[str, Any]:
    path = case_root / "public-inventory.json"
    if not path.is_file():
        raise InstallRefused(f"case has no public-inventory.json: {case_root}")
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as failure:
        raise InstallRefused(f"inventory unreadable: {failure}") from failure
    if inventory.get("schema_version") != 1 or not isinstance(
            inventory.get("includes"), list) or not inventory["includes"]:
        raise InstallRefused("inventory shape is not recognized")
    return inventory


def verify_inventory(case_root: Path) -> list[dict[str, Any]]:
    """Verify every inventory entry; return the verified entries."""
    inventory = load_inventory(case_root)
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in inventory["includes"]:
        rel = str(entry.get("path", ""))
        _check_portable(rel)
        _check_no_judge_name(rel)
        if rel in seen:
            raise InstallRefused(f"duplicate inventory entry: {rel}")
        seen.add(rel)
        file = case_root / rel
        if file.is_symlink() or _is_reparse_point(file):
            raise InstallRefused(f"inventory entry is a link: {rel}")
        if not file.is_file():
            raise InstallRefused(f"inventory entry is missing: {rel}")
        data = file.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry.get("sha256"):
            raise InstallRefused(f"inventory hash mismatch: {rel}")
        if entry.get("byte_length") != len(data):
            raise InstallRefused(f"inventory byte length mismatch: {rel}")
        verified.append({"path": rel, "sha256": digest,
                         "byte_length": len(data)})
    return verified


def _product_relative(rel: str) -> str | None:
    """Map a case inventory path onto the installed product layout.

    ``seed/**`` is installed at the product root, the intake becomes
    ``docs/intake/``, the worker briefing becomes ``BENCH.md``, and the
    public suite keeps its directory name. ``case.yaml`` is case metadata
    and is not installed.
    """
    if rel == "case.yaml":
        return None
    if rel == "input.md":
        return "docs/intake/J03-document-flow.md"
    if rel == "WORKER.md":
        return "BENCH.md"
    if rel.startswith("seed/"):
        return rel[len("seed/"):]
    if rel.startswith("public_suite/"):
        return rel
    return None


def _assert_product_clean(product: Path, verified: list[dict[str, Any]]) -> int:
    """Re-verify the installed product; return the verified file count."""
    for entry in verified:
        mapped = _product_relative(entry["path"])
        if mapped is None:
            continue
        file = product / mapped
        if file.is_symlink() or _is_reparse_point(file):
            raise InstallRefused(f"installed entry is a link: {entry['path']}")
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise InstallRefused(f"installed hash mismatch: {entry['path']}")
    for current, dir_names, file_names in os.walk(product):
        here = Path(current)
        for name in list(dir_names) + list(file_names):
            _check_no_judge_name(str((here / name).relative_to(product)))
            candidate = here / name
            if candidate.is_symlink() or _is_reparse_point(candidate):
                raise InstallRefused(
                    f"installed tree contains a link: "
                    f"{candidate.relative_to(product)}")
    return len(verified)


def install_document_flow(
    product_dir: Path | str,
    *,
    case_root: Path | str | None = None,
    framework_root: Path | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Install the J03 public pack and return the installation metadata."""
    product = Path(product_dir).resolve()
    case = Path(case_root).resolve() if case_root else DEFAULT_CASE_ROOT
    if not case.is_dir():
        raise InstallRefused(f"case root not found: {case}")
    verified = verify_inventory(case)

    from deltafuse.bench.init_product import init_bench_product

    pack_root = None
    if framework_root is not None:
        pack_root = Path(framework_root).resolve() / "process" / "bench"
    meta = init_bench_product(
        "J03-document-flow", product, framework_root=framework_root or REPO_ROOT,
        pack_root=pack_root, force=force)
    for entry in verified:  # the framework does not copy the public suite
        mapped = _product_relative(entry["path"])
        if mapped is None or not mapped.startswith("public_suite/"):
            continue
        source = case / entry["path"]
        destination = product / mapped
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    checked = _assert_product_clean(product, verified)
    return {"case": "J03-document-flow", "product": str(product),
            "intake": meta.get("intake"), "verified_files": checked,
            "inventory_entries": len(verified)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("product_dir")
    parser.add_argument("--case-root", default=None)
    parser.add_argument("--framework-root", default=None)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        meta = install_document_flow(
            arguments.product_dir, case_root=arguments.case_root,
            framework_root=arguments.framework_root, force=arguments.force)
    except InstallRefused as refusal:
        print(f"INSTALL REFUSED: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as failure:  # framework errors are refusals too
        print(f"INSTALL REFUSED: {failure}", file=sys.stderr)
        return EXIT_REFUSED
    print(json.dumps(meta, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
