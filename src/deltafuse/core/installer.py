"""Product installer and framework updater for DeltaFuse 2.0."""

from __future__ import annotations
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple
import yaml
from deltafuse.core.adapters import (
    adapter_mode_from_mapping,
    install_adapter_skills,
    is_framework_uri,
    resolve_effective_adapter_mode,
)
from deltafuse.core.assets import resolve_assets, source_assets_root
from deltafuse.core.hasher import compute_framework_content_hash
from deltafuse.core.leash import load_leash_mode, sync_leash_hook
from deltafuse.core.lock import format_lock_yaml, workflow_from_mapping


class InstallResult(NamedTuple):
    target_dir: Path
    version: str
    content_hash: str
    skills_installed: int
    adapter_mode: str
    agents_md_mode: str
    agents_md_target: Path | None


class InstallationError(Exception):
    """Raised when product installation or upgrade fails."""
    pass


def _active_change_ids(target_root: Path) -> list[str]:
    """Change ids whose status is not terminal (fail-closed upgrade, C-02)."""
    terminal = {"archived", "rejected", "duplicate", "superseded", "not-reproduced"}
    out: list[str] = []
    root = target_root / "docs" / "changes"
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*/change.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if not isinstance(data, dict):
            continue
        if data.get("status") not in terminal:
            out.append(str(data.get("id") or path.parent.name))
    return out


TEMPLATE_MAPPINGS = [
    ("process/templates/.deltafuse/config.yaml", ".deltafuse/config.yaml"),
    ("process/templates/docs/intake/README.md", "docs/intake/README.md"),
    ("process/templates/docs/changes/README.md", "docs/changes/README.md"),
    ("process/templates/docs/spec/README.md", "docs/spec/README.md"),
    ("process/templates/docs/spec/context.md", "docs/spec/context.md"),
    ("process/templates/docs/spec/_capabilities.yaml", "docs/spec/_capabilities.yaml"),
    ("process/templates/docs/decisions/README.md", "docs/decisions/README.md"),
    ("process/templates/docs/decisions/DEC-0000-template.md", "docs/decisions/DEC-0000-template.md"),
    ("process/templates/docs/archive/README.md", "docs/archive/README.md"),
    ("process/templates/docs/archive/intake/README.md", "docs/archive/intake/README.md"),
    ("process/templates/docs/archive/changes/README.md", "docs/archive/changes/README.md"),
    ("process/templates/CHANGELOG.md", "CHANGELOG.md"),
    ("process/templates/.github/workflows/deltafuse-leash.yml", ".github/workflows/deltafuse-leash.yml"),
]

BRIDGE_BEGIN = "<!-- deltafuse:bridge -->"
BRIDGE_END = "<!-- /deltafuse:bridge -->"
BRIDGE = """<!-- deltafuse:bridge -->
## DeltaFuse

When work is explicitly run through DeltaFuse, load the installed DeltaFuse
`run` skill and follow `deltafuse next --json`. DeltaFuse governs lifecycle
artifacts; repository rules continue to govern code, tests, security, and style.
<!-- /deltafuse:bridge -->
"""


def _effective_agents_path(target_root: Path) -> Path | None:
    """The override wins because it is the instruction file an agent will see."""
    override = target_root / "AGENTS.override.md"
    agents = target_root / "AGENTS.md"
    if override.is_file():
        return override
    if agents.is_file():
        return agents
    return None


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def _bridge_agents(path: Path) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    begins, ends = existing.count(BRIDGE_BEGIN), existing.count(BRIDGE_END)
    if begins != ends or begins > 1:
        raise InstallationError(
            f"Cannot add DeltaFuse bridge to {path.name}: damaged or ambiguous DeltaFuse bridge markers."
        )
    if begins == 1:
        start, end = existing.find(BRIDGE_BEGIN), existing.find(BRIDGE_END)
        if start > end:
            raise InstallationError(f"Cannot add DeltaFuse bridge to {path.name}: damaged DeltaFuse bridge markers.")
        return
    separator = "" if not existing or existing.endswith(("\n", "\r")) else "\n"
    _atomic_write(path, existing + separator + ("\n" if existing else "") + BRIDGE)


def _select_agents_mode(target_root: Path, requested: str | None) -> tuple[str, Path | None]:
    if requested is not None and requested not in {"prompt", "bridge", "preserve", "replace"}:
        raise InstallationError("Invalid --agents-md value; expected prompt, bridge, preserve, or replace.")
    effective = _effective_agents_path(target_root)
    mode = requested
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if mode is None:
        mode = "prompt" if interactive else "preserve"
    if mode == "prompt":
        if not interactive:
            raise InstallationError("--agents-md=prompt requires an interactive TTY.")
        target_name = effective.name if effective else "AGENTS.md (new)"
        print(f"Effective host instruction file: {target_name}")
        if (target_root / "AGENTS.override.md").is_file() and (target_root / "AGENTS.md").is_file():
            print("AGENTS.override.md takes precedence; changing AGENTS.md alone would not activate DeltaFuse.")
        print("[b] Add minimal bridge and preserve host rules; [p] leave unchanged (use /run or deltafuse next --json); [r] replace completely (removes host rules)")
        choice = input("Choose b, p, or r: ").strip().lower()
        mode = {"b": "bridge", "p": "preserve", "r": "replace"}.get(choice, "")
        if not mode:
            raise InstallationError("No valid AGENTS.md integration choice was made.")
    if mode == "replace" and effective is None:
        raise InstallationError("--agents-md=replace requires an existing effective host instruction file.")
    return mode, effective


def _apply_agents_policy(target_root: Path, requested: str | None, framework_root: Path, bundle_assets: Path | None) -> tuple[str, Path | None]:
    mode, effective = _select_agents_mode(target_root, requested)
    if mode == "preserve":
        return mode, effective
    if mode == "bridge":
        target = effective or target_root / "AGENTS.md"
        _bridge_agents(target)
        return mode, target
    assert effective is not None
    template = (framework_root / ("templates/AGENTS.md" if bundle_assets is not None else "process/templates/AGENTS.md")).read_text(encoding="utf-8")
    if sys.stdin.isatty() and sys.stdout.isatty():
        import difflib
        print("".join(difflib.unified_diff(effective.read_text(encoding="utf-8").splitlines(True), template.splitlines(True), fromfile=str(effective), tofile="DeltaFuse template")))
        if input("Replace this host instruction file? Type replace: ").strip() != "replace":
            raise InstallationError("AGENTS.md replacement cancelled.")
    _atomic_write(effective, template)
    return mode, effective

DIRECTORIES_TO_CREATE = [
    ".deltafuse",
    "docs/intake",
    "docs/changes",
    "docs/spec",
    "docs/decisions",
    "docs/archive/intake",
    "docs/archive/changes",
]

VERSION_TEMPLATE_MARKER = "0.0.0 # deltafuse:version-template"


def _render_version_markers(content: str, version: str) -> str:
    return content.replace(VERSION_TEMPLATE_MARKER, version)


def _copy_template_file(
    framework_root: Path, target_root: Path, src_rel: str, dst_rel: str, version: str
) -> bool:
    """Copies template file to target if target does not already exist. Returns True if created."""
    src = framework_root / src_rel
    dst = target_root / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return False
    content = src.read_text(encoding="utf-8")
    if VERSION_TEMPLATE_MARKER in content:
        _atomic_write(dst, _render_version_markers(content, version))
    else:
        shutil.copyfile(src, dst)
    return True


def _replace_config_source(config_content: str, source: str) -> str:
    if re.search(r"(?m)^\s{2}source:\s*\S+\s*$", config_content):
        return re.sub(
            r"(?m)^(\s{2}source:\s*)\S+(\s*)$",
            f"\\g<1>{source}\\g<2>",
            config_content,
            count=1,
        )
    return config_content


def install(
    target_dir: Path | str = ".",
    force: bool = False,
    framework_root: Path | str | None = None,
    agents_md: str | None = None,
) -> InstallResult:
    """
    Installs or updates DeltaFuse product layout in target_dir.
    """
    if agents_md is not None and agents_md not in {"prompt", "bridge", "preserve", "replace"}:
        raise InstallationError("Invalid --agents-md value; expected prompt, bridge, preserve, or replace.")
    target_root = Path(target_dir).resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    bundle_assets: Path | None
    if framework_root is None:
        checkout = source_assets_root()
        if checkout is not None:
            # Source checkout (dev, nested vendor tree): canonical process/.
            framework_root = checkout.parent
            bundle_assets = None
        else:
            # DF3-005: pure wheel install — the immutable bundle root stands
            # in for the checkout and the lock pins the bundle manifest digest.
            framework_root = resolve_assets("templates").parent
            bundle_assets = framework_root
    else:
        framework_root = Path(framework_root)
        if not framework_root.is_absolute():
            framework_root = target_root / framework_root
        framework_root = Path(os.path.abspath(str(framework_root)))
        bundle_assets = None

    if bundle_assets is None:
        version_file = framework_root / "VERSION"
        if not version_file.is_file():
            raise InstallationError(f"VERSION file not found in framework root: {framework_root}")
        version = version_file.read_text(encoding="utf-8").strip()
        content_hash = compute_framework_content_hash(framework_root)
    else:
        from importlib.metadata import version as _package_version

        version = _package_version("deltafuse")
        manifest_path = bundle_assets / "manifest.json"
        if not manifest_path.is_file():
            raise InstallationError("deltafuse asset bundle is incomplete: manifest.json missing")
        content_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    lock_path = target_root / ".deltafuse" / "lock.yaml"
    if lock_path.is_file():
        lock_text = lock_path.read_text(encoding="utf-8")
        lock_differs = f"content_hash: sha256:{content_hash}" not in lock_text
        if lock_differs and not force:
            raise InstallationError("A different DeltaFuse lock already exists. Rerun with --force for an explicit upgrade.")
        if lock_differs and force:
            # DF3-005 / C-02 fail-closed upgrade: a pin revision change never
            # silently invalidates active Change evidence stamps.
            active = _active_change_ids(target_root)
            if active:
                raise InstallationError(
                    "Fail-closed upgrade: framework pin differs while active Changes "
                    f"exist ({', '.join(sorted(active))}). Close or migrate the Changes "
                    "and re-run their evidence cycle before upgrading; evidence stamps "
                    "are never re-signed."
                )

    # Create target directories
    for d in DIRECTORIES_TO_CREATE:
        (target_root / d).mkdir(parents=True, exist_ok=True)

    # Append DeltaFuse-generated artifacts to host project .gitignore
    gitignore_path = target_root / ".gitignore"
    gitignore_entries = [
        ".deltafuse/hooks/",
        ".agents/skills/",
        ".cursor/skills/",
        ".gemini/skills/",
    ]
    gitignore_content = ""
    if gitignore_path.is_file():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
    new_entries = []
    for entry in gitignore_entries:
        if entry not in gitignore_content:
            new_entries.append(entry)
    if new_entries:
        gitignore_path.write_text(
            gitignore_content.rstrip() + "\n" + "\n".join(new_entries) + "\n",
            encoding="utf-8",
        )

    config_path = target_root / ".deltafuse" / "config.yaml"
    config_existed = config_path.is_file()
    if config_existed:
        config_content = config_path.read_text(encoding="utf-8")
        rendered_config = _render_version_markers(config_content, version)
        if rendered_config != config_content:
            _atomic_write(config_path, rendered_config)

    # Host instructions are never a normal template: choose their policy explicitly.
    agents_md_mode, agents_md_target = _apply_agents_policy(target_root, agents_md, framework_root, bundle_assets)

    # Copy product-owned template files.
    for src_rel, dst_rel in TEMPLATE_MAPPINGS:
        if bundle_assets is not None:
            src_rel = src_rel.replace('process/templates/', 'templates/', 1)
        _copy_template_file(framework_root, target_root, src_rel, dst_rel, version)

    adapter_roots: list[str] = []
    config_dict: dict = {}
    if config_path.is_file():
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                config_dict = loaded
            adapters_section = config_dict.get("adapters", {})
            if isinstance(adapters_section, dict):
                roots = adapters_section.get("roots", [])
                if isinstance(roots, list):
                    adapter_roots = [str(r).strip() for r in roots if r]
        except Exception:
            pass

    call_width, auto_accept, workflow_errors = workflow_from_mapping(config_dict)
    if workflow_errors:
        raise InstallationError("Invalid .deltafuse/config.yaml workflow: " + "; ".join(workflow_errors))

    requested_adapter_mode, adapter_mode_errors = adapter_mode_from_mapping(config_dict)
    if adapter_mode_errors:
        raise InstallationError("Invalid .deltafuse/config.yaml adapters: " + "; ".join(adapter_mode_errors))

    adapter_mode, nested_relposix = resolve_effective_adapter_mode(
        requested_adapter_mode, framework_root, target_root
    )
    if requested_adapter_mode == "link" and not nested_relposix:
        raise InstallationError(
            "adapters.mode is link but the framework checkout is not inside the product "
            "(use a git submodule or vendor path, or set adapters.mode to copy)."
        )

    config_source = None
    if config_path.is_file():
        config_text = config_path.read_text(encoding="utf-8")
        source_match = re.search(r"(?m)^\s{2}source:\s*(\S+)\s*$", config_text)
        if source_match:
            config_source = source_match.group(1)

    if adapter_mode == "link" and nested_relposix:
        effective_source = nested_relposix
    elif config_source and not is_framework_uri(config_source):
        effective_source = config_source
    else:
        effective_source = f"deltafuse://v{version}"

    if config_path.is_file():
        config_content = config_path.read_text(encoding="utf-8")
        dirty = False
        if not config_existed or force:
            if not re.search(r"(?m)^\s{2}version:\s*\S+\s*$", config_content):
                raise InstallationError(
                    "Cannot update framework version: .deltafuse/config.yaml has no indented version field."
                )
            config_content = re.sub(
                r"(?m)^(\s{2}version:\s*)\S+(\s*)$",
                f"\\g<1>{version}\\g<2>",
                config_content,
                count=1,
            )
            dirty = True
        if adapter_mode == "link" or (not config_existed or force):
            updated = _replace_config_source(config_content, effective_source)
            if updated != config_content:
                config_content = updated
                dirty = True
        if dirty:
            config_path.write_text(config_content, encoding="utf-8")

    lock_path.write_text(
        format_lock_yaml(
            version=version,
            source=effective_source,
            content_hash=content_hash,
            call_width=call_width,
            auto_accept_decisions=auto_accept,
        ),
        encoding="utf-8",
    )

    if not adapter_roots:
        adapter_roots = [".agents/skills", ".cursor/skills", ".gemini/skills"]

    skills_dir = None if bundle_assets is None else framework_root / 'skills'
    total_skills = 0
    actual_mode = adapter_mode
    for root_rel in adapter_roots:
        installed, used = install_adapter_skills(
            framework_root=framework_root,
            skills_dir=skills_dir,
            target_root=target_root,
            adapter_rel=root_rel,
            version=version,
            content_hash=content_hash,
            mode=adapter_mode,
            nested_relposix=nested_relposix,
        )
        total_skills += installed
        if used != "link":
            actual_mode = "copy"

    if adapter_mode == "link" and actual_mode == "copy":
        if requested_adapter_mode == "link":
            raise InstallationError(
                "Could not create skill symlinks. On Windows enable Developer Mode, or set adapters.mode to copy."
            )
        effective_source = f"deltafuse://v{version}"
        if config_path.is_file():
            config_path.write_text(
                _replace_config_source(config_path.read_text(encoding="utf-8"), effective_source),
                encoding="utf-8",
            )
        lock_path.write_text(
            format_lock_yaml(
                version=version,
                source=effective_source,
                content_hash=content_hash,
                call_width=call_width,
                auto_accept_decisions=auto_accept,
            ),
            encoding="utf-8",
        )

    sync_leash_hook(target_root, load_leash_mode(target_root, missing="off"))

    return InstallResult(
        target_dir=target_root,
        version=version,
        content_hash=content_hash,
        skills_installed=total_skills,
        adapter_mode=actual_mode,
        agents_md_mode=agents_md_mode,
        agents_md_target=agents_md_target,
    )
