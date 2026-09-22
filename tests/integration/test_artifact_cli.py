from deltafuse import __version__ as FW_VERSION
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
import pytest


from deltafuse.core.assets import get_installed_lock_hash

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def isolated_wheel_venv(tmp_path_factory):
    """Builds and installs deltafuse wheel into a clean isolated virtualenv."""
    if importlib.util.find_spec("pip") is None:
        pytest.fail("blocked: pip is unavailable; wheel smoke cannot run silently skipped")
    root_tmp = tmp_path_factory.mktemp("isolated_wheel_fixture")
    dist = root_tmp / "dist"

    check = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_assets.py"), "--check"],
        capture_output=True, text=True,
    )
    assert check.returncode == 0, f"asset sync drift: {check.stdout}\n{check.stderr}"

    build = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(REPO_ROOT)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, f"wheel build failed: {build.stdout}\n{build.stderr}"
    wheels = list(dist.glob("deltafuse-*.whl"))
    assert wheels, "No wheel built"
    wheel = wheels[0]

    venv_dir = root_tmp / "venv"
    venv.create(venv_dir, with_pip=True)
    pip_python = venv_dir / "Scripts" / "python.exe"
    if not pip_python.is_file():
        pip_python = venv_dir / "bin" / "python"

    install = subprocess.run(
        [str(pip_python), "-I", "-m", "pip", "install", str(wheel)],
        capture_output=True, text=True,
    )
    assert install.returncode == 0, f"wheel install failed: {install.stdout}\n{install.stderr}"

    return str(pip_python)


def test_subprocess_artifact_describe():
    cmd = [sys.executable, "-m", "deltafuse.cli", "artifact", "describe", "--kind", "task", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["kind"] == "task"
    assert "creatable_semantic_fields" in data or "allowed_semantic_fields" in data


def test_subprocess_artifact_create_via_stdin(tmp_path):
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    lock_hash = get_installed_lock_hash()
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        f"  content_hash: {lock_hash}\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    chg_dir = tmp_path / "docs" / "changes" / "CHG-001"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-001\nstatus: active\n", encoding="utf-8")
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")


    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-100",
        "semantic_payload": {
            "title": "Subprocess Created Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-100: Subprocess Created Task\n\nSubprocess test body.",
    }
    input_text = json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    receipt = json.loads(proc.stdout)
    assert receipt["outcome"] == "committed"

    task_file = tmp_path / "tasks" / "TASK-100.md"
    assert task_file.is_file()
    assert "Subprocess Created Task" in task_file.read_text(encoding="utf-8")


def test_subprocess_artifact_core_owned_field_denied(tmp_path):
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    lock_hash = get_installed_lock_hash()
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        f"  content_hash: {lock_hash}\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    chg_dir = tmp_path / "docs" / "changes" / "CHG-001"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-001\nstatus: active\n", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-101",
        "semantic_payload": {
            "title": "Denied Task",
            "status": "verified",
        },
    }
    input_text = json.dumps(payload)
    proc = subprocess.run(cmd, input=input_text, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 3
    assert not (tmp_path / "tasks" / "TASK-101.md").exists()



def test_subprocess_artifact_update_retry_and_idempotency(tmp_path):
    import hashlib

    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    lock_hash = get_installed_lock_hash()
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        f"  content_hash: {lock_hash}\n"
        "workflow:\n"
        "  call_width: wide\n"
        "  auto_accept_decisions: false\n",
        encoding="utf-8",
    )
    chg_dir = tmp_path / "docs" / "changes" / "CHG-001"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-001\nstatus: active\n", encoding="utf-8")
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-001\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")


    cmd_create = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    create_payload = {
        "request_id": "cli-req-cr-1",
        "identity": "TASK-200",
        "semantic_payload": {
            "title": "CLI Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-200: CLI Task\n\nBody prose",
    }
    proc = subprocess.run(cmd_create, input=json.dumps(create_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    cr_receipt = json.loads(proc.stdout)

    task_file = tmp_path / "tasks" / "TASK-200.md"
    h0 = hashlib.sha256(task_file.read_bytes()).hexdigest()

    cmd_update = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "update",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    update_payload = {
        "request_id": "cli-req-up-1",
        "target": "tasks/TASK-200.md",
        "expected_sha256": h0,
        "patch": {"set": [{"path": "/kind", "value": "refactor"}]},
    }
    proc = subprocess.run(cmd_update, input=json.dumps(update_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    up_receipt1 = json.loads(proc.stdout)
    assert up_receipt1["changed"] is True

    proc = subprocess.run(cmd_update, input=json.dumps(update_payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    up_receipt2 = json.loads(proc.stdout)
    assert up_receipt2["transaction_id"] == up_receipt1["transaction_id"]
    assert up_receipt2["changed"] is True


def test_aw37_cli_create_missing_change_authority_rejected(tmp_path):
    from deltafuse.core.assets import get_installed_lock_hash
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n"
        f"  content_hash: {get_installed_lock_hash()}\n",
        encoding="utf-8",
    )
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-370\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    # Ensure no change.yaml exists
    change_yaml = tmp_path / "change.yaml"
    if change_yaml.is_file():
        change_yaml.unlink()

    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-370",
        "semantic_payload": {
            "title": "Missing Change Authority Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "Body",
    }
    proc = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 3
    assert not (tmp_path / "tasks" / "TASK-370.md").exists()


def test_aw38_cli_create_missing_content_hash_rejected(tmp_path):
    (tmp_path / ".deltafuse").mkdir(parents=True, exist_ok=True)
    # Lock retains source but omits content_hash
    (tmp_path / ".deltafuse" / "lock.yaml").write_text(
        "schema_version: 3\n"
        "framework:\n"
        f"  version: {FW_VERSION}\n"
        "  source: deltafuse\n",
        encoding="utf-8",
    )
    (tmp_path / "change.yaml").write_text(
        "schema_version: 3\nid: CHG-380\ntitle: AW38 Test\nstatus: implement\n",
        encoding="utf-8",
    )
    (tmp_path / "slices").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slices" / "SLICE-01.md").write_text("---\nid: SLICE-01\nchange: CHG-380\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
    (tmp_path / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "deltafuse.cli",
        "artifact", "create",
        "--kind", "task",
        "--change", str(tmp_path),
        "--input", "-",
        "--json",
    ]
    payload = {
        "identity": "TASK-380",
        "semantic_payload": {
            "title": "Missing Content Hash Lock Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "Body",
    }
    proc = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode != 0
    assert not (tmp_path / "tasks" / "TASK-380.md").exists()


def test_isolated_wheel_artifact_describe(isolated_wheel_venv, tmp_path):
    clean_workdir = tmp_path / "clean_describe"
    clean_workdir.mkdir()
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    cmd = [isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "describe", "--kind", "task", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(clean_workdir), env=clean_env)
    assert proc.returncode == 0, f"describe failed: {proc.stdout}\n{proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["kind"] == "task"
    assert "creatable_semantic_fields" in data or "allowed_semantic_fields" in data


def test_isolated_wheel_artifact_create_update_validate(isolated_wheel_venv, tmp_path):
    clean_workdir = tmp_path / "clean_ops"
    clean_workdir.mkdir()
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    repo_dir = clean_workdir / "repo"
    init_res = subprocess.run(
        [isolated_wheel_venv, "-m", "deltafuse", "init", str(repo_dir)],
        capture_output=True, text=True, cwd=str(clean_workdir), env=clean_env,
    )
    assert init_res.returncode == 0, f"init failed: {init_res.stdout}\n{init_res.stderr}"

    chg_dir = repo_dir / "docs" / "changes" / "CHG-100"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-100\nstatus: active\n", encoding="utf-8")
    (repo_dir / "slices").mkdir(parents=True, exist_ok=True)
    (repo_dir / "slices" / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-100\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n",
        encoding="utf-8",
    )
    (repo_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (repo_dir / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    # 1. Create artifact via wheel
    create_payload = {
        "identity": "TASK-100",
        "semantic_payload": {
            "title": "Wheel Isolated Task",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-100: Wheel Isolated Task\n\nBody content.",
    }
    create_cmd = [
        isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
        "--kind", "task",
        "--change", str(repo_dir),
        "--input", "-",
        "--json",
    ]
    proc_cr = subprocess.run(
        create_cmd,
        input=json.dumps(create_payload),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_cr.returncode == 0, f"wheel create failed: {proc_cr.stdout}\n{proc_cr.stderr}"
    receipt = json.loads(proc_cr.stdout)
    assert receipt["outcome"] == "committed"

    task_file = repo_dir / "tasks" / "TASK-100.md"
    assert task_file.is_file()
    assert "Wheel Isolated Task" in task_file.read_text(encoding="utf-8")

    # 2. Validate artifact via wheel
    val_cmd = [
        isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "validate",
        "--kind", "task",
        "--change", str(repo_dir),
        "--target", "tasks/TASK-100.md",
        "--json",
    ]
    proc_val = subprocess.run(
        val_cmd,
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_val.returncode == 0, f"wheel validate failed: {proc_val.stdout}\n{proc_val.stderr}"
    val_data = json.loads(proc_val.stdout)
    assert val_data["valid"] is True

    # 3. Update artifact via wheel
    import hashlib
    h0 = hashlib.sha256(task_file.read_bytes()).hexdigest()
    update_payload = {
        "target": "tasks/TASK-100.md",
        "expected_sha256": h0,
        "patch": {"set": [{"path": "/kind", "value": "refactor"}]},
    }
    up_cmd = [
        isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "update",
        "--kind", "task",
        "--change", str(repo_dir),
        "--input", "-",
        "--json",
    ]
    proc_up = subprocess.run(
        up_cmd,
        input=json.dumps(update_payload),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_up.returncode == 0, f"wheel update failed: {proc_up.stdout}\n{proc_up.stderr}"
    up_data = json.loads(proc_up.stdout)
    assert up_data["changed"] is True

    # 4. Validate artifact after update
    proc_val2 = subprocess.run(
        val_cmd,
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_val2.returncode == 0
    val_data2 = json.loads(proc_val2.stdout)
    assert val_data2["valid"] is True


def test_isolated_wheel_artifact_input_validation_controls(isolated_wheel_venv, tmp_path):
    clean_workdir = tmp_path / "clean_tamper"
    clean_workdir.mkdir()
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    repo_dir = clean_workdir / "repo"
    init_res = subprocess.run(
        [isolated_wheel_venv, "-m", "deltafuse", "init", str(repo_dir)],
        capture_output=True, text=True, cwd=str(clean_workdir), env=clean_env,
    )
    assert init_res.returncode == 0

    chg_dir = repo_dir / "docs" / "changes" / "CHG-200"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-200\nstatus: active\n", encoding="utf-8")
    (repo_dir / "slices").mkdir(parents=True, exist_ok=True)
    (repo_dir / "slices" / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-200\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n",
        encoding="utf-8",
    )
    (repo_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (repo_dir / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    # Case 1: Malformed JSON envelope input
    proc_bad_json = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
            "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
        ],
        input="{not valid json",
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_bad_json.returncode != 0

    # Case 2: Missing required identity field in create envelope
    proc_missing_id = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
            "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
        ],
        input=json.dumps({"semantic_payload": {"title": "No ID"}}),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_missing_id.returncode == 2

    # Case 3: Create valid task first
    valid_payload = {
        "identity": "TASK-200",
        "semantic_payload": {
            "title": "Wheel Task 200",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-200: Wheel Task 200\n\nBody content.",
    }
    proc_cr = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
            "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
        ],
        input=json.dumps(valid_payload),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_cr.returncode == 0

    # Case 4: Tampered expected_sha256 in update envelope
    tampered_update_payload = {
        "target": "tasks/TASK-200.md",
        "expected_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "patch": {"set": [{"path": "/kind", "value": "refactor"}]},
    }
    proc_tampered_hash = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "update",
            "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
        ],
        input=json.dumps(tampered_update_payload),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_tampered_hash.returncode == 4

    # Case 5: Core-owned status mutation rejected in update
    import hashlib
    task_file = repo_dir / "tasks" / "TASK-200.md"
    current_hash = hashlib.sha256(task_file.read_bytes()).hexdigest()
    core_field_payload = {
        "target": "tasks/TASK-200.md",
        "expected_sha256": current_hash,
        "patch": {"set": [{"path": "/status", "value": "verified"}]},
    }
    proc_core_field = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "update",
            "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
        ],
        input=json.dumps(core_field_payload),
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert proc_core_field.returncode == 3


def test_isolated_wheel_packaged_schema_removal_and_corruption(isolated_wheel_venv, tmp_path):
    """AW41-F2..F4: In an isolated installed wheel, physically remove the packaged schema,

    then separately corrupt its bytes without repairing manifest. Invoke actual Writer create/update
    and assert asset_resolution_failed (exit code 5) with unchanged product artifacts and no receipt.
    """
    import hashlib

    clean_workdir = tmp_path / "pkg_corruption_test"
    clean_workdir.mkdir()
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    # 1. Verify module import origin is strictly within the isolated venv site-packages
    loc_proc = subprocess.run(
        [isolated_wheel_venv, "-c", "import deltafuse, pathlib; print(pathlib.Path(deltafuse.__file__).resolve().parent)"],
        capture_output=True, text=True, env=clean_env, cwd=str(clean_workdir),
    )
    assert loc_proc.returncode == 0
    pkg_dir = Path(loc_proc.stdout.strip())
    assert "site-packages" in str(pkg_dir) or "dist-packages" in str(pkg_dir)
    assert REPO_ROOT not in pkg_dir.parents

    schema_file = pkg_dir / "assets" / "contracts" / "artifact-writer.schema.yaml"
    assert schema_file.is_file(), f"Packaged schema missing at {schema_file}"
    orig_bytes = schema_file.read_bytes()
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()

    repo_dir = clean_workdir / "repo"
    init_res = subprocess.run(
        [isolated_wheel_venv, "-m", "deltafuse", "init", str(repo_dir)],
        capture_output=True, text=True, cwd=str(clean_workdir), env=clean_env,
    )
    assert init_res.returncode == 0

    def txn_files() -> set[str]:
        """AW44-R3: denied writes must leave no journal/receipt records."""
        files: set[str] = set()
        for sub in ("journal", "receipts"):
            d = repo_dir / ".deltafuse" / sub
            if d.is_dir():
                files.update(p.name for p in d.glob("*.json"))
        return files

    chg_dir = repo_dir / "docs" / "changes" / "CHG-201"
    chg_dir.mkdir(parents=True, exist_ok=True)
    (chg_dir / "change.yaml").write_text("id: CHG-201\nstatus: active\n", encoding="utf-8")
    (repo_dir / "slices").mkdir(parents=True, exist_ok=True)
    (repo_dir / "slices" / "SLICE-01.md").write_text(
        "---\nid: SLICE-01\nchange: CHG-201\ntitle: Slice 1\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n",
        encoding="utf-8",
    )
    (repo_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (repo_dir / "docs" / "spec" / "overview.md").write_text("# Spec\n", encoding="utf-8")

    task_payload = {
        "identity": "TASK-201",
        "semantic_payload": {
            "title": "Wheel Task 201",
            "kind": "feature",
            "slice": "SLICE-01",
            "depends_on": [],
            "requirement_delta": "none",
            "spec_refs": ["docs/spec/overview.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1000, "max_files": 5},
        },
        "body": "# TASK-201: Wheel Task 201\n\nBody content.",
    }

    try:
        txn_before = txn_files()
        # Probe 1: Physically remove packaged schema
        schema_file.unlink()
        assert not schema_file.exists()

        proc_del = subprocess.run(
            [
                isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
                "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
            ],
            input=json.dumps(task_payload),
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(clean_workdir), env=clean_env,
        )
        assert proc_del.returncode == 5, f"Expected exit code 5 on deleted schema, got {proc_del.returncode}: {proc_del.stderr}"
        del_out = json.loads(proc_del.stdout)
        assert del_out["ok"] is False
        assert del_out["error"]["code"] == "asset_resolution_failed"
        assert not (repo_dir / "tasks" / "TASK-201.md").exists(), "Product artifact must not be created on missing schema"
        assert txn_files() == txn_before, "denied create must not add journal/receipt records"

        # Restore original bytes cleanly
        schema_file.write_bytes(orig_bytes)
        assert hashlib.sha256(schema_file.read_bytes()).hexdigest() == orig_hash

        # Create TASK-201 with intact schema to have existing artifact for update test
        proc_create_ok = subprocess.run(
            [
                isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
                "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
            ],
            input=json.dumps(task_payload),
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(clean_workdir), env=clean_env,
        )
        assert proc_create_ok.returncode == 0
        task_file = repo_dir / "tasks" / "TASK-201.md"
        assert task_file.is_file()
        task_bytes_before = task_file.read_bytes()
        task_hash_before = hashlib.sha256(task_bytes_before).hexdigest()

        txn_before = txn_files()
        # Probe 2: Corrupt packaged schema bytes without repairing manifest
        schema_file.write_bytes(b"invalid_yaml: [broken: {content\n")
        assert hashlib.sha256(schema_file.read_bytes()).hexdigest() != orig_hash

        # Attempt to create TASK-202 under corrupted schema
        task_payload_2 = dict(task_payload)
        task_payload_2["identity"] = "TASK-202"
        proc_tamper_create = subprocess.run(
            [
                isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "create",
                "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
            ],
            input=json.dumps(task_payload_2),
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(clean_workdir), env=clean_env,
        )
        assert proc_tamper_create.returncode == 5, f"Expected exit code 5 on tampered schema, got {proc_tamper_create.returncode}: {proc_tamper_create.stderr}"
        tamper_cr_out = json.loads(proc_tamper_create.stdout)
        assert tamper_cr_out["ok"] is False
        assert tamper_cr_out["error"]["code"] == "asset_resolution_failed"
        assert not (repo_dir / "tasks" / "TASK-202.md").exists(), "Product artifact must not be created on corrupted schema"
        assert txn_files() == txn_before, "denied create must not add journal/receipt records"

        # Probe 3: Attempt to update TASK-201 under corrupted schema
        update_payload = {
            "target": "tasks/TASK-201.md",
            "expected_sha256": task_hash_before,
            "patch": {"set": [{"path": "/kind", "value": "refactor"}]},
        }
        proc_tamper_update = subprocess.run(
            [
                isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "update",
                "--kind", "task", "--change", str(repo_dir), "--input", "-", "--json",
            ],
            input=json.dumps(update_payload),
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(clean_workdir), env=clean_env,
        )
        assert proc_tamper_update.returncode == 5, f"Expected exit code 5 on update with tampered schema, got {proc_tamper_update.returncode}: {proc_tamper_update.stderr}"
        tamper_up_out = json.loads(proc_tamper_update.stdout)
        assert tamper_up_out["ok"] is False
        assert tamper_up_out["error"]["code"] == "asset_resolution_failed"
        assert task_file.read_bytes() == task_bytes_before, "Product artifact must remain unchanged on rejected update"
        assert txn_files() == txn_before, "denied update must not add journal/receipt records"

    finally:
        # Guarantee exact restoration of original packaged schema bytes
        if schema_file.parent.exists():
            schema_file.write_bytes(orig_bytes)
            assert hashlib.sha256(schema_file.read_bytes()).hexdigest() == orig_hash

    # Final control: Verify describe and validate work cleanly after restoration
    desc_proc = subprocess.run(
        [isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "describe", "--kind", "task", "--json"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert desc_proc.returncode == 0
    desc_data = json.loads(desc_proc.stdout)
    assert desc_data["kind"] == "task"

    val_proc = subprocess.run(
        [
            isolated_wheel_venv, "-m", "deltafuse.cli", "artifact", "validate",
            "--kind", "task", "--change", str(repo_dir), "--target", "tasks/TASK-201.md", "--json",
        ],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(clean_workdir), env=clean_env,
    )
    assert val_proc.returncode == 0
    val_data = json.loads(val_proc.stdout)
    assert val_data["valid"] is True
