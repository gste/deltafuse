"""Deterministic YAML and frontmatter codec for DeltaFuse artifacts (AW-04).

Defines stable key ordering, strict scalar quoting, literal multiline formatting,
pre-serialization round-trip equality validation, and metadata canonicalization opt-in.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
import yaml

from deltafuse.core.artifact_reader import strict_parse_yaml, strict_read_artifact, ArtifactReaderError


class ArtifactCodecError(Exception):
    """Raised when artifact encoding, round-trip validation, or formatting opt-in fails."""

    def __init__(self, message: str, *, code: str = "codec_error", preview_hash: str | None = None, hint: str | None = None):
        full_msg = f"[{code}] {message}"
        super().__init__(full_msg)
        self.message = message
        self.code = code
        self.preview_hash = preview_hash
        self.hint = hint


STANDARD_KEY_ORDERS: dict[str, list[str]] = {
    "task": [
        "id",
        "change",
        "slice",
        "kind",
        "status",
        "depends_on",
        "requirement_delta",
        "spec_refs",
        "design_ref",
        "allowed_paths",
        "forbidden_paths",
        "context_budget",
    ],
    "slice": [
        "id",
        "change",
        "title",
        "status",
        "primary_capability",
        "related_capabilities",
        "policies",
        "spec_refs",
        "claims",
        "depends_on",
        "context_budget",
    ],
    "spec-delta": ["change", "status", "slices", "added", "modified", "removed"],
    "routing": ["change", "claims"],
    "change": [
        "schema_version",
        "id",
        "title",
        "status",
        "framework",
        "intent",
        "risk",
        "source",
        "analysis",
        "deltas",
        "slices",
        "decisions",
        "tasks",
        "verification",
    ],
    "decision": [
        "id",
        "title",
        "kind",
        "status",
        "owner",
        "date",
        "change",
        "affects",
        "supersedes",
        "superseded_by",
    ],
    "evidence": [
        "schema_version",
        "change",
        "task",
        "phase",
        "timestamp",
        "command",
        "exit_code",
        "result",
        "failure_category",
        "summary",
        "changed_paths",
        "spec_status",
        "base_revision",
        "recorded_by",
        "recorded_sha256",
    ],
    "coverage": ["change", "claims"],
    "capability": ["schema_version", "domains", "policies"],
    "lock": ["schema_version", "framework"],
}

_RESERVED_STRINGS = {
    "yes", "no", "y", "n", "true", "false", "on", "off",
    "null", "~", "none", ".nan", ".inf", "-.inf", "+.inf", ".nan", ".inf"
}
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StrictYamlDumper(yaml.SafeDumper):
    """PyYAML SafeDumper enforcing deterministic scalar quoting and multiline style."""

    def represent_str(self, data: str) -> yaml.Node:
        lowered = data.lower()
        if (
            lowered in _RESERVED_STRINGS
            or _DATE_PATTERN.match(data)
            or (data.startswith("0") and len(data) > 1 and data.isdigit())
            or data.isdigit()
        ):
            return self.represent_scalar("tag:yaml.org,2002:str", data, style='"')
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return super().represent_str(data)


StrictYamlDumper.add_representer(str, StrictYamlDumper.represent_str)


def order_dict_keys(data: dict[str, Any], kind: str) -> dict[str, Any]:
    """Order mapping keys according to the kind's standard key order, followed by extension keys."""
    order = STANDARD_KEY_ORDERS.get(kind, [])
    ordered: dict[str, Any] = {}
    
    # First add standard keys in defined order if present in data
    for k in order:
        if k in data:
            ordered[k] = data[k]

    # Next add any remaining keys alphabetically
    for k in sorted(data.keys()):
        if k not in ordered:
            ordered[k] = data[k]

    return ordered


def strict_encode_yaml(data: dict[str, Any], kind: str = "task") -> str:
    """Encode a Python dictionary to canonical YAML string with pre-serialization roundtrip validation."""
    if not isinstance(data, dict):
        raise ArtifactCodecError("Metadata payload must be a mapping/dict")

    ordered_data = order_dict_keys(data, kind)

    try:
        dumped = yaml.dump(
            ordered_data,
            Dumper=StrictYamlDumper,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        if not dumped.endswith("\n"):
            dumped += "\n"
    except Exception as ex:
        raise ArtifactCodecError(f"YAML dump failed: {ex}") from ex

    # Pre-serialization round-trip equality check
    try:
        parsed = strict_parse_yaml(dumped)
    except ArtifactReaderError as ex:
        raise ArtifactCodecError(f"Pre-serialization round-trip parse failed: {ex}") from ex

    if parsed != ordered_data:
        raise ArtifactCodecError(
            "Pre-serialization round-trip equality check failed; emitted YAML changed semantic data values",
            code="roundtrip_mismatch",
        )

    return dumped


def serialize_artifact(
    metadata: dict[str, Any],
    body: str = "",
    *,
    kind: str = "task",
    existing_raw_content: str | None = None,
    canonicalize_metadata: bool = False,
) -> str:
    """Serialize metadata and body into canonical frontmatter Markdown text.

    If *existing_raw_content* is provided and differs in metadata formatting from canonical output,
    requires *canonicalize_metadata=True* to authorize re-formatting.
    """
    canonical_yaml = strict_encode_yaml(metadata, kind=kind)
    if canonical_yaml.endswith("\n"):
        candidate_output = f"---\n{canonical_yaml}---\n{body}"
    else:
        candidate_output = f"---\n{canonical_yaml}\n---\n{body}"

    if existing_raw_content is not None:
        try:
            old_res = strict_read_artifact(existing_raw_content)
            old_raw_meta = old_res.raw_metadata.strip()
        except ArtifactReaderError:
            old_raw_meta = None

        if old_raw_meta is not None and old_raw_meta != canonical_yaml.strip():
            if not canonicalize_metadata:
                preview_hash = "sha256:" + hashlib.sha256(candidate_output.encode("utf-8")).hexdigest()
                raise ArtifactCodecError(
                    "Existing metadata formatting differs from canonical output; explicit canonicalize_metadata=True required",
                    code="format_change_required",
                    preview_hash=preview_hash,
                    hint="Pass canonicalize_metadata=True in update request to authorize frontmatter formatting change",
                )

    return candidate_output
