"""Generate the immutable runtime asset bundle (DF3-005 / B-01).

Copies process/schemas, process/templates and process/skills into
src/deltafuse/assets/ and writes a manifest.json with SHA-256 per asset.
Canonical sources stay in process/**; the bundle is generated content that
ships inside the wheel and is re-verified at runtime. Run before building:

    python scripts/sync_assets.py

V3-FIX-022: `--check` is read-only. It generates the bundle into a temporary
directory, compares the manifest with the committed one and reports drift
without ever touching src/deltafuse/assets.

QF-009/QF-016: `sync` is a CRASH-SAFE TRANSACTIONAL REPLACEMENT — not a
single-operation atomic directory replacement (Windows does not provide one
for non-empty directories). The transaction keeps a journal next to the
target; every phase is journalled atomically BEFORE the rename it guards:

    prepared -> begin-prev -> prev-moved -> swapped -> (journal removed)

On startup `recover()` runs BEFORE any cleanup:
- valid target present: only journal-confirmed stale copies are deleted;
- target missing, valid prev present: prev is restored byte-for-byte;
- target missing, valid next present and the journal allows the commit:
  the transaction is completed (next becomes the target);
- ambiguous or invalid state: recovery STOPS WITHOUT DELETION.

`_verify_bundle` checks the manifest schema, the exact file set, per-file
SHA-256 and rejects symlink/junction entries inside the bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path

# Test-only overrides (used by the crash-kill matrix); production defaults.
REPO = Path(os.environ.get("DELTAFUSE_TEST_REPO")
            or Path(__file__).resolve().parent.parent)
ASSETS = Path(os.environ.get("DELTAFUSE_TEST_ASSETS")
              or REPO / "src" / "deltafuse" / "assets")
BUNDLE_ROOTS = ("schemas", "templates", "skills")
SCHEMA_VERSION = 1
JOURNAL_NAME = "assets.journal.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generate(target: Path) -> tuple[dict[str, str], list[str]]:
    """Generate the bundle into `target`; returns (files manifest, problems)."""
    problems: list[str] = []
    target.mkdir(parents=True, exist_ok=True)
    init_text = (
        '"""Generated runtime asset bundle. DO NOT EDIT: run scripts/sync_assets.py."""\n'
    )
    # QF-023: exact bytes — write_text would apply platform newline
    # translation (CRLF on Windows), making the hashed marker content
    # platform-dependent and the bundle non-verifiable across hosts.
    (target / "__init__.py").write_bytes(init_text.encode("utf-8"))
    files: dict[str, str] = {
        # QF-023: the package marker ships and is hashed like every asset
        "__init__.py": _hash(target / "__init__.py"),
    }
    for root in BUNDLE_ROOTS:
        source_dir = REPO / "process" / root
        if not source_dir.is_dir():
            problems.append(f"missing process/{root}")
            continue
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            rel = path.relative_to(source_dir)
            dest = target / root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            files[f"{root}/{rel.as_posix()}"] = _hash(dest)
    return files, problems


# QF-009: module-level alias so tests can inject rename failures.
_rename = os.rename


def _is_reparse_point(path: Path) -> bool:
    """True for symlinks and (on Windows) junctions/mount points inside a
    bundle. QF-023: detected via lstat reparse attributes, not only a
    realpath string comparison."""
    try:
        st = os.lstat(path)
    except OSError:
        return True
    if hasattr(st, "st_file_attributes"):
        if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    if os.path.islink(path):
        return True
    try:
        return os.path.realpath(path) != str(path)
    except OSError:
        return True


def _verify_bundle(bundle: Path) -> None:
    """QF-016: full bundle verification — manifest schema, exact file set,
    per-file hashes, no symlink/junction entries. Raises RuntimeError."""
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("bundle manifest schema_version mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError("bundle manifest has no files map")
    for rel, digest in files.items():
        if not isinstance(digest, str) or len(digest) != 64:
            raise RuntimeError(f"bundle manifest digest malformed: {rel}")
    # QF-023: the manifest must cover EVERY packaged regular file, the
    # package marker included — only the manifest itself is self-describing.
    expected = set(files) | {"manifest.json"}
    for path in sorted(bundle.rglob("*")):
        # the generator never packages these; runtime imports may drop them
        # into a development source tree and they are not bundle contract
        if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        rel = path.relative_to(bundle).as_posix()
        if _is_reparse_point(path):
            raise RuntimeError(f"bundle contains symlink/junction: {rel}")
        if path.is_file():
            if rel not in expected:
                raise RuntimeError(f"extra packaged file in bundle: {rel}")
    for rel, digest in sorted(files.items()):
        path = bundle / rel
        if not path.is_file():
            raise RuntimeError(f"generated bundle is missing {rel}")
        if _hash(path) != digest:
            raise RuntimeError(f"generated bundle hash mismatch: {rel}")


# ------------------------------------------------------------ QF-016 journal


def _journal_path(assets: Path) -> Path:
    return assets.parent / JOURNAL_NAME


def _read_journal(assets: Path) -> dict | None:
    """Journal dict, None when absent. A CORRUPTED journal is reported as
    {"corrupted": True} so recovery can stop without deleting anything."""
    path = _journal_path(assets)
    if not path.is_file():
        return None
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"corrupted": True}
    if not isinstance(journal, dict) or "target" not in journal:
        return {"corrupted": True}
    return journal


def _write_journal(assets: Path, journal: dict | None) -> None:
    """Atomic journal replacement; None removes the journal (commit)."""
    path = _journal_path(assets)
    if journal is None:
        path.unlink(missing_ok=True)
        return
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(journal, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _maybe_crash(phase: str) -> None:
    """Test-only crash injection: hard exit at a named transaction phase."""
    if os.environ.get("DELTAFUSE_SYNC_CRASH_AT") == phase:
        sys.stderr.write(f"[crash injection] {phase}\n")
        sys.stderr.flush()
        os._exit(137)


def recover(assets: Path | None = None) -> int:
    assets = assets if assets is not None else ASSETS
    """QF-016: recover the last transaction BEFORE any cleanup.

    Returns 0 when the state is clean/recovered; raises RuntimeError on an
    ambiguous or invalid state (stop WITHOUT deletion)."""
    parent = assets.parent
    journal = _read_journal(assets)
    if journal is None:
        return 0
    if journal.get("corrupted"):
        raise RuntimeError(
            "asset transaction journal is corrupted; refusing to touch "
            "assets — resolve manually, then delete the journal"
        )
    target_valid = prev_valid = next_valid = False
    prev = parent / journal["prev"] if journal.get("prev") else None
    nxt = parent / journal["next"] if journal.get("next") else None

    def _valid(path: Path | None) -> bool:
        if path is None or not path.exists():
            return False
        try:
            _verify_bundle(path)
            return True
        except (RuntimeError, json.JSONDecodeError, OSError):
            return False  # invalid candidate, never a reason to delete

    target_valid = _valid(assets)
    prev_valid = _valid(prev)
    next_valid = (
        journal.get("phase") in ("prepared", "begin-prev", "prev-moved")
        and _valid(nxt)
    )
    if target_valid:
        # only journal-confirmed stale copies may be removed
        for stale in (prev, nxt):
            if stale is not None and stale.exists():
                shutil.rmtree(stale, ignore_errors=True)
        _write_journal(assets, None)
        print("recovery: valid target present; confirmed stale copies removed")
        return 0
    if prev_valid:
        _rename(prev, assets)
        if nxt is not None and nxt.exists():
            shutil.rmtree(nxt, ignore_errors=True)
        _write_journal(assets, None)
        print("recovery: previous bundle restored")
        return 0
    if next_valid:
        _rename(nxt, assets)
        _write_journal(assets, None)
        print("recovery: verified new bundle committed")
        return 0
    raise RuntimeError(
        "asset transaction state is ambiguous (no valid target/prev/next); "
        "refusing to delete anything — resolve manually"
    )


def _cleanup_stale(parent: Path) -> None:
    """Remove temp dirs left behind by runs that never journalled them.

    Only runs AFTER recover() confirmed a valid committed state, so a stale
    directory can never be the last valid copy (QF-016)."""
    for pattern in ("assets.next-*", "assets.prev-*"):
        for stale in parent.glob(pattern):
            shutil.rmtree(stale, ignore_errors=True)


def _swap_in(new_dir: Path, target: Path) -> None:
    """QF-016 crash-safe transactional replacement.

    os.replace cannot replace a non-empty directory on Windows, so the swap
    is journalled renames: target -> prev (journalled BEFORE and AFTER), then
    next -> target; recovery restores prev or commits next after a crash.
    """
    parent = target.parent
    prev = parent / f"assets.prev-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    journal = _read_journal(target) or {}
    journal.update({
        "id": uuid.uuid4().hex,
        "target": target.name,
        "prev": prev.name,
        "next": new_dir.name,
        "files": json.loads((new_dir / "manifest.json").read_text(encoding="utf-8"))["files"],
    })
    had_previous = target.exists()
    if had_previous:
        journal["phase"] = "begin-prev"
        _write_journal(target, journal)
        _maybe_crash("begin-prev")
        _rename(target, prev)
        journal["phase"] = "prev-moved"
        _write_journal(target, journal)
        _maybe_crash("prev-moved")
    _maybe_crash("commit")
    try:
        _rename(new_dir, target)
    except Exception as ex:
        if had_previous and prev.exists():
            _rename(prev, target)  # rollback: restore the previous bundle
            _write_journal(target, None)
        raise RuntimeError(f"bundle swap failed; previous bundle restored: {ex}") from ex
    journal["phase"] = "swapped"
    _write_journal(target, journal)
    _maybe_crash("swapped")
    if had_previous:
        shutil.rmtree(prev, ignore_errors=True)
    _write_journal(target, None)


def sync(assets: Path | None = None) -> list[str]:
    assets = assets if assets is not None else ASSETS
    parent = assets.parent
    recover(assets)  # QF-016: recovery BEFORE cleanup, never the other way
    _cleanup_stale(parent)
    next_dir = parent / f"assets.next-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        files, problems = _generate(next_dir)
        if problems:
            shutil.rmtree(next_dir, ignore_errors=True)
            return problems
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_by": "scripts/sync_assets.py",
            "canonical": "process/**",
            "files": files,
        }
        manifest_text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        (next_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
        _verify_bundle(next_dir)  # never swap an unverified bundle
        _swap_in(next_dir, assets)
    except Exception:
        shutil.rmtree(next_dir, ignore_errors=True)  # no temp garbage
        raise
    print(f"bundle: {len(files)} assets -> {assets}")
    return problems


def check() -> int:
    """V3-FIX-022: read-only drift check; never mutates the assets tree."""
    if not (ASSETS / "manifest.json").is_file():
        print("check: src/deltafuse/assets is missing; run sync_assets.py")
        return 1
    before = (ASSETS / "manifest.json").read_bytes()
    committed = json.loads(before.decode("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        files, problems = _generate(Path(tmp))
    if problems:
        for problem in problems:
            print(f"check: {problem}")
        return 1
    expected = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/sync_assets.py",
        "canonical": "process/**",
        "files": files,
    }
    drift = []
    for key, value in expected["files"].items():
        if committed["files"].get(key) != value:
            drift.append(key)
    for key in sorted(set(committed["files"]) - set(expected["files"])):
        drift.append(f"-{key} (stale bundle entry)")
    # b) actual packaged files vs the committed manifest
    for rel, digest in sorted(committed["files"].items()):
        path = ASSETS / rel
        if not path.is_file():
            drift.append(f"missing packaged asset: {rel}")
        elif _hash(path) != digest:
            drift.append(f"tampered packaged asset: {rel}")
    # c) QF-023: full bundle verification — exact file set, per-file hashes
    #    and the TYPE of every entry (no symlink/junction/reparse point)
    try:
        _verify_bundle(ASSETS)
    except (RuntimeError, json.JSONDecodeError, OSError) as ex:
        drift.append(f"bundle verification failed: {ex}")
    if committed.get("schema_version") != expected["schema_version"]:
        drift.append("manifest schema_version")
    if drift:
        print(f"check: bundle is stale ({len(drift)} drift); run sync_assets.py:")
        for key in drift[:20]:
            print(f"  {key}")
        return 1
    print(f"check: bundle is up to date ({len(files)} assets)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="read-only: report bundle drift without regenerating",
    )
    ap.add_argument(
        "--recover-only",
        action="store_true",
        help="QF-016: run transaction recovery and exit without syncing",
    )
    args = ap.parse_args()
    if args.recover_only:
        try:
            sys.exit(recover())
        except RuntimeError as ex:
            print(f"recovery stopped: {ex}", file=sys.stderr)
            sys.exit(5)
    if args.check:
        sys.exit(check())
    try:
        sys.exit(1 if sync() else 0)
    except RuntimeError as ex:
        print(f"sync failed: {ex}", file=sys.stderr)
        sys.exit(5)
