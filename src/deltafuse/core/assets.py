"""Runtime asset resolution (DF3-005).

One resolver for framework assets: packaged bundle (wheel, via
``importlib.resources``) first, canonical ``process/**`` in the source
checkout as the developer fallback. The bundle manifest is verified before
assets are used, so a corrupted or stale wheel fails loudly instead of
serving mismatched schemas/templates/skills.
"""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

BUNDLE_PACKAGE = "deltafuse.assets"


class AssetError(Exception):
    """Bundle missing or fails manifest verification."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_executing_framework_identity() -> tuple[str, set[str]]:
    """Return (running_version, set_of_valid_content_hashes) for executing framework assets."""
    from deltafuse import __version__
    from deltafuse.core.hasher import compute_framework_content_hash

    valid_hashes: set[str] = set()

    bundle = bundle_root()
    if bundle is not None:
        manifest_path = bundle / "manifest.json"
        if manifest_path.is_file():
            digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest().lower()
            valid_hashes.add(digest)
            valid_hashes.add(f"sha256:{digest}")

    source = source_assets_root()
    if source is not None:
        digest = compute_framework_content_hash().lower()
        valid_hashes.add(digest)
        valid_hashes.add(f"sha256:{digest}")

    return __version__, valid_hashes


def get_installed_lock_hash() -> str:
    """Return an authentic sha256:... lock content_hash string for executing framework.

    The packaged bundle's manifest hash comes first: it is the one every copy
    verifies - a wheel installed elsewhere knows only that hash, while a source
    checkout also knows the process/ tree hash. Picking the alphabetically
    first of the two made a lock written from a checkout fail in an installed
    copy whenever the process/ hash happened to sort first (CI, macOS, 3.2.0).
    """
    bundle = bundle_root()
    if bundle is not None and (bundle / "manifest.json").is_file():
        digest = hashlib.sha256((bundle / "manifest.json").read_bytes()).hexdigest().lower()
        return f"sha256:{digest}"
    _, valid_hashes = get_executing_framework_identity()
    for h in sorted(valid_hashes):
        if h.startswith("sha256:"):
            return h
    if valid_hashes:
        return f"sha256:{sorted(valid_hashes)[0]}"
    return "sha256:" + ("0" * 64)


def source_assets_root() -> Path | None:
    """Canonical process/ tree of a source checkout, if present."""
    root = Path(__file__).resolve().parent.parent.parent.parent
    candidate = root / "process"
    return candidate if candidate.is_dir() else None


def bundle_root() -> Path | None:
    """Directory of the packaged asset bundle, if importable."""
    try:
        anchor = resources.files(BUNDLE_PACKAGE)
    except ModuleNotFoundError:
        return None
    with resources.as_file(anchor) as path:
        return path


def verify_manifest(root: Path) -> list[str]:
    """Re-hash every manifest entry; return problems (empty when intact)."""
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["asset bundle manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as ex:
        return [f"asset bundle manifest is unreadable: {ex}"]
    if manifest.get("schema_version") != 1:
        return [f"unsupported bundle schema_version: {manifest.get('schema_version')!r}"]
    problems: list[str] = []
    files: dict[str, str] = manifest.get("files") or {}
    for rel, digest in sorted(files.items()):
        path = root / rel
        if not path.is_file():
            problems.append(f"bundle asset missing: {rel}")
        elif _hash(path) != digest:
            problems.append(f"bundle asset tampered: {rel}")
    return problems


def resolve_assets(sub: str, *, prefer: str = "auto") -> Path:
    """Resolve ``schemas``/``templates``/``skills`` directory.

    prefer: ``auto`` — bundle when packaged, source tree in checkouts;
    ``bundle`` — require the packaged bundle; ``source`` — require process/.
    """
    if prefer not in {"auto", "bundle", "source"}:
        raise AssetError(f"unknown prefer mode: {prefer!r}")

    bundle = None if prefer == "source" else bundle_root()
    if bundle is not None and (bundle / sub).is_dir():
        problems = verify_manifest(bundle)
        if problems:
            raise AssetError("; ".join(problems))
        return bundle / sub

    if prefer == "bundle":
        raise AssetError(f"asset bundle package {BUNDLE_PACKAGE!r} is not installed")

    source = source_assets_root()
    if source is not None and (source / sub).is_dir():
        return source / sub

    raise AssetError(
        f"framework assets '{sub}' not found: no usable bundle and no process/ source tree"
    )
