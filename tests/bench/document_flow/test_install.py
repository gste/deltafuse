"""Installation, layout and leak tests for the J03 public pack.

Portable checks run without any framework install: inventory verification
must refuse modified hashes, missing entries, escaping links, duplicated
entries and any judge-named material — including a renamed oracle. The
integration test installs the real public pack into a sandbox and proves
the installed tree is complete, hash-clean and judge-free.
"""

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from scripts.document_flow import install as installer

REPO_ROOT = Path(__file__).parents[3]
CASE_ROOT = REPO_ROOT / "process/bench/cases/J03-document-flow"


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _inventory_entry(root: Path, rel: str) -> dict:
    data = (root / rel).read_bytes()
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(),
            "byte_length": len(data)}


def _mini_case(case: Path, entries: list[dict]) -> Path:
    case.mkdir(parents=True, exist_ok=True)
    inventory = {"schema_version": 1, "case": "mini", "includes": entries,
                 "excluded_judge_roots": ["oracle", "hidden_suite"]}
    (case / "public-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8")
    return case


def test_portable_path_checks_reject_escapes_and_non_portable_names():
    for bad in ("../seed/pom.xml", "seed\\pom.xml", "C:/seed/pom.xml",
                "/seed/pom.xml", "seed/./pom.xml", ""):
        with pytest.raises(installer.InstallRefused):
            installer._check_portable(bad)
    installer._check_portable("seed/pom.xml")


def test_judge_names_are_refused_even_when_renamed_or_nested():
    for bad in ("seed/legacy/oracle-notes.md", "seed/expected/oracle/x.java",
                "judge/answers.json", "seed/hidden_suite/case1.py",
                "reports/mutations/report.md", "seed/secret-values.yaml",
                "seed/legacy/mutation-helper.java"):
        with pytest.raises(installer.InstallRefused):
            installer._check_no_judge_name(bad)
    installer._check_no_judge_name("seed/legacy/LegacyMemoMapper.java")
    installer._check_no_judge_name("seed/pom.xml")


def test_verify_inventory_refuses_modified_or_missing_entries(tmp_path):
    case = tmp_path / "case"
    _write(case / "seed/pom.xml", b"<project/>")
    case = _mini_case(case, [_inventory_entry(case, "seed/pom.xml")])
    assert len(installer.verify_inventory(case)) == 1

    _write(case / "seed/pom.xml", b"<project changed/>")
    with pytest.raises(installer.InstallRefused, match="hash mismatch"):
        installer.verify_inventory(case)

    case = _mini_case(tmp_path / "case2", [{"path": "seed/absent.xml",
                                            "sha256": "0" * 64,
                                            "byte_length": 1}])
    with pytest.raises(installer.InstallRefused, match="missing"):
        installer.verify_inventory(case)


def test_verify_inventory_refuses_duplicate_and_judge_entries(tmp_path):
    case = tmp_path / "case"
    _write(case / "seed/pom.xml", b"<project/>")
    entry = _inventory_entry(case, "seed/pom.xml")
    case = _mini_case(case, [entry, dict(entry)])
    with pytest.raises(installer.InstallRefused, match="duplicate"):
        installer.verify_inventory(case)

    case = tmp_path / "case2"
    _write(case / "seed/pom.xml", b"<project/>")
    _write(case / "seed/legacy/oracle-notes.md", b"renamed oracle")
    renamed = _inventory_entry(case, "seed/legacy/oracle-notes.md")
    entry = _inventory_entry(case, "seed/pom.xml")
    case = _mini_case(case, [entry, renamed])
    with pytest.raises(installer.InstallRefused, match="judge material"):
        installer.verify_inventory(case)


def test_verify_inventory_refuses_link_entries(tmp_path):
    case = tmp_path / "case"
    target = case / "seed/pom.xml"
    _write(target, b"<project/>")
    entry = _inventory_entry(case, "seed/pom.xml")
    link = case / "seed" / "escape.xml"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlink creation unavailable on this platform")
    _write(case / "seed/escape.xml", b"<project/>")
    case = _mini_case(case, [entry, _inventory_entry(case, "seed/escape.xml")])
    os.remove(case / "seed/escape.xml")
    with pytest.raises(installer.InstallRefused, match="link"):
        installer.verify_inventory(case)


def test_real_case_inventory_is_complete_and_verifies_clean():
    inventory = installer.load_inventory(CASE_ROOT)
    assert inventory["case"] == "J03-document-flow"
    verified = installer.verify_inventory(CASE_ROOT)
    assert len(verified) == len(inventory["includes"]) >= 100
    rels = {entry["path"] for entry in verified}
    for required in ("input.md", "WORKER.md", "case.yaml",
                     "seed/pom.xml", "seed/compose.yaml",
                     "seed/infra/stack.ps1", "seed/infra/fault.ps1",
                     "seed/README.md",
                     "seed/tests/system/fixtures/approve.json",
                     "public_suite/baseline_suite.py"):
        assert required in rels, "public inventory lacks " + required
    judge_roots = inventory["excluded_judge_roots"]
    for entry in verified:
        assert not any(root in Path(entry["path"]).parts for root in judge_roots)


def test_install_public_pack_into_sandbox_is_complete_and_judge_free(tmp_path):
    product = tmp_path / "sandbox"
    meta = installer.install_document_flow(product, force=True)
    assert meta["case"] == "J03-document-flow"
    assert meta["verified_files"] == meta["inventory_entries"]
    product = Path(meta["product"])
    assert (product / "pom.xml").is_file()
    assert (product / "docs/intake/J03-document-flow.md").is_file()
    assert (product / "BENCH.md").is_file()
    assert (product / ".deltafuse/bench.yaml").is_file()
    assert (product / "shared-contracts/src/main/java/dev/deltafuse/"
            "bench/contracts/CanonicalJson.java").is_file()
    assert (product / "workflow-service/src/main/java/dev/deltafuse/bench/"
            "workflow/query/WorkflowProjectionController.java").is_file()
    lowered = str(product).lower()
    assert "oracle" not in lowered and "hidden_suite" not in lowered
    # a second run without --force refuses because the sandbox is occupied
    with pytest.raises(Exception):
        installer.install_document_flow(product, force=False)


def test_reparse_or_symlink_in_installed_tree_is_refused(tmp_path):
    product = tmp_path / "sandbox"
    installer.install_document_flow(product, force=True)
    outside = tmp_path / "outside.txt"
    _write(outside, b"escape")
    link = product / "seed" / "escape-link.xml"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlink creation unavailable on this platform")
    verified = installer.verify_inventory(CASE_ROOT)
    with pytest.raises(installer.InstallRefused, match="link"):
        installer._assert_product_clean(product, verified)
