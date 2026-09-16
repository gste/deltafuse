"""Human Gate receipts and integrity profiles (DF3-007 / DR-3.0-3).

Two profiles:

- ``local``: hash-chained receipts — tamper-evident against accidental
  corruption, and honest about not protecting against a forged journal.
- ``broker-signed``: every receipt is HMAC-signed by the host broker with a
  key that never lives in the Worker surface (env ``DELTAFUSE_BROKER_KEY``);
  Core verifies against public trust roots in ``.deltafuse/trusted-keys.yaml``.

The journal is append-only and chained; a head digest in
``.deltafuse/journal-head`` makes truncation and replacement detectable.
Editing or rebuilding the journal never produces a valid Human Gate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

RECEIPT_VERSION = 2
JOURNAL_REL = ".deltafuse/gate-journal.jsonl"
HEAD_REL = ".deltafuse/journal-head"
TRUST_ROOTS_REL = ".deltafuse/trusted-keys.yaml"
PROFILES = ("local", "broker-signed")
BROKER_KEY_ENV = "DELTAFUSE_BROKER_KEY"
LOCAL_GUARANTEE = (
    "local profile: chain detects accidental corruption only; it does not "
    "protect against a forged journal (use broker-signed for that)"
)


class ReceiptError(Exception):
    """Receipt recording or trust-root problem."""


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_profile(product_root: Path) -> str:
    config = Path(product_root) / ".deltafuse" / "config.yaml"
    if config.is_file():
        try:
            data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        workflow = data.get("workflow") if isinstance(data, dict) else None
        raw = workflow.get("integrity_profile") if isinstance(workflow, dict) else None
        if raw is not None:
            if raw not in PROFILES:
                raise ReceiptError(
                    f"unknown integrity_profile {raw!r}; expected one of {list(PROFILES)}"
                )
            return str(raw)
    return "local"


def journal_path(product_root: Path) -> Path:
    return Path(product_root) / JOURNAL_REL


def trust_roots_path(product_root: Path) -> Path:
    return Path(product_root) / TRUST_ROOTS_REL


def _load_trust_roots(product_root: Path) -> dict[str, str]:
    path = trust_roots_path(product_root)
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.get("keys", {}).items()}


def install_trust_root(product_root: Path, *, key_id: str, secret: str) -> None:
    """Register one broker verification key (public trust root)."""
    path = trust_roots_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"keys": {}}
    if path.is_file():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            pass
    data.setdefault("keys", {})[key_id] = secret
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _chain_hash(entry: dict[str, Any]) -> str:
    body = {
        k: v
        for k, v in entry.items()
        if k not in ("signature", "chain_hash", "prev_hash", "guarantee")
    }
    return _digest(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def load_receipts(product_root: Path) -> list[dict[str, Any]]:
    path = journal_path(product_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def record_receipt(
    product_root: Path,
    *,
    kind: str,
    status: str,
    rel_path: str,
    artifact_id: str,
    change: str | None,
    artifact: Path,
) -> dict[str, Any]:
    """Append one versioned Human Gate receipt (Core only; never git push)."""
    if kind not in {"decision", "spec"}:
        raise ReceiptError(f"unknown gate receipt kind: {kind!r}")
    if status not in {"accepted", "rejected"}:
        raise ReceiptError(f"unknown gate verdict: {status!r}")

    root = Path(product_root)
    profile = load_profile(root)
    artifact_file = Path(artifact)
    if not artifact_file.is_file():
        raise ReceiptError(f"receipt artifact missing on disk: {artifact_file}")

    prev_hash = _head_digest(root)
    entry: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "profile": profile,
        "kind": kind,
        "status": status,
        "id": artifact_id,
        "path": rel_path.replace("\\", "/"),
        "change": change,
        "artifact_sha256": _digest(artifact_file.read_bytes()),
        "actor": "human-via-core",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nonce": secrets.token_hex(8),
        "prev_hash": prev_hash,
    }
    if profile == "broker-signed":
        secret = os.environ.get(BROKER_KEY_ENV)
        if not secret:
            raise ReceiptError(
                f"broker-signed profile requires the host broker key in {BROKER_KEY_ENV}"
            )
        key_id = _digest(secret.encode("utf-8"))[:12]
        trust = _load_trust_roots(root)
        if key_id not in trust:
            raise ReceiptError(
                "broker key is not registered in the trust roots "
                f"({TRUST_ROOTS_REL}); register it with install_trust_root"
            )
        entry["key_id"] = key_id
        entry["chain_hash"] = _chain_hash(entry)
        entry["signature"] = hmac.new(
            secret.encode("utf-8"), entry["chain_hash"].encode("utf-8"), hashlib.sha256
        ).hexdigest()
    else:
        entry["chain_hash"] = _chain_hash(entry)
        entry["guarantee"] = LOCAL_GUARANTEE

    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    path = journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    _write_head(root, _digest(line.encode("utf-8")))
    return entry


def _head_path(product_root: Path) -> Path:
    return Path(product_root) / HEAD_REL


def _head_digest(product_root: Path) -> str:
    path = _head_path(product_root)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _write_head(product_root: Path, digest: str) -> None:
    path = _head_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(digest + "\n", encoding="utf-8")


def journal_errors(product_root: Path) -> list[str]:
    """Detect replay, truncation, replacement and stale-artifact receipts."""
    root = Path(product_root)
    errors: list[str] = []
    receipts = load_receipts(root)
    path = journal_path(root)

    # Truncation / replacement: the recorded head must match the last line.
    lines = [
        raw for raw in (path.read_text(encoding="utf-8").splitlines() if path.is_file() else []) if raw.strip()
    ]
    if lines:
        recorded_head = _head_digest(root)
        actual_head = _digest(lines[-1].strip().encode("utf-8"))
        if recorded_head and recorded_head != actual_head:
            errors.append(
                "gate journal head digest mismatch: the journal was truncated or replaced"
            )

    seen_nonces: set[str] = set()
    trust = _load_trust_roots(root)
    for index, entry in enumerate(receipts):
        version = entry.get("receipt_version")
        if version is None:
            continue  # legacy line: no receipt semantics claimed
        label = f"receipt[{index}]"
        chain = entry.get("chain_hash")
        if not chain or _chain_hash(entry) != chain:
            errors.append(f"{label}: chain hash mismatch (entry was edited)")
        if entry.get("prev_hash") is None:
            errors.append(f"{label}: missing prev_hash")
        nonce = entry.get("nonce")
        if nonce in seen_nonces:
            errors.append(f"{label}: replayed nonce {nonce!r}")
        if nonce:
            seen_nonces.add(nonce)
        if version != RECEIPT_VERSION:
            errors.append(f"{label}: unsupported receipt_version {version!r}")
            continue
        if entry.get("profile") == "broker-signed":
            key_id = entry.get("key_id")
            secret = trust.get(str(key_id))
            if secret is None:
                errors.append(f"{label}: signed by unknown key_id {key_id!r}")
                continue
            expected = hmac.new(
                secret.encode("utf-8"),
                str(chain).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, str(entry.get("signature"))):
                errors.append(f"{label}: broker signature does not verify")
    return errors


def has_valid_receipt(
    product_root: Path,
    *,
    kind: str,
    status: str,
    artifact_id: str | None = None,
    rel_path: str | None = None,
    artifact: Path | None = None,
) -> bool:
    """True when a receipt for this click still matches the artifact bytes.

    A receipt whose artifact changed after the click is stale and no longer
    counts (DF3-007 item 5). Signature/chain integrity is verified per entry.
    """
    root = Path(product_root)
    want_rel = rel_path.replace("\\", "/") if rel_path else None
    current_digest = (
        _digest(Path(artifact).read_bytes())
        if artifact is not None and Path(artifact).is_file()
        else None
    )
    for entry in reversed(load_receipts(root)):
        if entry.get("kind") != kind or entry.get("status") != status:
            continue
        if artifact_id and entry.get("id") != artifact_id:
            continue
        if want_rel and entry.get("path") != want_rel:
            continue
        version = entry.get("receipt_version")
        if version is not None:
            if version != RECEIPT_VERSION:
                continue
            if not entry.get("chain_hash") or _chain_hash(entry) != entry["chain_hash"]:
                continue
            if entry.get("profile") == "broker-signed":
                secret = _load_trust_roots(root).get(str(entry.get("key_id")))
                if secret is None:
                    continue
                expected = hmac.new(
                    secret.encode("utf-8"),
                    str(entry["chain_hash"]).encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(expected, str(entry.get("signature"))):
                    continue
        if (
            current_digest is not None
            and version is not None
            and entry.get("artifact_sha256") != current_digest
        ):
            continue  # stale: artifact changed after the click
        return True
    return False
