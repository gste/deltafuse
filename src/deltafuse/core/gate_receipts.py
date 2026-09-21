"""Human Gate receipt chain: the single writer and reader of `.deltafuse/gate-journal.jsonl`.

Not to be confused with `artifact_transactions.py`, which owns receipts for artifact
writes (idempotency, crash recovery). This module owns receipts for human gate
verdicts (decision / spec accept-reject), hash-chained and optionally broker-signed.

Absorbed the legacy `gate_journal.py` (DF3-007 supersedes it): that module declared
the same JOURNAL_REL and journal_path, duplicated the reader verbatim, and its
writer `append_click` was dead code.

Signed receipts use Ed25519: the repository holds only public keys
(`.deltafuse/trusted-keys.yaml`), the human's private key stays outside the
Worker's reach. The earlier broker-signed profile used HMAC with the secret in
that same file, so anyone who could read the repository - the Worker - could
forge a signature; such receipts and trust roots are no longer trusted. Once
trust roots exist, every later receipt must be signed whatever the configured
profile, so editing `config.yaml` does not switch signing off.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from deltafuse.core import ed25519

RECEIPT_VERSION = 2
JOURNAL_REL = ".deltafuse/gate-journal.jsonl"
HEAD_REL = ".deltafuse/journal-head"
TRUST_ROOTS_REL = ".deltafuse/trusted-keys.yaml"
PROFILES = ("local", "broker-signed")
TERMINAL_STATUSES = frozenset({"accepted", "rejected"})
BROKER_KEY_ENV = "DELTAFUSE_BROKER_KEY"
BROKER_KEY_FILE_ENV = "DELTAFUSE_BROKER_KEY_FILE"
SIG_ALG = "ed25519"
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


def _trust_file(product_root: Path) -> dict[str, Any]:
    path = trust_roots_path(product_root)
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_trust_roots(product_root: Path) -> dict[str, str]:
    """Registered verification keys: key_id -> Ed25519 public key (hex).

    A file without `alg: ed25519` is the old format, whose `keys` were HMAC
    secrets stored in the repository; it yields no trusted key.
    """
    data = _trust_file(product_root)
    if data.get("alg") != SIG_ALG:
        return {}
    return {str(k): str(v) for k, v in (data.get("keys") or {}).items()}


def trust_roots_registered(product_root: Path) -> bool:
    """True once the trust roots file exists: later receipts must be signed.

    Checked on the file, not on its keys, so an emptied or legacy file does not
    quietly switch the product back to unsigned receipts.
    """
    return trust_roots_path(product_root).is_file()


def _signed_since(product_root: Path) -> int:
    """Index of the first receipt that must be signed (receipts at registration)."""
    since = _trust_file(product_root).get("since_receipts")
    return since if isinstance(since, int) and since >= 0 else 0


def key_id_for(public: bytes) -> str:
    return _digest(public)[:12]


def install_trust_root(product_root: Path, *, public_key: bytes) -> str:
    """Register one Ed25519 verification key; returns its key_id.

    The first registration records how many receipts already exist: those were
    written unsigned under the local profile and stay valid.
    """
    if len(public_key) != 32:
        raise ReceiptError("an Ed25519 public key is 32 bytes")
    path = trust_roots_path(product_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _trust_file(product_root)
    keys = dict(_load_trust_roots(product_root))
    since = current.get("since_receipts") if current.get("alg") == SIG_ALG else None
    if not isinstance(since, int):
        since = len(load_receipts(Path(product_root)))
    key_id = key_id_for(public_key)
    keys[key_id] = public_key.hex()
    path.write_text(
        yaml.safe_dump({"alg": SIG_ALG, "since_receipts": since, "keys": keys}, sort_keys=True),
        encoding="utf-8",
    )
    return key_id


def _signing_seed() -> bytes | None:
    """The human's Ed25519 private key: hex in DELTAFUSE_BROKER_KEY, or a file
    named by DELTAFUSE_BROKER_KEY_FILE. None when neither is set."""
    raw = os.environ.get(BROKER_KEY_ENV, "").strip()
    key_file = os.environ.get(BROKER_KEY_FILE_ENV, "").strip()
    if not raw and key_file:
        try:
            raw = Path(key_file).expanduser().read_text(encoding="utf-8").strip()
        except OSError as ex:
            raise ReceiptError(f"cannot read {BROKER_KEY_FILE_ENV}: {ex}") from ex
    if not raw:
        return None
    try:
        seed = bytes.fromhex(raw)
    except ValueError:
        seed = b""
    if len(seed) != 32:
        raise ReceiptError(
            "the broker key must be a 32-byte Ed25519 private key in hex "
            "(create one with: deltafuse gate-key init)"
        )
    return seed


def signing_problem(product_root: Path) -> str | None:
    """Why a Human Gate receipt cannot be recorded right now; None when it can.

    Called before `decide` writes anything, so a refused verdict leaves no
    artifact marked accepted without its receipt.
    """
    root = Path(product_root)
    if not (load_profile(root) == "broker-signed" or trust_roots_registered(root)):
        return None
    try:
        seed = _signing_seed()
    except ReceiptError as ex:
        return str(ex)
    if seed is None:
        return (
            "this product requires signed Human Gate receipts and the human's key "
            f"is not available ({BROKER_KEY_ENV} or {BROKER_KEY_FILE_ENV}); a Worker "
            "must not record a Human Gate verdict"
        )
    public = ed25519.public_key(seed)
    if _load_trust_roots(root).get(key_id_for(public)) != public.hex():
        return (
            "broker key is not registered in the trust roots "
            f"({TRUST_ROOTS_REL}); register it with: deltafuse gate-key init"
        )
    return None


def _signature_problem(entry: dict[str, Any], trust: dict[str, str]) -> str | None:
    """None when the entry is signed by a registered Ed25519 key; else why not."""
    if entry.get("sig_alg") != SIG_ALG:
        return (
            "not signed with a registered Ed25519 key (HMAC receipts are not "
            "trusted: their key sat in the repository)"
        )
    public = trust.get(str(entry.get("key_id")))
    if public is None:
        return f"signed by unknown key_id {entry.get('key_id')!r}"
    try:
        ok = ed25519.verify(
            bytes.fromhex(public),
            str(entry.get("chain_hash")).encode("utf-8"),
            bytes.fromhex(str(entry.get("signature"))),
        )
    except ValueError:
        ok = False
    return None if ok else "broker signature does not verify"


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
    if profile == "broker-signed" or trust_roots_registered(root):
        problem = signing_problem(root)
        if problem:
            raise ReceiptError(problem)
        seed = _signing_seed()
        assert seed is not None  # signing_problem checked it
        key_id = key_id_for(ed25519.public_key(seed))
        entry["profile"] = "broker-signed"
        entry["key_id"] = key_id
        entry["sig_alg"] = SIG_ALG
        entry["chain_hash"] = _chain_hash(entry)
        entry["signature"] = ed25519.sign(seed, entry["chain_hash"].encode("utf-8")).hex()
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
    signed_from = _signed_since(root) if trust_roots_registered(root) else None
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
        must_sign = signed_from is not None and index >= signed_from
        if entry.get("profile") == "broker-signed" or must_sign:
            problem = _signature_problem(entry, trust)
            if problem:
                errors.append(f"{label}: {problem}")
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
    all_receipts = load_receipts(root)
    trust = _load_trust_roots(root)
    signed_from = _signed_since(root) if trust_roots_registered(root) else None
    for index in range(len(all_receipts) - 1, -1, -1):
        entry = all_receipts[index]
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
            must_sign = signed_from is not None and index >= signed_from
            if (entry.get("profile") == "broker-signed" or must_sign) and _signature_problem(
                entry, trust
            ):
                continue
        if (
            current_digest is not None
            and version is not None
            and entry.get("artifact_sha256") != current_digest
        ):
            continue  # stale: artifact changed after the click
        return True
    return False


def has_click(
    product_root: Path,
    *,
    kind: str,
    status: str,
    artifact_id: str | None = None,
    rel_path: str | None = None,
) -> bool:
    """True when the journal records this terminal status for the artifact.

    Weaker than `has_valid_receipt`: it does not re-check the artifact bytes or
    the chain, so a stale click still counts. Kept as its own predicate because
    `fsm.py` deliberately uses both.
    """
    want_path = rel_path.replace("\\", "/") if rel_path else None
    for event in reversed(load_receipts(product_root)):
        if event.get("kind") != kind or event.get("status") != status:
            continue
        if artifact_id and event.get("id") == artifact_id:
            return True
        if want_path and event.get("path") == want_path:
            return True
    return False
