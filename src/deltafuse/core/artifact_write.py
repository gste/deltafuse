"""`deltafuse artifact write`: the Worker's one way to write a structural artifact.

Roadmap item 1: the model writes prose, the Core and the Artifact Writer write
structure. `create` and `update` stay for exact control, but a Worker would have
to choose between them and compute the target's sha256 for an update - two
decisions and a hash a weak model has no business making. `write` takes the
fields and the prose body: no file yet, it creates; a file, it updates exactly
the fields given, with the expected sha256 read by the Core under its lock.

Fields the Core can derive are defaulted here, not asked of the model: a task's
`context_budget` is the product's `context` budget from `.deltafuse/config.yaml`,
and a new task or slice is added to the `change.yaml` index by the Core.

`spec-delta.md` grows one slice per Specify step, so its lists merge: the Worker
names only this slice's entries and its prose is appended, never replaced.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core.artifact_policy import create_authorization_context
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError

ENVELOPE_KEYS = frozenset({"identity", "target", "fields", "body", "request_id"})
MERGED_LISTS = {"spec-delta": ("slices", "added", "modified", "removed")}
INDEXED_KINDS = ("task", "slice", "decision")
DECISION_ID = re.compile(r"^DEC-([0-9]{4,})")
CHANGE_ID = re.compile(r"^CHG-[0-9]{3,}(-[a-z0-9-]+)?$")


def _change_id(change_dir: Path) -> str:
    change_file = change_dir / "change.yaml"
    try:
        data = yaml.safe_load(change_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as ex:
        raise ArtifactServiceError(
            f"{change_file.as_posix()} cannot be read: {ex}", code="missing_change_authority"
        ) from ex
    cid = data.get("id") if isinstance(data, dict) else None
    if not isinstance(cid, str) or not CHANGE_ID.match(cid):
        raise ArtifactServiceError(
            f"change.yaml has no valid Change id: {cid!r}", code="missing_change_authority"
        )
    return cid


def _product_budget(product_root: Path) -> dict[str, int]:
    from deltafuse.core.context import DEFAULT_TASK_BUDGET

    budget = dict(DEFAULT_TASK_BUDGET)
    try:
        data = yaml.safe_load((product_root / ".deltafuse" / "config.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return budget
    context = data.get("context") if isinstance(data, dict) else None
    if isinstance(context, dict):
        for key in ("max_tokens", "max_files"):
            if isinstance(context.get(key), int):
                budget[key] = context[key]
    return budget


def split_envelope(raw: dict[str, Any]) -> tuple[str | None, str | None, dict[str, Any], str | None]:
    """(identity, target, fields, body) from `{"fields": {...}}` or a flat mapping."""
    if not isinstance(raw, dict):
        raise ArtifactServiceError("input must be a JSON object", code="invalid_envelope")
    fields = raw.get("fields")
    if fields is None:
        fields = {k: v for k, v in raw.items() if k not in ENVELOPE_KEYS}
    if not isinstance(fields, dict):
        raise ArtifactServiceError("'fields' must be a JSON object", code="invalid_envelope")
    body = raw.get("body")
    if body is not None and not isinstance(body, str):
        raise ArtifactServiceError("'body' must be a string of prose", code="invalid_envelope")
    identity = raw.get("identity")
    target = raw.get("target")
    return (
        str(identity) if identity else None,
        str(target) if target else None,
        dict(fields),
        body,
    )


def write_artifact(
    change_dir: Path | str,
    kind: str,
    *,
    identity: str | None = None,
    target: str | None = None,
    fields: dict[str, Any],
    body: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create or update one artifact of a Change through the Artifact Writer.

    Returns the Writer's receipt plus `"operation": "create" | "update"`.
    """
    from deltafuse.core.artifact_lock import resolve_product_root

    change_path = Path(change_dir).resolve()
    if not identity and not target and kind != "decision":
        raise ArtifactServiceError(
            "name the artifact: 'identity' (e.g. TASK-001, SLICE-01) or 'target' (a path in the Change)",
            code="required_property_missing",
        )
    root = resolve_product_root(change_path)
    auth = create_authorization_context(
        actor="worker", work_item="CLI", product_root=root, change_id=_change_id(change_path)
    )
    service = ArtifactService(product_root=root, change_dir=change_path, auth_context=auth)
    if kind == "decision":
        identity, path = _decision_target(root, identity, target)
    else:
        path = service._resolve_target_path(kind, target or identity)

    if path.is_file():
        descriptor = service.registry.get_descriptor(kind)
        core_owned = set(descriptor.get("core_owned_fields") or [])
        current = _current_metadata(path)
        if kind == "decision" and current.get("status") != "proposed":
            raise ArtifactServiceError(
                f"{path.name} is {current.get('status')!r}: a decided Decision is the human's; "
                "propose a new one that names it in 'supersedes'",
                code="policy_denied",
            )
        patch_fields = {}
        for key, value in fields.items():
            if key in core_owned and current.get(key) == value:
                continue  # restating a Core-owned value (a task's slice) is not a change
            if key in MERGED_LISTS.get(kind, ()) and isinstance(value, list):
                merged = list(current.get(key) or [])
                merged += [item for item in value if item not in merged]
                value = merged
            patch_fields[key] = value
        if body is not None and kind in MERGED_LISTS:
            old_body = _current_body(path)
            body = (old_body.rstrip() + "\n\n" + body.strip() + "\n") if old_body.strip() else body
        patch = {"set": [{"path": f"/{key}", "value": value} for key, value in patch_fields.items()]}
        receipt = service.update(
            kind=kind,
            target=path,
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            patch=patch,
            body_replacement=body,
            request_id=request_id,
        )
        return {**receipt, "operation": "update"}

    if not identity:
        raise ArtifactServiceError(
            f"{path.as_posix()} does not exist; creating it needs 'identity'",
            code="target_not_found",
        )
    payload = dict(fields)
    if kind == "task" and "context_budget" not in payload:
        payload["context_budget"] = _product_budget(root)
    if kind == "decision":
        from datetime import date

        # The human owner answers it; the Worker only proposes (decide.py).
        payload.setdefault("owner", "human")
        payload.setdefault("date", date.today().isoformat())
    receipt = service.create(
        kind=kind, identity=identity, semantic_payload=payload, body=body or "", request_id=request_id
    )
    if kind in INDEXED_KINDS:
        from deltafuse.core.scaffold import update_change_child_index

        update_change_child_index(change_path, kind, identity)
    return {**receipt, "operation": "create"}


def _decision_target(root: Path, identity: str | None, target: str | None) -> tuple[str, Path]:
    """(DEC id, file) for a Decision: an existing one by id or path, or the next free id.

    A Decision's id is the Core's: the Worker may leave it out and the Core
    allocates the next `DEC-NNNN` after those in `docs/decisions/`.
    """
    folder = root / "docs" / "decisions"
    if target:
        path = (root / target).resolve() if not Path(target).is_absolute() else Path(target)
        match = DECISION_ID.match(path.name)
        if not match:
            raise ArtifactServiceError(f"{target} is not a DEC-NNNN file", code="invalid_envelope")
        return path.stem, path
    if identity and identity.lower() != "new":
        if not DECISION_ID.match(identity):
            raise ArtifactServiceError(
                f"Decision identity must be DEC-NNNN or omitted, got {identity!r}", code="invalid_envelope"
            )
        existing = sorted(folder.glob(f"{identity}*.md")) if folder.is_dir() else []
        exact = [p for p in existing if p.stem == identity or p.stem.startswith(identity + "-")]
        return identity, exact[0] if exact else folder / f"{identity}.md"
    numbers = [
        int(m.group(1)) for m in (DECISION_ID.match(p.name) for p in folder.glob("DEC-*.md")) if m
    ] if folder.is_dir() else []
    return f"DEC-{max(numbers + [0]) + 1:04d}", folder / f"DEC-{max(numbers + [0]) + 1:04d}.md"


def _current_body(path: Path) -> str:
    from deltafuse.core.frontmatter import parse_frontmatter

    _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return body or ""


def _current_metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    from deltafuse.core.frontmatter import parse_frontmatter

    meta, _ = parse_frontmatter(text)
    return meta if isinstance(meta, dict) else {}
