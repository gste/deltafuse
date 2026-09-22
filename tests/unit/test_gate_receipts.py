"""DF3-007: Human Gate receipts and integrity profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from deltafuse.cli import main
from deltafuse.core import ed25519
from deltafuse.core import gate_receipts as receipts
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.installer import install

# The human's key: RFC 8032 TEST 1 secret. A Worker reads the repository, which
# holds only the public half.
SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUBLIC = ed25519.public_key(SEED)


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


def _register(root: Path, monkeypatch, *, profile: str | None = "broker-signed") -> str:
    key_id = receipts.install_trust_root(root, public_key=PUBLIC)
    monkeypatch.setenv(receipts.BROKER_KEY_ENV, SEED.hex())
    if profile:
        (root / ".deltafuse" / "config.yaml").write_text(
            yaml.safe_dump({"workflow": {"integrity_profile": profile}}), encoding="utf-8"
        )
    return key_id


def test_broker_signed_receipt_verifies_against_trust_roots(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    root = _root(tmp_path, repo_root)
    key_id = _register(root, monkeypatch)
    artifact = _artifact(root)

    receipt = _record(root, artifact)

    assert receipt["profile"] == "broker-signed"
    assert receipt["sig_alg"] == "ed25519" and receipt["key_id"] == key_id
    assert receipts.journal_errors(root) == []
    assert receipts.has_valid_receipt(
        root, kind="spec", status="accepted", artifact=artifact
    )


def test_trust_roots_hold_only_the_public_key(tmp_path: Path, repo_root: Path, monkeypatch):
    """The HMAC profile kept its secret in trusted-keys.yaml: whoever read the
    repository could sign. The file now holds a public key, which signs
    nothing."""
    root = _root(tmp_path, repo_root)
    key_id = _register(root, monkeypatch)
    stored = yaml.safe_load((root / ".deltafuse" / "trusted-keys.yaml").read_text(encoding="utf-8"))
    assert stored["alg"] == "ed25519"
    assert stored["keys"] == {key_id: PUBLIC.hex()}
    assert SEED.hex() not in (root / ".deltafuse" / "trusted-keys.yaml").read_text(encoding="utf-8")

    # A Worker that uses what it can read as the key is refused.
    monkeypatch.setenv(receipts.BROKER_KEY_ENV, PUBLIC.hex())
    with pytest.raises(receipts.ReceiptError, match="not registered"):
        _record(root, _artifact(root))


def test_forged_receipt_fails_verification(tmp_path: Path, repo_root: Path, monkeypatch):
    root = _root(tmp_path, repo_root)
    _register(root, monkeypatch)
    artifact = _artifact(root)
    _record(root, artifact, status="rejected")

    journal = root / ".deltafuse" / "gate-journal.jsonl"
    entry = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
    entry["status"] = "accepted"  # the forger flips the verdict and re-chains it
    entry["chain_hash"] = receipts._chain_hash(entry)
    entry["signature"] = ed25519.sign(bytes(32), entry["chain_hash"].encode("utf-8")).hex()
    journal.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")
    receipts._write_head(root, receipts._digest(json.dumps(entry, sort_keys=True).encode("utf-8")))

    assert any("does not verify" in e for e in receipts.journal_errors(root))
    assert not receipts.has_valid_receipt(root, kind="spec", status="accepted", artifact=artifact)


def test_config_downgrade_does_not_switch_signing_off(tmp_path: Path, repo_root: Path, monkeypatch):
    """`.deltafuse/config.yaml` is not guarded by the leash; with trust roots
    registered, the local profile still requires the human's key."""
    root = _root(tmp_path, repo_root)
    _register(root, monkeypatch, profile="local")
    monkeypatch.delenv(receipts.BROKER_KEY_ENV)
    with pytest.raises(receipts.ReceiptError, match="signed Human Gate receipts"):
        _record(root, _artifact(root))


def test_receipts_before_registration_stay_valid(tmp_path: Path, repo_root: Path, monkeypatch):
    root = _root(tmp_path, repo_root)
    earlier = _artifact(root, "early.md")
    _record(root, earlier)  # local profile, unsigned

    _register(root, monkeypatch, profile=None)
    later = _artifact(root, "later.md")
    _record(root, later)

    assert receipts.journal_errors(root) == []
    assert receipts.has_valid_receipt(root, kind="spec", status="accepted", artifact=earlier)
    assert receipts.has_valid_receipt(root, kind="spec", status="accepted", artifact=later)


def test_legacy_hmac_trust_roots_are_not_trusted(tmp_path: Path, repo_root: Path):
    root = _root(tmp_path, repo_root)
    (root / ".deltafuse" / "trusted-keys.yaml").write_text(
        yaml.safe_dump({"keys": {"abc123": "a-secret-in-the-repository"}}), encoding="utf-8"
    )
    journal = root / ".deltafuse" / "gate-journal.jsonl"
    entry = {
        "receipt_version": receipts.RECEIPT_VERSION, "profile": "broker-signed",
        "kind": "spec", "status": "accepted", "id": "CHG-700", "path": "x.md",
        "change": "CHG-700", "artifact_sha256": "0", "actor": "human-via-core",
        "ts": "2026-09-21T00:00:00Z", "nonce": "n1", "prev_hash": "", "key_id": "abc123",
    }
    entry["chain_hash"] = receipts._chain_hash(entry)
    entry["signature"] = "00"
    journal.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")
    assert any("not signed with a registered Ed25519 key" in e for e in receipts.journal_errors(root))


def test_worker_decide_is_refused_before_anything_is_written(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    """Roadmap item 4: the Worker could run `deltafuse decide` and the receipt
    read as the human's. Without the human's key the verdict is refused, and
    the artifact is left as it was."""
    root = _root(tmp_path, repo_root)
    _register(root, monkeypatch, profile=None)
    monkeypatch.delenv(receipts.BROKER_KEY_ENV)
    dec_dir = root / "docs" / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    dec = dec_dir / "DEC-0001-store.md"
    dec.write_text(
        "---\nid: DEC-0001\ntitle: Store\nkind: architecture\nstatus: proposed\n"
        "owner: ghost\naffects: {capabilities: [], spec_refs: []}\n---\n# Decision\n",
        encoding="utf-8",
    )
    before = dec.read_bytes()
    with pytest.raises(DecideError, match="signed Human Gate receipts"):
        apply_decision(root, status="accepted", decision="DEC-0001")
    assert dec.read_bytes() == before
    assert receipts.load_receipts(root) == []


def test_gate_key_init_keeps_the_private_key_outside_the_product(
    tmp_path_factory, repo_root: Path, capsys
):
    product = tmp_path_factory.mktemp("product")
    install(target_dir=product, framework_root=repo_root)
    inside = product / "keys" / "human.ed25519"
    assert main(["gate-key", "init", str(product), "--key-file", str(inside)]) == 1
    assert not inside.exists()
    capsys.readouterr()

    outside = tmp_path_factory.mktemp("home") / "human.ed25519"
    assert main(["gate-key", "init", str(product), "--key-file", str(outside)]) == 0
    seed = bytes.fromhex(outside.read_text(encoding="utf-8").strip())
    stored = yaml.safe_load((product / ".deltafuse" / "trusted-keys.yaml").read_text(encoding="utf-8"))
    assert list(stored["keys"].values()) == [ed25519.public_key(seed).hex()]
    assert seed.hex() not in (product / ".deltafuse" / "trusted-keys.yaml").read_text(encoding="utf-8")


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
