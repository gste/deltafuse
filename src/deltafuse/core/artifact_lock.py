"""Mutation locking and optimistic concurrency (AW-08).

Provides shared product mutation locking across processes/threads,
lock liveness inspection and safe dead-PID recovery, whole-file optimistic hash validation,
and pre-commit authority fingerprint recheck.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable


class ArtifactLockError(Exception):
    """Raised when mutation lock acquisition or optimistic concurrency recheck fails."""

    def __init__(self, message: str, *, code: str, path: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.message = message
        self.code = code
        self.path = path


_lock_mutex = threading.Lock()


def _is_pid_alive(pid: int) -> bool:
    """Return True if process with PID is active on local system."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return True
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def resolve_product_root(path: Path | str) -> Path:
    from deltafuse.core.fsm import find_repo_root
    p = Path(path).resolve()
    if p.is_file():
        p = p.parent
    if (p / ".deltafuse").is_dir():
        return p
    root = find_repo_root(p)
    if not (root / ".deltafuse").is_dir() and not (root / "docs").is_dir() and root == p.parent:
        return p
    return root


class ProductMutationLock:
    """Shared product-level mutation lock ensuring single-writer concurrency."""

    def __init__(self, product_root: Path, timeout: float = 5.0):
        self.product_root = resolve_product_root(product_root)
        self.timeout = timeout
        self.lock_dir = self.product_root / ".deltafuse" / "locks"
        self.lock_file = self.lock_dir / "mutation.lock"
        self._file_obj: Any = None
        self._acquired_mutex = False

    def acquire(self) -> None:
        start_time = time.time()
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        while True:
            if _lock_mutex.acquire(blocking=False):
                self._acquired_mutex = True
                try:
                    if self._try_file_lock():
                        return
                except Exception:
                    _lock_mutex.release()
                    self._acquired_mutex = False
                    raise
                # File lock could not be acquired (held by another process or active lock file)
                _lock_mutex.release()
                self._acquired_mutex = False

            if (time.time() - start_time) >= self.timeout:
                raise ArtifactLockError(
                    f"Product mutation lock acquisition timed out on '{self.lock_file}'",
                    code="lock_acquisition_failed",
                    path=str(self.lock_file),
                )
            time.sleep(0.02)

    def _try_file_lock(self) -> bool:
        if self.lock_file.exists():
            try:
                content = self.lock_file.read_text(encoding="utf-8")
                owner_pid = None
                for line in content.splitlines():
                    if line.startswith("pid="):
                        owner_pid = int(line.split("=", 1)[1].strip())
                if owner_pid is not None and owner_pid != os.getpid():
                    if not _is_pid_alive(owner_pid):
                        # Safely recover stale lock from dead process
                        try:
                            self.lock_file.unlink(missing_ok=True)
                        except OSError:
                            pass
                    else:
                        # Owner PID is alive
                        return False
                elif owner_pid == os.getpid():
                    # Active lock owned by current process already exists
                    return False
            except Exception:
                pass

        try:
            f = open(self.lock_file, "a+", encoding="utf-8")
            f.seek(0)
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    f.close()
                    return False
            else:
                import fcntl

                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    f.close()
                    return False

            f.seek(0)
            f.truncate()
            f.write(f"pid={os.getpid()}\ntime={time.time()}\n")
            f.flush()
            self._file_obj = f
            return True

        except OSError:
            return False

    def release(self) -> None:
        if self._file_obj is not None:
            try:
                if os.name == "nt":
                    import msvcrt

                    self._file_obj.seek(0)
                    try:
                        msvcrt.locking(self._file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl

                    try:
                        fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                self._file_obj.close()
            except OSError:
                pass
            finally:
                self._file_obj = None
                try:
                    self.lock_file.unlink(missing_ok=True)
                except OSError:
                    pass

        if self._acquired_mutex:
            _lock_mutex.release()
            self._acquired_mutex = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def validate_expected_hash(target_path: Path, expected_sha256: str) -> None:
    """Validate target file existence and whole-file expected SHA256 digest."""
    target_path = Path(target_path)
    if not target_path.is_file():
        raise ArtifactLockError(
            f"Target file '{target_path}' does not exist for validation",
            code="target_not_found",
            path=str(target_path),
        )

    actual_bytes = target_path.read_bytes()
    actual_hash = hashlib.sha256(actual_bytes).hexdigest()
    if actual_hash != expected_sha256:
        raise ArtifactLockError(
            f"Target file hash mismatch for '{target_path}': expected {expected_sha256}, got {actual_hash}",
            code="stale_target",
            path=str(target_path),
        )


def revalidate_authority(auth_context: Any, current_context_fn: Callable[[], Any]) -> None:
    """Re-verify authority context fingerprint and attributes prior to commit under lock."""
    if auth_context is None:
        raise ArtifactLockError("Null authorization context", code="null_authorization_context")
    fresh_ctx = current_context_fn()
    inactive_stages = {
        "halted",
        "accepted",
        "converged",
        "archived",
        "rejected",
        "duplicate",
        "superseded",
        "not-reproduced",
        "missing_change_authority",
        "invalid_change_stage",
    }
    stage_val = (getattr(fresh_ctx, "stage", "") or "").lower()
    if stage_val in inactive_stages:
        raise ArtifactLockError(f"Authority context stage '{stage_val}' is invalid, revoked or inactive", code="authority_revoked")

    actor1 = (getattr(auth_context, "actor", "") or "").lower()
    actor2 = (getattr(fresh_ctx, "actor", "") or "").lower()
    work1 = str(getattr(auth_context, "work_item", "") or "").lower()
    work2 = str(getattr(fresh_ctx, "work_item", "") or "").lower()
    stage1 = (getattr(auth_context, "stage", "") or "").lower()
    stage2 = (getattr(fresh_ctx, "stage", "") or "").lower()

    if actor1 != actor2 or work1 != work2 or stage1 != stage2:
        raise ArtifactLockError(
            "Authority context was revoked or invalidated prior to commit",
            code="authority_revoked",
        )

    fp1 = str(getattr(auth_context, "fingerprint", ""))
    fp2 = str(getattr(fresh_ctx, "fingerprint", ""))
    if fp1 != fp2:
        raise ArtifactLockError(
            "Authority context was revoked or invalidated prior to commit",
            code="authority_revoked",
        )


def check_noop_mutation(current_bytes: bytes, candidate_bytes: bytes) -> bool:
    """Return True if candidate bytes match current bytes byte-for-byte (no-op mutation)."""
    return current_bytes == candidate_bytes
