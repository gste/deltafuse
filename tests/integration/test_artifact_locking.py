"""Integration tests for shared product mutation lock (AW-08)."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from deltafuse.core.artifact_lock import (
    ArtifactLockError,
    ProductMutationLock,
)


def test_product_mutation_lock_mutual_exclusion(tmp_path: Path):
    """ProductMutationLock prevents concurrent acquisition by a second caller."""
    root = tmp_path / "repo"
    root.mkdir()

    lock1 = ProductMutationLock(root, timeout=0.1)
    lock2 = ProductMutationLock(root, timeout=0.1)

    with lock1:
        # Second lock acquisition must fail with lock_acquisition_failed
        with pytest.raises(ArtifactLockError) as exc_info:
            with lock2:
                pass

        assert exc_info.value.code == "lock_acquisition_failed"


def test_product_mutation_lock_reentry_or_sequential(tmp_path: Path):
    """Sequential lock acquisition succeeds after first lock releases."""
    root = tmp_path / "repo"
    root.mkdir()

    with ProductMutationLock(root, timeout=0.5):
        pass

    # Now second lock acquisition succeeds
    with ProductMutationLock(root, timeout=0.5):
        pass


def test_stale_lock_recovery_dead_pid(tmp_path: Path):
    """Stale lock owned by dead PID on local machine is safely recovered."""
    root = tmp_path / "repo"
    lock_dir = root / ".deltafuse" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "mutation.lock"

    # Write stale lock with nonexistent PID (999999)
    stale_pid = 999999
    lock_file.write_text(f"pid={stale_pid}\ntime=1000.0\n", encoding="utf-8")

    # Acquisition should detect dead PID and recover lock successfully
    lock = ProductMutationLock(root, timeout=0.5)
    with lock:
        assert lock._file_obj is not None
        lock._file_obj.seek(0)
        content = lock._file_obj.read()
        assert f"pid={os.getpid()}" in content


def test_active_pid_lock_refused(tmp_path: Path):
    """Lock owned by active PID (current process) blocks secondary non-reentrant acquisition."""
    root = tmp_path / "repo"
    lock_dir = root / ".deltafuse" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / "mutation.lock"

    # Simulate lock held by current process in file
    lock_file.write_text(f"pid={os.getpid()}\ntime=100000000.0\n", encoding="utf-8")

    lock2 = ProductMutationLock(root, timeout=0.1)
    with pytest.raises(ArtifactLockError) as exc_info:
        with lock2:
            pass

    assert exc_info.value.code == "lock_acquisition_failed"


def test_evidence_contends_on_product_mutation_lock(tmp_path: Path):
    """Core evidence writing must contend on ProductMutationLock."""
    from deltafuse.core.evidence import write_stamped_evidence

    root = tmp_path / "repo"
    root.mkdir()
    (root / ".deltafuse").mkdir()
    dest = root / "docs" / "changes" / "CHG-01" / "evidence" / "verification" / "run.yaml"

    payload = {
        "schema_version": 3,
        "change": "CHG-001",
        "task": None,
        "phase": "verification",
        "timestamp": "2026-09-19T00:00:00Z",
        "command": "pytest",
        "exit_code": 0,
        "result": "passed",
        "failure_category": None,
        "summary": "OK",
        "changed_paths": [],
        "spec_status": "unchanged",
        "base_revision": "sha256:" + ("0" * 64),
    }



    lock = ProductMutationLock(root, timeout=0.1)
    with lock:
        # Calling write_stamped_evidence while lock is held must fail/contend on lock
        with pytest.raises(ArtifactLockError) as exc_info:
            write_stamped_evidence(dest, payload, root, lock_timeout=0.1)
        assert exc_info.value.code == "lock_acquisition_failed"

