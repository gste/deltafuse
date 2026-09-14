"""Private parallel-approval overlay integrity and live PostgreSQL checks."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

REPO_ROOT = Path(__file__).parents[3]
CASE_ROOT = REPO_ROOT / "process/bench/cases/J03-document-flow"
SEED = CASE_ROOT / "seed"
REFERENCE = CASE_ROOT / "oracle/reference"
SUPERSEDE = REFERENCE / "patches/version-supersede"
APPROVAL = REFERENCE / "patches/parallel-approval"


def _copy_overlay(source: Path, destination: Path) -> None:
    for file in (source / "overlay").rglob("*"):
        if file.is_file():
            target = destination / file.relative_to(source / "overlay")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)


def _reference_copy(tmp_path: Path, *, approval: bool) -> Path:
    copied = tmp_path / "seed"
    shutil.copytree(SEED, copied)
    _copy_overlay(SUPERSEDE, copied)
    if approval:
        for patch in ("workflow-command-service.patch", "decision-state.patch"):
            finished = subprocess.run(
                ["git", "apply", str(APPROVAL / patch)], cwd=copied,
                capture_output=True, text=True)
            assert finished.returncode == 0, finished.stderr
        _copy_overlay(APPROVAL, copied)
    else:
        harness = APPROVAL / "overlay/workflow-service/src/test/java/dev/deltafuse/bench/workflow/ReferenceApprovalHarness.java"
        target = copied / harness.relative_to(APPROVAL / "overlay")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(harness, target)
    return copied


def _maven(copied: Path) -> subprocess.CompletedProcess[str]:
    repository = os.environ["J03_MAVEN_REPOSITORY"]
    environment = dict(os.environ)
    environment.setdefault("JAVA_HOME", os.environ.get("J03_JAVA_HOME", ""))
    return subprocess.run(
        [shutil.which("mvn") or "mvn", "--offline",
         "-Dmaven.repo.local=" + repository, "-f", str(copied / "pom.xml"),
         "-pl", "workflow-service", "-am", "test", "-Pdb-integration",
         "-Dtest=ReferenceApprovalHarness",
         "-Dsurefire.failIfNoSpecifiedTests=false"],
        cwd=copied, env=environment, capture_output=True, text=True,
        timeout=1800)


def test_parallel_overlay_manifest_binds_every_asset():
    manifest = json.loads((APPROVAL / "overlay.json").read_text(encoding="utf-8"))
    assert manifest["patch"] == "parallel-approval"
    for entry in manifest["files"]:
        file = APPROVAL / entry["path"]
        assert file.is_file() and not file.is_symlink()
        assert hashlib.sha256(file.read_bytes()).hexdigest() == entry["sha256"]
        assert len(file.read_bytes()) == entry["byte_length"]


def test_patch_applies_only_after_supersede_overlay(tmp_path):
    copied = _reference_copy(tmp_path, approval=True)
    service = (copied / "workflow-service/src/main/java/dev/deltafuse/bench/workflow/WorkflowCommandService.java").read_text(encoding="utf-8")
    assert all(marker in service for marker in (
        "EXPERT_REVIEW_INCOMPLETE", "ACTOR_ROLE_MISMATCH", "UNSUPPORTED_ACTION"))
    assert (copied / "workflow-service/src/main/resources/db/migration/V5__reference_parallel_approval.sql").is_file()


def test_public_seed_remains_single_approver_baseline():
    service = (SEED / "workflow-service/src/main/java/dev/deltafuse/bench/workflow/WorkflowCommandService.java").read_text(encoding="utf-8")
    assert "ACTOR_ROLE_MISMATCH" not in service
    status = subprocess.run(["git", "status", "--porcelain", "--", str(SEED)],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert status.returncode == 0 and not status.stdout.strip()


def test_live_parallel_approval_matches_interpreter(tmp_path):
    if not os.environ.get("J03_MAVEN_REPOSITORY"):
        pytest.skip("live reference run not selected")
    copied = _reference_copy(tmp_path, approval=True)
    result = _maven(copied)
    assert result.returncode == 0, result.stdout[-5000:] + result.stderr[-2000:]
    observed = json.loads((copied / "workflow-service/target/reference-approval-outcomes.json").read_text())
    interpreter = _load_interpreter()
    normal = interpreter.reduce(_normal_operations())
    reject = interpreter.reduce(_reject_operations())
    assert observed["normal"] == normal.documents["normal-doc"].routes[("normal-doc", "normal-version")].state
    assert observed["reject"] == reject.documents["reject-doc"].routes[("reject-doc", "reject-version")].state
    assert observed["normal_decisions"] == 3
    assert observed["reject_decisions"] == 1
    assert observed["generated_approved"] == 2
    for index in range(2):
        generated = interpreter.reduce(_generated_operations(index))
        name = f"generated-{index}"
        assert generated.documents[name + "-doc"].routes[(name + "-doc", name + "-version")].state == "APPROVED"


def _normal_operations():
    base = _base("normal")
    base.extend([
        _decision("normal", "d-early", "reg-1", "registrar", "APPROVE"),
        _decision("normal", "d-legal", "expert-1", "legal", "APPROVE"),
        _decision("normal", "d-reuse", "expert-1", "security", "APPROVE"),
        _decision("normal", "d-security", "expert-2", "security", "APPROVE"),
        _decision("normal", "d-reg-reject", "reg-1", "registrar", "REJECT"),
        _decision("normal", "d-registrar", "reg-1", "registrar", "APPROVE"),
        _decision("normal", "d-registrar", "reg-1", "registrar", "APPROVE"),
    ])
    return base


def _reject_operations():
    return _base("reject") + [_decision("reject", "d-reject", "expert-3", "legal", "REJECT")]


def _generated_operations(index):
    name = f"generated-{index}"
    first, second = (("legal", "security") if index == 0 else ("security", "legal"))
    return _base(name) + [
        _decision(name, "d-first", f"generated-a-{index}", first, "APPROVE"),
        _decision(name, "d-second", f"generated-b-{index}", second, "APPROVE"),
        _decision(name, "d-registrar", f"generated-r-{index}", "registrar", "APPROVE"),
    ]


def _base(name):
    return [
        {"kind": "http", "op": "create-document", "document_id": name + "-doc", "title": name},
        {"kind": "http", "op": "create-version", "document_id": name + "-doc", "version_id": name + "-version", "content": name},
        {"kind": "http", "op": "submit-version", "document_id": name + "-doc", "version_id": name + "-version", "route_id": name + "-route"},
    ]


def _decision(name, decision_id, actor, role, action):
    return {"kind": "decision", "op": "decision", "document_id": name + "-doc",
            "version_id": name + "-version", "route_id": name + "-route",
            "decision_id": decision_id, "actor_id": actor, "role": role,
            "action": action}


def _load_interpreter():
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("j03_approval_interpreter", REFERENCE / "../interpreter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
