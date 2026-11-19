"""Audit 2026-11-17 (df-leash), the Writer: FW-9 (a kind writes only its own file), FW-14 (a second
create of an existing identity is a refusal, not a traceback), FW-16 (the contract's own example)."""

from __future__ import annotations

import hashlib
import json

import pytest

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, TASK_FIELDS, cli, leash, product_at, walk, write,
)


# --- FW-9 -------------------------------------------------------------------------------

MISPLACED = [
    ("routing", {"target": "coverage.yaml", "fields": {"claims": {}}}, "coverage.yaml"),
    ("routing", {"target": "change.yaml", "fields": {"claims": {}}}, "change.yaml"),
    ("change", {"target": "routing.yaml", "fields": {"route": "docs"}}, "routing.yaml"),
    ("change", {"target": "coverage.yaml", "fields": {"route": "docs"}}, "coverage.yaml"),
    ("slice", {"target": "tasks/TASK-001.md", "fields": {}, "body": "replaced"}, "tasks/TASK-001.md"),
    ("task", {"target": "slices/SLICE-01.md", "fields": {}, "body": "replaced"}, "slices/SLICE-01.md"),
    ("routing", {"target": "evidence/red/TASK-001.yaml", "fields": {"claims": {}}}, "evidence/red/TASK-001.yaml"),
    ("spec-delta", {"target": "verification.md", "fields": {}, "body": "x"}, "verification.md"),
]


@pytest.mark.parametrize("kind,envelope,victim", MISPLACED, ids=[f"{k}->{v}" for k, _, v in MISPLACED])
def test_a_kind_does_not_write_another_kinds_file(product_at, kind, envelope, victim):
    """FW-9: `--kind routing` with `target: coverage.yaml` replaced the Core-only coverage.yaml
    with a routing mapping; the leash passed it (a Writer receipt vouched for it)."""
    root, change = product_at("declared")
    path = change / victim
    before = path.read_bytes() if path.exists() else None
    code, out = write(root, kind, envelope, check=False)
    assert code != 0, out
    assert (path.read_bytes() if path.exists() else None) == before, f"{victim} was rewritten"


def test_the_service_refuses_it_too(product_at):
    """The other entry point: `artifact update`, which names its target itself."""
    from deltafuse.core.artifact_policy import ArtifactPolicyError, create_authorization_context
    from deltafuse.core.artifacts import ArtifactService

    root, change = product_at("declared")
    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=root, change_id=CHANGE)
    service = ArtifactService(product_root=root, change_dir=change, auth_context=auth)
    victim = change / "coverage.yaml"
    before = victim.read_bytes()
    for target in ("coverage.yaml", str(victim), "tasks/../coverage.yaml"):
        with pytest.raises(ArtifactPolicyError):
            service.update(kind="routing", target=target, expected_sha256=hashlib.sha256(before).hexdigest(),
                           patch={"set": [{"path": "/claims", "value": {}}]})
    assert victim.read_bytes() == before


def test_each_kind_still_writes_its_own_file(product_at):
    root, change = product_at("specified")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS, "body": "b"})
    write(root, "task", {"target": "tasks/TASK-001.md", "fields": {}, "body": "by target"})
    write(root, "slice", {"identity": "SLICE-01", "fields": {}, "body": "new body"})
    write(root, "change", {"target": "change.yaml", "fields": {"route": "code"}})
    assert "by target" in (change / "tasks" / "TASK-001.md").read_text(encoding="utf-8")


# --- FW-14 ------------------------------------------------------------------------------

def _open_transactions(root) -> list[str]:
    journal = root / ".deltafuse" / "journal"
    receipts = root / ".deltafuse" / "receipts"
    return [f.name for f in journal.glob("*.json") if not (receipts / f.name).exists()] if journal.is_dir() else []


def test_a_second_create_under_another_file_name_is_refused_cleanly(product_at):
    """FW-14: `identity: TASK-001` with `target: tasks/TASK-001-banner.md`: the target did not exist,
    so the Writer went to create TASK-001 again - a traceback and a journal entry left open."""
    root, change = product_at("specified")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS, "body": "x"})
    task = change / "tasks" / "TASK-001.md"
    before = task.read_bytes()
    opened = _open_transactions(root)
    code, out = write(root, "task", {"identity": "TASK-001", "target": "tasks/TASK-001-banner.md",
                                      "fields": TASK_FIELDS, "body": "y"}, check=False)
    assert code != 0 and "Traceback" not in out, out
    assert "already exists" in out, out
    assert task.read_bytes() == before and not (change / "tasks" / "TASK-001-banner.md").exists()
    assert _open_transactions(root) == opened, "a transaction was left open"
    write(root, "task", {"identity": "TASK-002", "fields": {**TASK_FIELDS, "title": "next"}, "body": "x"})


def test_the_service_create_refuses_an_existing_identity_before_the_transaction(product_at):
    """The twin: `artifact create` itself, and an identity held by a `<ID>-<slug>.md` file."""
    from deltafuse.core.artifact_policy import create_authorization_context
    from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError

    root, change = product_at("specified")
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS, "body": "x"})
    (change / "tasks" / "TASK-001.md").rename(change / "tasks" / "TASK-001-banner.md")
    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=root, change_id=CHANGE)
    service = ArtifactService(product_root=root, change_dir=change, auth_context=auth)
    opened = _open_transactions(root)
    payload = {**TASK_FIELDS, "context_budget": {"max_tokens": 64000, "max_files": 24}}
    with pytest.raises(ArtifactServiceError, match="already exists"):
        service.create(kind="task", identity="TASK-001", semantic_payload=payload, body="again")
    assert _open_transactions(root) == opened
    assert not (change / "tasks" / "TASK-001.md").exists()


# --- FW-16 ------------------------------------------------------------------------------

def test_the_contracts_title_example_works(product_at):
    """FW-16: docs/contracts/artifact-writer.md shows `set /title` on a task; the Writer refused it."""
    root, change = product_at("specified")  # Decompose: the step that writes tasks
    write(root, "task", {"identity": "TASK-001", "fields": TASK_FIELDS,
                         "body": "Print the banner. Oracle: tests/test_banner.py."})
    code, out = write(root, "task", {"identity": "TASK-001", "fields": {"title": "Updated Auth Title"}}, check=False)
    assert code == 0, out
    text = (change / "tasks" / "TASK-001.md").read_text(encoding="utf-8")
    assert "# TASK-001: Updated Auth Title" in text and "Print the banner. Oracle" in text, text
    code, data = leash(root)
    assert data["violations"] == [], data


def test_the_contract_table_names_every_field_the_descriptors_expose(repo_root):
    """The table left `route` out of `routing`; it is checked against the descriptors now."""
    import yaml

    for name in ("artifact-writer.md", "artifact-writer.ru.md"):
        table = (repo_root / "docs" / "contracts" / name).read_text(encoding="utf-8")
        for kind in ("task", "slice", "spec-delta", "routing", "change", "decision"):
            descriptor = yaml.safe_load(
                (repo_root / "process" / "artifact-operations" / f"{kind}.descriptor.yaml").read_text(encoding="utf-8"))
            row = next((line for line in table.splitlines() if line.startswith(f"| `{kind}` |")), None)
            assert row is not None, (name, kind)
            fields = (set(descriptor.get("creatable_semantic_fields") or []) | {
                p.strip("/") for p in descriptor.get("updatable_semantic_fields") or []}
            ) - set(descriptor.get("core_owned_fields") or [])
            public = row.split("|")[3]
            missing = sorted(f for f in fields if f"`{f}`" not in public)
            assert not missing, (name, kind, missing)
