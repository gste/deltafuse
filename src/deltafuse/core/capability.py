"""Proposing a capability the catalog does not have yet (q8 decision).

A Change that needs a new capability could not be analysed at all. Routing
refuses a name the catalog does not hold, and the catalog is writable only in
Specify - which comes after the `analyzed` gate. So the only legal move in
Analyze was to route into an existing capability, which is what M02 run 1 did
before failing every downstream check (runs-2026-09-23).

The catalog stays the human's. What changes is when the question is asked: the
Worker proposes an entry with `status: draft`, routing accepts a draft, and the
`specified` Human Gate - where the human already signs the spec-delta - refuses
to close while a capability this Change routes into is still a draft. The
human's acceptance is what makes it `active`; `converged` checks again, which
is the catalog rule q6 was holding.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.artifact_storage import atomic_replace
from deltafuse.core.integrity import load_capability_catalog, lookup_capability
from deltafuse.core.transitions import append_receipt

CATALOG_REL = "docs/spec/_capabilities.yaml"
DRAFT = "draft"


class CapabilityError(Exception):
    """The proposal cannot be recorded; the message is for the Worker."""


def catalog_path(product_root: Path | str) -> Path:
    return Path(product_root) / "docs" / "spec" / "_capabilities.yaml"


def draft_capabilities(product_root: Path | str, names: list[str]) -> list[str]:
    """Which of `names` the catalog still holds as a draft."""
    catalog, errors = load_capability_catalog(Path(product_root))
    if errors or not isinstance(catalog, dict):
        return []
    out = []
    for name in names:
        cap = lookup_capability(catalog, name)
        if isinstance(cap, dict) and str(cap.get("status") or "").lower() == DRAFT:
            out.append(name)
    return sorted(set(out))


def propose_capability(
    product_root: Path | str,
    name: str,
    *,
    summary: str,
    spec: str,
    code_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Add `<domain>.<capability>` to the catalog as a draft. Returns what it wrote.

    The spec file it names does not exist yet: Specify writes it. That is why
    the draft status exists - the entry is a claim about what this Change will
    add, not a finished capability.
    """
    root = Path(product_root)
    if "." not in name or name.startswith(".") or name.endswith("."):
        raise CapabilityError(f"capability name must be '<domain>.<capability>', got {name!r}")
    domain, cap_name = name.split(".", 1)
    if "." in cap_name:
        raise CapabilityError(f"capability name has more than one dot: {name!r}")
    if not summary.strip():
        raise CapabilityError("a proposed capability needs a one-line summary")
    spec_rel = spec.replace("\\", "/").strip().lstrip("/")
    if not spec_rel.startswith("docs/spec/") or not spec_rel.endswith(".md"):
        raise CapabilityError(f"spec must be a markdown file under docs/spec/, got {spec!r}")

    path = catalog_path(root)
    if not path.is_file():
        raise CapabilityError(f"{CATALOG_REL} is missing: this product has no catalog to add to")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as ex:
        raise CapabilityError(f"{CATALOG_REL} cannot be read: {ex}") from ex
    if not isinstance(data, dict):
        raise CapabilityError(f"{CATALOG_REL} must be a mapping")

    domains = data.setdefault("domains", {})
    if not isinstance(domains, dict):
        raise CapabilityError(f"{CATALOG_REL}: 'domains' must be a mapping")
    node = domains.setdefault(domain, {"summary": domain, "capabilities": {}})
    if not isinstance(node, dict):
        raise CapabilityError(f"{CATALOG_REL}: domain {domain!r} must be a mapping")
    caps = node.setdefault("capabilities", {})
    if not isinstance(caps, dict):
        raise CapabilityError(f"{CATALOG_REL}: domain {domain!r} has no capability mapping")
    if cap_name in caps:
        status = (caps[cap_name] or {}).get("status") if isinstance(caps[cap_name], dict) else None
        raise CapabilityError(
            f"capability {name!r} already exists in the catalog (status {status!r}); "
            "route into it instead of proposing it again"
        )

    entry: dict[str, Any] = {
        "summary": summary.strip(),
        "spec": [spec_rel],
        "status": DRAFT,
        "type": "supporting",
    }
    if code_roots:
        entry["code_roots"] = [r.replace("\\", "/").strip().lstrip("/") for r in code_roots if r.strip()]
    caps[cap_name] = entry

    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8")
    # The catalog is structure, so the leash refuses bytes no writer vouches
    # for. The receipt carries the digest the Core is about to write, the way
    # `deltafuse state` does for a task file.
    digest = hashlib.sha256(rendered).hexdigest()
    append_receipt(
        root,
        {
            "kind": "capability-draft",
            # `path` is the key the leash reads a Core receipt's target from.
            "path": CATALOG_REL,
            "capability": name,
            "status": DRAFT,
            "spec": spec_rel,
            "sha256": digest,
        },
    )
    atomic_replace(path, rendered)
    return {"capability": name, "status": DRAFT, "spec": spec_rel, "path": CATALOG_REL}
