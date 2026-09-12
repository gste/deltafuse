"""Deterministic Change scaffolding (DF3-005 / C-03).

``deltafuse new <change-id>`` creates a minimal, schema-valid Change package
so Workers and humans stop hand-crafting YAML. Scaffolding never closes
Intake: the package carries no claims and stays in ``normalized`` status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

VALID_ROUTES = ("code", "docs", "ops")
CHANGE_ID_PATTERN = r"^CHG-[0-9]{3,}(-[a-z0-9-]+)?$"


class ScaffoldError(Exception):
    """Invalid or conflicting scaffolding request."""


def _change_yaml(change_id: str, route: str, created: str) -> dict[str, Any]:
    return {
        "id": change_id,
        "title": "",
        "intent": "feature",
        "route": route,
        "status": "normalized",
        "created": created,
    }


def scaffold_change(
    product_root: Path | str,
    change_id: str,
    *,
    route: str = "code",
    title: str = "",
) -> Path:
    """Create ``docs/changes/<change-id>/`` with minimal artifacts."""
    change_id = (change_id or "").strip()
    if not _valid_change_id(change_id):
        raise ScaffoldError(
            f"Change id '{change_id}' must match CHG-<digits>[-slug], e.g. CHG-101-auth"
        )
    if route not in VALID_ROUTES:
        raise ScaffoldError(f"route must be one of {list(VALID_ROUTES)}")

    root = Path(product_root).resolve()
    change_dir = root / "docs" / "changes" / change_id
    if change_dir.exists():
        raise ScaffoldError(f"Change directory already exists: {change_dir}")
    archive = root / "docs" / "archive" / "changes"
    if archive.is_dir() and any(p.name.endswith(f"-{change_id}") for p in archive.iterdir() if p.is_dir()):
        raise ScaffoldError(f"Change id '{change_id}' was already archived")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _change_yaml(change_id, route, created)
    if title:
        data["title"] = title

    (change_dir / "slices").mkdir(parents=True)
    (change_dir / "tasks").mkdir()
    (change_dir / "evidence").mkdir()

    (change_dir / "change.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (change_dir / "request.md").write_text(
        f"---\nchange: {change_id}\nstatus: drafted\nslices: []\n---\n\n"
        f"# {title or change_id}\n\n"
        "<!-- Raw intent. Claims stay unverified; Intake is not closed by scaffolding. -->\n",
        encoding="utf-8",
    )
    return change_dir


def _valid_change_id(change_id: str) -> bool:
    import re

    return re.match(CHANGE_ID_PATTERN, change_id) is not None
