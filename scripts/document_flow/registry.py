"""Load and validate the frozen J03 check registry."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping


STAGES = ("intake", "analyze", "specify", "decompose", "declare", "implement", "verify")
EXPECTED_TOTALS = MappingProxyType({
    **{f"stage.{stage}.correctness": 600 for stage in STAGES},
    **{f"stage.{stage}.discipline": 250 for stage in STAGES},
    "system.functional": 1800,
    "system.resilience": 600,
    "system.compatibility": 400,
    "system.efficiency": 200,
})
EXPECTED_CATEGORIES = frozenset(("correctness", "discipline", "system"))
OUTCOME_KEYS = frozenset(("check_id", "status", "evidence_refs", "failure_reason"))
OUTCOME_STATUSES = frozenset(("pass", "fail", "not_reached"))


class RegistryError(ValueError):
    """The registry or a registry-bound outcome is not trustworthy."""


@dataclass(frozen=True)
class Check:
    id: str
    category: str
    group: str
    points: int
    prerequisite_ids: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    hard_gate: bool


@dataclass(frozen=True)
class FrozenRegistry:
    version: str
    sha256: str
    checks: tuple[Check, ...]
    hard_gate_ids: frozenset[str]
    group_totals: Mapping[str, int]
    _canonical_document: Mapping[str, object]

    @property
    def stages(self) -> tuple[str, ...]:
        return STAGES

    def compute_sha256(self) -> str:
        return _content_hash(self._canonical_document)

    def validate_outcome_ids(self, outcome_ids: Iterable[str]) -> None:
        known = {check.id for check in self.checks}
        unknown = sorted(set(outcome_ids) - known)
        if unknown:
            raise RegistryError(f"unknown outcome check id: {', '.join(unknown)}")

    def validate_outcomes(self, outcomes: Iterable[Mapping[str, object]]) -> None:
        ids: list[str] = []
        for outcome in outcomes:
            extra = set(outcome) - OUTCOME_KEYS
            if extra:
                raise RegistryError("outcomes may contain only registry-bound observation fields")
            check_id = outcome.get("check_id")
            status = outcome.get("status")
            if not isinstance(check_id, str) or status not in OUTCOME_STATUSES:
                raise RegistryError("malformed outcome")
            ids.append(check_id)
        if len(ids) != len(set(ids)):
            raise RegistryError("duplicate outcome check id")
        self.validate_outcome_ids(ids)


def _content_hash(document: Mapping[str, object]) -> str:
    unsigned = dict(document)
    unsigned.pop("registry_sha256", None)
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _closed(row: Mapping[str, object], required: frozenset[str], context: str) -> None:
    keys = set(row)
    if keys != required:
        raise RegistryError(f"{context} fields differ: missing={sorted(required - keys)}, unknown={sorted(keys - required)}")


def load_registry(path: str | Path) -> FrozenRegistry:
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot decode registry: {exc}") from exc
    if not isinstance(document, dict):
        raise RegistryError("registry root must be an object")
    _closed(document, frozenset(("schema_version", "registry_version", "registry_sha256", "hard_gates", "checks")), "registry")
    if document["schema_version"] != 1 or document["registry_version"] != "J03-checks-1":
        raise RegistryError("unsupported registry version")
    rows = document["checks"]
    if not isinstance(rows, list):
        raise RegistryError("checks must be an array")
    checks: list[Check] = []
    ids: set[str] = set()
    required = frozenset(("id", "category", "group", "points", "prerequisite_ids", "evidence_sources", "hard_gate"))
    for raw in rows:
        if not isinstance(raw, dict):
            raise RegistryError("check row must be an object")
        _closed(raw, required, "check row")
        check_id = raw["id"]
        if not isinstance(check_id, str) or not check_id:
            raise RegistryError("check id must be a nonempty string")
        if check_id in ids:
            raise RegistryError(f"duplicate check id: {check_id}")
        ids.add(check_id)
        if raw["category"] not in EXPECTED_CATEGORIES:
            raise RegistryError(f"unknown category for {check_id}")
        if not isinstance(raw["points"], int) or isinstance(raw["points"], bool) or raw["points"] <= 0:
            raise RegistryError(f"invalid points for {check_id}")
        for field in ("prerequisite_ids", "evidence_sources"):
            if not isinstance(raw[field], list) or not all(isinstance(item, str) and item for item in raw[field]):
                raise RegistryError(f"invalid {field} for {check_id}")
            if len(raw[field]) != len(set(raw[field])):
                raise RegistryError(f"duplicate {field} for {check_id}")
        if not raw["evidence_sources"]:
            raise RegistryError(f"missing evidence source for {check_id}")
        if not isinstance(raw["hard_gate"], bool):
            raise RegistryError(f"invalid hard_gate for {check_id}")
        checks.append(Check(check_id, raw["category"], raw["group"], raw["points"], tuple(raw["prerequisite_ids"]), tuple(raw["evidence_sources"]), raw["hard_gate"]))
    categories = {check.category for check in checks}
    missing_categories = EXPECTED_CATEGORIES - categories
    if missing_categories:
        raise RegistryError(f"missing category: {', '.join(sorted(missing_categories))}")
    for check in checks:
        unknown = set(check.prerequisite_ids) - ids
        if unknown:
            raise RegistryError(f"unknown prerequisite check id for {check.id}: {', '.join(sorted(unknown))}")
    totals = {group: sum(check.points for check in checks if check.group == group) for group in EXPECTED_TOTALS}
    unknown_groups = {check.group for check in checks} - set(EXPECTED_TOTALS)
    if unknown_groups or totals != dict(EXPECTED_TOTALS):
        raise RegistryError(f"group total mismatch: actual={totals}, expected={dict(EXPECTED_TOTALS)}, unknown={sorted(unknown_groups)}")
    hard_gates = document["hard_gates"]
    if not isinstance(hard_gates, list) or not all(isinstance(item, str) and item for item in hard_gates):
        raise RegistryError("hard_gates must be a nonempty string array")
    if not hard_gates or len(hard_gates) != len(set(hard_gates)):
        raise RegistryError("hard gates must be independently identifiable")
    declared_hash = document["registry_sha256"]
    actual_hash = _content_hash(document)
    if declared_hash != actual_hash:
        raise RegistryError(f"registry hash mismatch: declared={declared_hash}, actual={actual_hash}")
    return FrozenRegistry(document["registry_version"], actual_hash, tuple(checks), frozenset(hard_gates), MappingProxyType(totals), MappingProxyType(document))


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
