"""Reference supersede tests: overlay integrity, seed purity, live scenarios.

The reference patch is private judge material: an overlay applied to a
fresh seed copy that implements the version-supersede slice of the target
Change. These tests prove the overlay binds and applies, the public seed
stays byte-identical, and — when J03_MAVEN_REPOSITORY selects a live run —
the patched reference passes real-PostgreSQL supersede scenarios whose
outcomes are compared against the independent interpreter.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.document_flow.install import _is_reparse_point

REPO_ROOT = Path(__file__).parents[3]
CASE_ROOT = REPO_ROOT / "process/bench/cases/J03-document-flow"
SEED = CASE_ROOT / "seed"
REFERENCE = CASE_ROOT / "oracle/reference"
PATCH = REFERENCE / "patches/version-supersede"
OVERLAY_MANIFEST = PATCH / "overlay.json"

SERVICE = "workflow-service/src/main/java/dev/deltafuse/bench/workflow/WorkflowCommandService.java"


def test_reference_assets_exist_and_bind_their_files():
    manifest = json.loads((REFERENCE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference"] == "version-supersede"
    overlay = json.loads(OVERLAY_MANIFEST.read_text(encoding="utf-8"))
    assert overlay["patch"] == "version-supersede"
    for entry in overlay["files"]:
        file = PATCH / entry["path"]
        assert file.is_file(), "overlay file missing: " + entry["path"]
        data = file.read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert entry["byte_length"] == len(data)
        assert not file.is_symlink() and not _is_reparse_point(file)


def test_overlay_implements_supersede_and_late_decision_semantics():
    patched = (PATCH / "overlay" / SERVICE).read_text(encoding="utf-8")
    for marker in ("SUPERSEDED", "j03.workflow.route-superseded",
                   "IGNORED_LATE_DECISION"):
        assert marker in patched, "overlay lacks " + marker
    migrations = list((PATCH / "overlay").rglob("V4__*.sql"))
    assert migrations, "overlay lacks the supersede schema migration"
    assert "SUPERSEDED" in migrations[0].read_text(encoding="utf-8")


def test_public_seed_does_not_contain_reference_semantics():
    seed_service = (SEED / SERVICE).read_text(encoding="utf-8")
    assert "IGNORED_LATE_DECISION" not in seed_service
    assert "route-superseded" not in seed_service
    seeded = subprocess.run(
        ["git", "status", "--porcelain", "--", str(SEED)],
        capture_output=True, text=True, cwd=REPO_ROOT)
    assert seeded.returncode == 0 and seeded.stdout.strip() == "", (
        "public seed drifted: " + seeded.stdout)


def test_baseline_seed_fails_the_supersede_check(tmp_path):
    """Red control: the unpatched baseline rejects the supersede submission."""
    copied = tmp_path / "seed"
    shutil.copytree(SEED, copied)
    from scripts.document_flow import install as _reparse_probe  # noqa: F401
    command_service = (copied / SERVICE).read_text(encoding="utf-8")
    assert "IGNORED_LATE_DECISION" not in command_service
    assert "already has a pending route" in command_service


def test_overlay_applies_to_a_fresh_seed_copy(tmp_path):
    copied = tmp_path / "seed"
    shutil.copytree(SEED, copied)
    overlay = json.loads(OVERLAY_MANIFEST.read_text(encoding="utf-8"))
    for entry in overlay["files"]:
        source = PATCH / entry["path"]
        relative = Path(entry["path"]).relative_to("overlay")
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    patched = (copied / SERVICE).read_text(encoding="utf-8")
    assert "IGNORED_LATE_DECISION" in patched
    assert (copied / "workflow-service/src/main/resources/db/migration"
            / "V4__reference_supersede.sql").is_file()


def test_live_reference_scenarios_match_the_interpreter(tmp_path):
    repository = os.environ.get("J03_MAVEN_REPOSITORY")
    if not repository:
        pytest.skip("live reference run not selected; portable checks passed")
    copied = tmp_path / "seed"
    shutil.copytree(SEED, copied)
    overlay = json.loads(OVERLAY_MANIFEST.read_text(encoding="utf-8"))
    for entry in overlay["files"]:
        source = PATCH / entry["path"]
        relative = Path(entry["path"]).relative_to("overlay")
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    mvn = shutil.which("mvn")
    if not mvn:
        pytest.skip("mvn is not on PATH for this shell")
    environment = dict(os.environ)
    environment.setdefault("JAVA_HOME", os.environ.get("J03_JAVA_HOME", ""))
    finished = subprocess.run(
        [mvn, "--offline", "-Dmaven.repo.local=" + repository,
         "-f", str(copied / "pom.xml"), "-pl", "workflow-service", "-am",
         "test", "-Pdb-integration", "-Dtest=ReferenceSupersedeHarness",
         "-Dsurefire.failIfNoSpecifiedTests=false"],
        capture_output=True, text=True, timeout=1800, env=environment,
        cwd=str(copied))
    assert finished.returncode == 0, (
        "reference harness failed:\n" + finished.stdout[-4000:]
        + "\n" + finished.stderr[-2000:])

    outcomes = json.loads((copied / "workflow-service/target"
                           / "reference-supersede-outcomes.json"
                           ).read_text(encoding="utf-8"))
    scenarios = {scenario["id"]: scenario for scenario in outcomes["scenarios"]}
    for scenario_id, scenario in scenarios.items():
        operations = scenario["operations"]
        expected = _load_interpreter().reduce(operations)
        document_id = operations[0]["document_id"]
        expected_states = {
            key[1]: route.state
            for key, route in expected.documents[document_id].routes.items()}
        actual_states = {route["version"]: route["state"]
                         for route in scenario["routes"].values()}
        assert actual_states == expected_states, (
            scenario_id + ": reference diverged from the interpreter")
        expected_workflow_kinds = sorted(
            ("j03.workflow.decision-ignored"
             if entry.kind == "IGNORED_LATE_DECISION" else entry.kind)
            for entry in expected.audit[document_id]
            if entry.kind.startswith(("j03.workflow.", "IGNORED_", "ACTOR_",
                                      "EXPERT_", "UNSUPPORTED_")))
        actual_workflow_kinds = sorted(
            kind for kinds in scenario["outbox_by_route"].values()
            for kind in kinds)
        assert actual_workflow_kinds == expected_workflow_kinds, (
            scenario_id + ": workflow event kinds diverged")


def _load_interpreter():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "j03_reference_interpreter",
        CASE_ROOT / "oracle" / "interpreter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
