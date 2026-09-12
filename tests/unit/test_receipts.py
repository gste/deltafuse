"""DF3-007: Human Gate receipts and integrity profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from deltafuse.core import receipts
from deltafuse.core.installer import install

import hashlib

SECRET = "test-secret-0123456789abcdef"
KEY_ID = hashlib.sha256(SECRET.encode()).hexdigest()[:12]


def _root(tmp_path: Path, repo_root: Path) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    return tmp_path


def _artifact(tmp_path: Path, name: str = "spec-delta.md") -> Path:
    path = tmp_path / name
    path.write_text("---\nstatus: accepted\n---\nbody\n", encoding="utf-8")
    return path


def _record(
    root: Path, artifact: Path, *, status: str = "accepted", kind: str = "spec"
) -> dict:
    return receipts.record_receipt(
        root,
        kind=kind,
        status=status,
        rel_path=artifact.name,
        artifact_id="CHG-700",
        change="CHG-700",
        artifact=artifact,
    )


def test_local_profile_records_chain_and_declares_weak_guarantee(
    tmp_path: Path, repo_root: Path
):
    root = _root(tmp_path, repo_root)
    artifact = _artifact(root)

    receipt = _record(root, artifact)

    assert receipts.load_profile(root) == "local"
    assert receipt["receipt_version"] == receipts.RECEIPT_VERSION
    assert receipt["prev_hash"] == ""  # first link
    assert "guarantee" in receipt and "does not" in receipt["guarantee"]
    assert "signature" not in receipt
    assert receipts.journal_errors(root) == []
    assert receipts.has_valid_receipt(
        root, kind="spec", status="accepted", artifact=artifact
    )


def test_broker_signed_receipt_verifies_against_trust_roots(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    root = _root(tmp_path, repo_root)
    receipts.install_trust_root(root, key_id=KEY_ID, secret=SECRET)
    monkeypatch.setenv(receipts.BROKER_KEY_ENV, SECRET)
    (root / ".deltafuse" / "config.yaml").write_text(
        yaml.safe_dump({"workflow": {"integrity_profile": "broker-signed"}}),
        encoding="utf-8",
    )
    artifact = _artifact(root)

    receipt = _record(root, artifact)

    assert receipt["profile"] == "broker-signed"
    assert receipt["key_id"] and receipt["signature"]
    assert receipts.journal_errors(root) == []
    assert receipts.has_valid_receipt(
        root, kind="spec", status="accepted", artifact=artifact
    )


def test_broker_signed_requires_host_key_outside_worker_surface(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    root = _root(tmp_path, repo_root)
    (root / ".deltafuse" / "config.yaml").write_text(
        yaml.safe_dump({"workflow": {"integrity_profile": "broker-signed"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv(receipts.BROKER_KEY_ENV, raising=False)
    with pytest.raises(receipts.ReceiptError, match="broker"):
        _record(root, _artifact(root))


def test_edited_entry_is_detected(tmp_path: Path, repo_root: Path):
    root = _root(tmp_path, repo_root)
    artifact = _artifact(root)
    _record(root, artifact)

    journal = root / ".deltafuse" / "gate-journal.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    edited = json.loads(lines[0])
    edited["status"] = "rejected"  # forger flips the verdict in place
    lines[0] = json.dumps(edited, ensure_ascii=False, sort_keys=True)
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    errors = receipts.journal_errors(root)
    assert any("chain hash" in e for e in errors), errors
    assert not receipts.has_valid_receipt(
        root, kind="spec", status="accepted", artifact=artifact
    )


def test_truncated_journal_is_detected(tmp_path: Path, repo_root: Path):
    root = _root(tmp_path, repo_root)
    artifact = _artifact(root)
    _record(root, artifact)
    _record(root, artifact, status="rejected", kind="decision")

    journal = root / ".deltafuse" / "gate-journal.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    journal.write_text(lines[0] + "\n", encoding="utf-8")  # drop the last click

    errors = receipts.journal_errors(root)
    assert any("truncated or replaced" in e for e in errors), errors


def test_replaced_history_is_detected(tmp_path: Path, repo_root: Path):
    """Rebuilding the journal with a fresh chain cannot match the head digest
    the Core recorded when appending."""
    root = _root(tmp_path, repo_root)
    artifact = _artifact(root)
    _record(root, artifact)

    journal = root / ".deltafuse" / "gate-journal.jsonl"
    forged = dict(_artifact_receipt_payload(), chain_hash=None)
    journal.write_text(
        json.dumps({**_artifact_receipt_payload(), "chain_hash": ""}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    assert any("head digest" in e for e in receipts.journal_errors(root))


def _artifact_receipt_payload() -> dict:
    return {
        "receipt_version": 2,
        "profile": "local",
        "kind": "spec",
        "status": "accepted",
        "id": "CHG-700",
        "path": "spec-delta.md",
        "change": "CHG-700",
        "actor": "human-via-core",
        "ts": "2026-09-12T00:00:00Z",
        "nonce": "deadbeef",
        "prev_hash": "",
    }


def test_stale_receipt_does_not_count_after_artifact_changed(
    tmp_path: Path, repo_root: Path
):
    root = _root(tmp_path, repo_root)
    artifact = _artifact(root)
    _record(root, artifact)

    artifact.write_text("---\nstatus: accepted\n---\nbody v2\n", encoding="utf-8")
    assert receipts.journal_errors(root) == []  # journal itself intact
    assert not receipts.has_valid_receipt(
        root, kind="spec", status="accepted", artifact=artifact
    ), "a receipt over old bytes must not validate a Human Gate"


def test_core_never_offers_a_merge_command(capsys):
    """Merge stays a host/human gate: the CLI has no merge command."""
    from deltafuse.cli import main

    with pytest.raises(SystemExit):
        main(["merge"])
    _, err = capsys.readouterr()
    assert "merge" in err
