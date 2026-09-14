"""Snapshot-bound Docker Compose runner for the private J03 system judge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
from typing import Callable

COMPLETED = 0
PRODUCT_BUILD_FAILURE = 1
INVOCATION_ERROR = 2
INFRASTRUCTURE_INVALID = 3


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class SystemEvidence:
    run_id: str
    snapshot_sha256: str
    classification: str
    exit_code: int
    phase: str
    commands: list[dict] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)


def subprocess_executor(argv, *, cwd, env=None, timeout=None) -> CommandResult:
    started = time.monotonic_ns()
    try:
        finished = subprocess.run(argv, cwd=cwd, env=env, timeout=timeout,
                                  capture_output=True, text=True, shell=False)
    except OSError as failure:
        return CommandResult(tuple(argv), 127, "", str(failure),
                             (time.monotonic_ns() - started) // 1_000_000)
    return CommandResult(tuple(argv), finished.returncode, finished.stdout, finished.stderr,
                         (time.monotonic_ns() - started) // 1_000_000)


def tree_identity(root: Path) -> str:
    root = root.resolve(strict=True)
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("snapshot contains a link boundary")
        relative = path.relative_to(root).as_posix()
        digest.update(("D\0" if path.is_dir() else "F\0").encode() + relative.encode() + b"\0")
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class SystemRunner:
    COMPILE_MARKERS = ("compilation error", "cannot find symbol", "maven-compiler-plugin")

    def __init__(self, executor: Callable = subprocess_executor):
        self._executor = executor

    def execute(self, snapshot: Path, run_id: str, evidence_root: Path) -> SystemEvidence:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,47}", run_id):
            raise ValueError("run_id must be a safe lowercase identifier")
        snapshot = snapshot.resolve(strict=True)
        identity = tree_identity(snapshot)
        evidence_root.mkdir(parents=True, exist_ok=False)
        project = "j03-" + run_id
        base = ["docker", "compose", "--project-directory", str(snapshot),
                "--project-name", project, "-f", str(snapshot / "compose.yaml")]
        environment = dict(os.environ)
        environment.update({"J03_RUN_ID": run_id, "J03_COMPOSE_PROJECT": project})
        for name in ("J03_POSTGRES_PASSWORD", "J03_DOCUMENT_DB_PASSWORD",
                     "J03_WORKFLOW_DB_PASSWORD", "J03_AUDIT_DB_PASSWORD",
                     "J03_JUDGE_DB_PASSWORD"):
            environment.setdefault(name, secrets.token_urlsafe(24))
        evidence = SystemEvidence(run_id, identity, "infrastructure-invalid", 3, "build")

        maven = [shutil.which("mvn") or "mvn", "--offline"]
        if environment.get("J03_MAVEN_REPOSITORY"):
            maven.append("-Dmaven.repo.local=" + environment["J03_MAVEN_REPOSITORY"])
        maven += ["-DskipTests", "package", "dependency:copy-dependencies",
                  "-DincludeScope=runtime", "-DoutputDirectory=target/dependency"]
        product = self._run(maven, snapshot, environment, 1800, evidence)
        if product.exit_code:
            combined = (product.stdout + "\n" + product.stderr).lower()
            if any(marker in combined for marker in self.COMPILE_MARKERS):
                evidence.classification = "product-build-failure"
                evidence.exit_code = PRODUCT_BUILD_FAILURE
            self._diagnose(base, snapshot, environment, evidence)
            self._save(evidence_root, evidence)
            return evidence

        build = self._run(base + ["build"], snapshot, environment, 1800, evidence)
        if build.exit_code:
            combined = (build.stdout + "\n" + build.stderr).lower()
            if any(marker in combined for marker in self.COMPILE_MARKERS):
                evidence.classification = "product-build-failure"
                evidence.exit_code = PRODUCT_BUILD_FAILURE
            self._diagnose(base, snapshot, environment, evidence)
            self._save(evidence_root, evidence)
            return evidence

        up = self._run(base + ["up", "-d", "--wait", "--wait-timeout", "180"],
                       snapshot, environment, 300, evidence)
        if up.exit_code:
            evidence.phase = "startup"
            self._diagnose(base, snapshot, environment, evidence)
            self._cleanup(base, snapshot, environment, evidence)
            self._save(evidence_root, evidence)
            return evidence

        evidence.phase = "readiness"
        ready = self._run(base + ["ps", "--format", "json"], snapshot, environment, 30, evidence)
        if ready.exit_code:
            self._diagnose(base, snapshot, environment, evidence)
            self._cleanup(base, snapshot, environment, evidence)
            self._save(evidence_root, evidence)
            return evidence

        evidence.classification = "completed"
        evidence.exit_code = COMPLETED
        evidence.phase = "complete"
        self._diagnose(base, snapshot, environment, evidence)
        self._cleanup(base, snapshot, environment, evidence)
        self._save(evidence_root, evidence)
        return evidence

    def _run(self, argv, cwd, env, timeout, evidence):
        result = self._executor(argv, cwd=cwd, env=env, timeout=timeout)
        evidence.commands.append(_receipt(result, argv))
        return result

    def _diagnose(self, base, cwd, env, evidence):
        for suffix in (["ps", "--all", "--format", "json"], ["logs", "--no-color", "--timestamps"]):
            result = self._executor(base + suffix, cwd=cwd, env=env, timeout=60)
            evidence.diagnostics.append(_receipt(result, base + suffix))

    def _cleanup(self, base, cwd, env, evidence):
        result = self._executor(base + ["down", "--volumes", "--remove-orphans"],
                                cwd=cwd, env=env, timeout=180)
        evidence.commands.append(_receipt(result, base + ["down", "--volumes", "--remove-orphans"]))

    @staticmethod
    def _save(root, evidence):
        (root / "system.json").write_text(
            json.dumps(asdict(evidence), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8")


def _receipt(result: CommandResult, argv) -> dict:
    return {"argv": list(argv), "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
            "stdout": result.stdout, "stderr": result.stderr}
