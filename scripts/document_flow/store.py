"""Host-owned, append-only evidence storage for the document-flow benchmark."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import canonical_bytes, content_hash, with_self_hash


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class IntegrityError(ValueError):
    """Raised when durable evidence violates its integrity contract."""


@dataclass(frozen=True)
class EvidenceRef:
    key: str
    sha256: str
    media_type: str
    byte_length: int
    producer_event_id: str
    run_id: str
    root_id: str


@dataclass(frozen=True)
class Seal:
    manifest_bytes: bytes
    mac_sha256: str


@dataclass(frozen=True)
class Verification:
    manifest_sha256: str
    object_count: int
    event_count: int
    final_count: int


class EvidenceStore:
    def __init__(self, root: Path, run_id: str, root_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self.root_id = root_id

    @classmethod
    def create(cls, root: Path | str, run_id: str, root_id: str) -> "EvidenceStore":
        if not _ID.fullmatch(run_id) or not _ID.fullmatch(root_id):
            raise IntegrityError("unsafe run/root identity")
        path = Path(root)
        try:
            path.mkdir(parents=True, exist_ok=False)
            (path / "objects").mkdir()
            (path / "events").mkdir()
        except FileExistsError as exc:
            raise IntegrityError("evidence root already exists") from exc
        return cls(path, run_id, root_id)

    @property
    def events_path(self) -> Path:
        return self.root / "events" / "host.jsonl"

    def put(self, data: bytes, media_type: str, producer_event_id: str) -> EvidenceRef:
        if not isinstance(data, bytes):
            raise IntegrityError("evidence payload must be bytes")
        if not media_type or not producer_event_id:
            raise IntegrityError("evidence metadata must be non-empty")
        digest = hashlib.sha256(data).hexdigest()
        key = f"objects/{digest}"
        destination = self.root / key
        self._publish(destination, data, allow_identical=True)
        return EvidenceRef(key, digest, media_type, len(data), producer_event_id, self.run_id, self.root_id)

    def resolve(self, ref: EvidenceRef) -> bytes:
        if ref.run_id != self.run_id or ref.root_id != self.root_id:
            raise IntegrityError("run/root identity mismatch")
        if not re.fullmatch(r"objects/[0-9a-f]{64}", ref.key) or ref.sha256 != ref.key.removeprefix("objects/"):
            raise IntegrityError("unsafe evidence key")
        path = self.root / PurePosixPath(ref.key)
        if self._has_link_boundary(path):
            raise IntegrityError("link boundary in evidence path")
        if not path.is_file():
            raise IntegrityError("missing object")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != ref.sha256 or len(data) != ref.byte_length:
            raise IntegrityError("object content mismatch")
        return data

    def append_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        rows = self._read_events()
        if any(field in event for field in ("sequence", "previous_hash", "event_hash")):
            raise IntegrityError("host event fields are reserved")
        row = dict(event)
        row["sequence"] = len(rows)
        row["previous_hash"] = rows[-1]["event_hash"] if rows else None
        row["event_hash"] = content_hash(row, exclude=("event_hash",))
        with self.events_path.open("ab") as stream:
            stream.write(canonical_bytes(row) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        return row

    def finalize_json(self, relative_path: str, value: Mapping[str, Any]) -> dict[str, Any]:
        path = self._final_path(relative_path)
        result = with_self_hash(value, "report_hash")
        self._publish(path, canonical_bytes(result), allow_identical=False)
        return result

    def recover(self) -> None:
        for path in self.root.rglob(".tmp-*"):
            if self._has_link_boundary(path):
                raise IntegrityError("link boundary in recovery path")
            if path.is_file():
                path.unlink()

    def seal(self, key: bytes) -> Seal:
        self._check_key(key)
        manifest = self._snapshot_manifest()
        encoded = canonical_bytes(manifest)
        return Seal(encoded, hmac.new(key, encoded, hashlib.sha256).hexdigest())

    def verify(
        self,
        seal: Seal,
        key: bytes,
        semantic_validators: Mapping[str, Callable[[Mapping[str, Any]], bool]] | None = None,
    ) -> Verification:
        self._check_key(key)
        expected_mac = hmac.new(key, seal.manifest_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_mac, seal.mac_sha256):
            raise IntegrityError("seal authentication failed")
        try:
            saved = self._decode_canonical(seal.manifest_bytes)
        except IntegrityError as exc:
            raise IntegrityError("seal authentication payload invalid") from exc
        current = self._snapshot_manifest()
        if canonical_bytes(saved) != canonical_bytes(current):
            raise IntegrityError("sealed manifest mismatch")
        for relative, validator in (semantic_validators or {}).items():
            path = self._final_path(relative)
            try:
                value = self._decode_canonical(path.read_bytes())
                valid = validator(value)
            except Exception as exc:
                raise IntegrityError(f"semantic recomputation mismatch: {relative}") from exc
            if not valid:
                raise IntegrityError(f"semantic recomputation mismatch: {relative}")
        return Verification(
            hashlib.sha256(seal.manifest_bytes).hexdigest(),
            len(current["objects"]),
            current["events"]["count"],
            len(current["finals"]),
        )

    def _snapshot_manifest(self) -> dict[str, Any]:
        rows = self._read_events()
        objects: dict[str, str] = {}
        for path in sorted((self.root / "objects").iterdir(), key=lambda item: item.name):
            if path.name.startswith(".tmp-"):
                continue
            if self._has_link_boundary(path) or not path.is_file() or not _HASH.fullmatch(path.name):
                raise IntegrityError("invalid object entry")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != path.name:
                raise IntegrityError("object content mismatch")
            objects[f"objects/{path.name}"] = digest
        finals: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path == self.events_path or "objects" in path.relative_to(self.root).parts:
                continue
            if path.name.startswith(".tmp-"):
                continue
            if self._has_link_boundary(path):
                raise IntegrityError("link boundary in final path")
            relative = path.relative_to(self.root).as_posix()
            data = path.read_bytes()
            if path.suffix == ".json":
                value = self._decode_canonical(data)
                if not isinstance(value, dict) or value.get("report_hash") != content_hash(value, exclude=("report_hash",)):
                    raise IntegrityError(f"final self-hash mismatch: {relative}")
            finals[relative] = hashlib.sha256(data).hexdigest()
        event_data = self.events_path.read_bytes() if self.events_path.exists() else b""
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "root_id": self.root_id,
            "objects": objects,
            "events": {
                "sha256": hashlib.sha256(event_data).hexdigest(),
                "count": len(rows),
                "last_hash": rows[-1]["event_hash"] if rows else None,
            },
            "finals": finals,
        }

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        data = self.events_path.read_bytes()
        if data and not data.endswith(b"\n"):
            raise IntegrityError("truncated event log")
        rows: list[dict[str, Any]] = []
        previous = None
        for sequence, line in enumerate(data.splitlines()):
            value = self._decode_canonical(line)
            if not isinstance(value, dict):
                raise IntegrityError("event must be an object")
            if value.get("sequence") != sequence or value.get("previous_hash") != previous:
                raise IntegrityError("event chain mismatch")
            digest = content_hash(value, exclude=("event_hash",))
            if value.get("event_hash") != digest:
                raise IntegrityError("event hash mismatch")
            rows.append(value)
            previous = digest
        return rows

    def _decode_canonical(self, data: bytes) -> Any:
        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result:
                    raise IntegrityError("duplicate JSON key")
                result[key] = value
            return result

        try:
            value = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=pairs,
                parse_float=lambda _value: (_ for _ in ()).throw(IntegrityError("float in canonical JSON")),
                parse_constant=lambda _value: (_ for _ in ()).throw(IntegrityError("constant in canonical JSON")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IntegrityError("invalid canonical JSON") from exc
        if canonical_bytes(value) != data:
            raise IntegrityError("non-canonical JSON")
        return value

    def _final_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or "\\" in relative_path or re.match(r"^[A-Za-z]:", relative_path):
            raise IntegrityError("unsafe final path")
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
            raise IntegrityError("unsafe final path")
        if pure.parts[0] not in {"reports", "stages", "visits"} or not relative_path.endswith(".json"):
            raise IntegrityError("unsafe final path")
        path = self.root.joinpath(*pure.parts)
        if self._has_link_boundary(path):
            raise IntegrityError("link boundary in final path")
        return path

    def _has_link_boundary(self, path: Path) -> bool:
        current = self.root
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return True
        for part in relative.parts:
            current = current / part
            if current.exists() and (current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction())):
                return True
        return False

    def _publish(self, destination: Path, data: bytes, *, allow_identical: bool) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self._has_link_boundary(destination.parent):
            raise IntegrityError("link boundary in publication path")
        temporary = destination.parent / f".tmp-{secrets.token_hex(12)}"
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                if allow_identical and destination.is_file() and destination.read_bytes() == data:
                    return
                raise IntegrityError("already finalized") from exc
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _check_key(key: bytes) -> None:
        if not isinstance(key, bytes) or not key:
            raise IntegrityError("seal key must be non-empty bytes")
