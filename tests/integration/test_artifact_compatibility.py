"""Integration tests for manual artifact backward compatibility, open extensions, and opt-in canonicalization (AW-16)."""

import hashlib
from pathlib import Path
import pytest
import yaml

from deltafuse.core.artifact_codec import ArtifactCodecError
from deltafuse.core.artifact_reader import strict_read_artifact
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError
from deltafuse.core.artifact_policy import create_authorization_context
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change


def test_manual_artifact_preservation_open_extension_fields_comments_crlf(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-160", route="code", title="Compatibility Test")

    (change_dir / "slices").mkdir(parents=True, exist_ok=True)
    (change_dir / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-160\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (change_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (change_dir / "docs" / "spec" / "core.md").write_text("# Core Spec\n", encoding="utf-8")

    # 1. Test open extension fields on routing.yaml (which permits unconstrained extension keys)
    routing_file = change_dir / "routing.yaml"
    routing_content = (
        "change: CHG-160\n"
        "claims:\n"
        "  CR-001:\n"
        "    primary_capability: core\n"
        "custom_vendor_notes: \"Manual note\"\n"
        "custom_routing_flag: 42\n"
    )
    routing_file.write_text(routing_content, encoding="utf-8")
    expected_routing_sha = hashlib.sha256(routing_file.read_bytes()).hexdigest()

    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=change_dir, change_id="CHG-160")
    service = ArtifactService(product_root=change_dir, auth_context=auth)

    patch_routing = {
        "set": [{"path": "/claims/CR-001/primary_capability", "value": "core"}],
        "remove": [],
        "canonicalize_metadata": True,
    }
    rec_r = service.update(kind="routing", target="routing.yaml", expected_sha256=expected_routing_sha, patch=patch_routing)
    assert rec_r["outcome"] in ("published", "committed", "unchanged")
    r_meta = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
    assert r_meta["custom_vendor_notes"] == "Manual note"
    assert r_meta["custom_routing_flag"] == 42

    # 2. Create task file manually with comments and CRLF line endings
    task_file = change_dir / "tasks" / "TASK-001.md"
    task_content = (
        "---\r\n"
        "id: TASK-001\r\n"
        "change: CHG-160\r\n"
        "slice: SLICE-01\r\n"
        "kind: feature\r\n"
        "status: pending\r\n"
        "depends_on: []\r\n"
        "requirement_delta: none\r\n"
        "spec_refs: [\"docs/spec/core.md\"]\r\n"
        "allowed_paths: [\"src/auth.py\"]\r\n"
        "forbidden_paths: []\r\n"
        "context_budget: {max_tokens: 1000, max_files: 5}\r\n"
        "---\r\n"
        "# TASK-001: Manual Authoring\r\n"
        "<!-- Manual author comment -->\r\n"
    )
    task_file.write_bytes(task_content.encode("utf-8"))
    expected_sha256 = hashlib.sha256(task_file.read_bytes()).hexdigest()

    # Patch an allowed semantic field (/allowed_paths) with canonicalize_metadata=True
    patch = {
        "set": [{"path": "/allowed_paths", "value": ["src/auth.py", "src/tokens.py"]}],
        "remove": [],
        "canonicalize_metadata": True,
    }

    receipt = service.update(
        kind="task",
        target="tasks/TASK-001.md",
        expected_sha256=expected_sha256,
        patch=patch,
    )
    assert receipt["outcome"] in ("published", "committed")

    # Read updated file and verify body comment is preserved
    updated_bytes = task_file.read_bytes()
    parse_res = strict_read_artifact(updated_bytes)
    assert parse_res.metadata["allowed_paths"] == ["src/auth.py", "src/tokens.py"]
    assert "<!-- Manual author comment -->" in parse_res.raw_body


def test_canonicalize_metadata_formatting_opt_in_hash_binding(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = scaffold_change(tmp_path, "CHG-161", route="code", title="Format Opt-In Test")

    (change_dir / "slices").mkdir(parents=True, exist_ok=True)
    (change_dir / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-161\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (change_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (change_dir / "docs" / "spec" / "core.md").write_text("# Core Spec\n", encoding="utf-8")

    # Non-canonical formatting (unordered keys, extra spacing)
    task_file = change_dir / "tasks" / "TASK-002.md"
    non_canonical_content = (
        "---\n"
        "status: pending\n"
        "kind: feature\n"
        "depends_on: []\n"
        "requirement_delta: none\n"
        "spec_refs: ['docs/spec/core.md']\n"
        "context_budget:\n"
        "  max_files: 2\n"
        "  max_tokens: 500\n"
        "allowed_paths: ['src/app.py']\n"
        "forbidden_paths: []\n"
        "slice: SLICE-01\n"
        "change: CHG-161\n"
        "id: TASK-002\n"
        "---\n"
        "# TASK-002\n"
    )
    task_file.write_text(non_canonical_content, encoding="utf-8")
    expected_sha256 = hashlib.sha256(task_file.read_bytes()).hexdigest()

    auth = create_authorization_context(actor="worker", work_item="CLI", product_root=change_dir, change_id="CHG-161")
    service = ArtifactService(product_root=change_dir, auth_context=auth)

    # Without canonicalize_metadata=True, update must fail fail-closed
    patch_no_optin = {
        "set": [{"path": "/allowed_paths", "value": ["src/app.py", "src/utils.py"]}],
        "remove": [],
        "canonicalize_metadata": False,
    }

    with pytest.raises(ArtifactServiceError) as exc_info:
        service.update(
            kind="task",
            target="tasks/TASK-002.md",
            expected_sha256=expected_sha256,
            patch=patch_no_optin,
        )
    assert exc_info.value.code == "invalid_payload" or "canonicalize_metadata=True" in str(exc_info.value)

    # File must remain untouched
    assert task_file.read_text(encoding="utf-8") == non_canonical_content


def test_all_route_types_scaffold_and_update(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)

    for r in ("code", "docs", "ops"):
        cid = f"CHG-162-{r}"
        cdir = scaffold_change(tmp_path, cid, route=r, title=f"Route {r}")
        cdata = yaml.safe_load((cdir / "change.yaml").read_text(encoding="utf-8"))
        assert cdata["route"] == r
