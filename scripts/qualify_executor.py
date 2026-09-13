"""QF-013: release qualification executors and the system boundary.

A release/reference qualification campaign must not run Worker-authored code
(pytest tests the Worker writes) on a machine or in a namespace where the
judge pack, the framework checkout or arbitrary host files are visible. Two
executor kinds exist:

- ``isolated`` — mandatory for release/reference campaigns. The Worker phase
  executes inside a container boundary: only the run sandbox is mounted
  (read/write); the judge pack and the framework checkout are never mounted;
  the network policy of the boundary probe is ``none``. If no isolated
  boundary is available, the campaign must end PENDING before the first
  Worker call — never with in-process execution.
- ``local-dev`` — development only. The in-process runner with L1 staging is
  acceptable here; every campaign capped at this kind can only reach the
  verdict ``non-release``: a green scorecard in local-dev never produces a
  release manifest with ``pass``.

The adversarial boundary probe runs INSIDE the actual boundary (a container
process, not a monkeypatch): it attempts to read a judge-side sentinel, to
find judge-pack directories, to write outside the sandbox and to open a
network connection. Any leak is a BoundaryViolation and blocks the campaign.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

EXECUTOR_KINDS = ("isolated", "local-dev")

# QF-019: classification of one executed command. The SandboxIO layer maps
# this onto its typed tool journal; nothing here depends on judge-side state.
_COMMAND_KINDS = ("ok", "exit", "timeout", "spawn_error", "container_error")

# A 125/126/127 exit of `runtime exec` may be the runtime itself failing
# (container died, daemon error) rather than the guest command. Runtime
# error text is the reliable discriminator; guest output never matches.
_RUNTIME_ERROR = re.compile(r"\b(docker|podman)\b.{0,200}\berror\b|OCI runtime", re.IGNORECASE)


@dataclass
class CommandResult:
    """Outcome of one command executed through a CommandExecutor.

    kind: ok (exit 0) | exit (guest command ran, nonzero) | timeout
    (wall clock exceeded) | spawn_error (command could not be started)
    | container_error (the boundary itself failed). stdout/stderr are kept
    (bounded by the caller); undecodable bytes are replaced and flagged.
    """

    kind: str
    exit_code: int | None
    stdout: str
    stderr: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _COMMAND_KINDS:
            raise ValueError(f"unknown command result kind: {self.kind!r}")

# The adversarial probe runs inside the boundary with this embedded script;
# targets are supplied on stdin so no host path is baked into the image.
PROBE_SCRIPT = r"""
import json, os, socket, sys

targets = json.load(sys.stdin)
results = {}

# 1. Judge-side sentinel must be unreadable by absolute path.
try:
    with open(targets["sentinel"], "rb") as fh:
        fh.read(1)
    results["sentinel_read"] = "LEAK"
except OSError:
    results["sentinel_read"] = "blocked"

# 2. Judge-pack directories must not be reachable on any mounted root.
names = set(targets["search_names"])
hits = []
for root in targets.get("search_roots", [os.sep]):
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep)
        if depth > 8:
            dirnames[:] = []
            continue
        hit = names.intersection(dirnames) | names.intersection(filenames)
        if hit:
            hits.append(dirpath)
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
results["pack_found"] = hits

# 3. Writes outside the sandbox must fail (host paths are not mounted).
write_leak = []
for target in targets.get("write_roots", []):
    probe = os.path.join(target, "deltafuse-boundary-probe")
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("x")
        write_leak.append(target)
    except OSError:
        pass
results["write_leak"] = write_leak

# 4. Network beyond the boundary policy must be refused.
peer = targets.get("forbidden_peer")
if peer:
    host, port = peer.rsplit(":", 1)
    try:
        socket.create_connection((host, int(port)), timeout=3).close()
        results["network"] = "LEAK"
    except OSError:
        results["network"] = "blocked"
else:
    results["network"] = "not-probed"

print(json.dumps(results))
"""


class ExecutorError(Exception):
    """Unknown executor mode or unusable executor definition."""


class ExecutorUnavailable(ExecutorError):
    """No isolated boundary is available on this host (QF-013 item 5)."""


class BoundaryViolation(Exception):
    """The adversarial probe found a leak across the release boundary."""


def _attest(value, provenance: str, **extra) -> dict:
    field = {"value": value, "provenance": provenance}
    field.update(extra)
    return field


class LocalDevExecutor:
    """In-process runner with L1 staging; development only, never release."""

    kind = "local-dev"

    def available(self) -> bool:
        return True

    def attest(self) -> dict:
        return {
            "kind": _attest("local-dev", "declared",
                            basis="runner invocation flag --executor local-dev"),
            "boundary": _attest("in-process", "declared",
                                basis="L1 staging (scripts/qualify_staging.py); no OS boundary"),
            "network_policy": _attest("unrestricted-host", "declared",
                                      basis="Worker commands run with runner rights; "
                                            "local-dev is never release evidence"),
            "release_cap": _attest("non-release", "declared",
                                   basis="QF-013: local-dev verdicts are capped at non-release"),
        }

    def boundary_probe(self, sandbox: Path, sentinel: Path, search_roots: list[str],
                       write_roots: list[str], forbidden_peer: str | None) -> dict:
        # Deliberately not executed: L1 staging cannot host a meaningful
        # boundary probe; local-dev is capped at non-release instead.
        return {"executed": False, "reason": "local-dev boundary probe not applicable"}


# ------------------------------------------------------------ QF-019 executors


class LocalCommandExecutor:
    """CommandExecutor for local-dev: direct subprocess with the staging
    interpreter and allowlist environment. Never used in release mode."""

    kind = "local-dev"

    def __init__(self, interpreter: str | None = None, env: dict | None = None):
        self.interpreter = interpreter
        self.env = env

    def _canonize(self, argv: list[str]) -> list[str]:
        """QF-005: `python ...`/`pytest ...` resolve to the pinned
        interpreter, never through a stray PATH."""
        if not self.interpreter:
            return list(argv)
        head = argv[0].lower()
        if head == "python":
            return [self.interpreter, *argv[1:]]
        if head == "pytest":
            return [self.interpreter, "-m", "pytest", *argv[1:]]
        return list(argv)

    def run(self, argv: list[str], cwd: Path, timeout: int) -> CommandResult:
        argv = self._canonize(argv)
        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self.env,
            )
        except subprocess.TimeoutExpired:
            return CommandResult("timeout", None, "",
                                 f"command timed out after {timeout}s")
        except OSError as ex:
            return CommandResult("spawn_error", None, "", f"cannot execute: {ex}")
        return CommandResult(
            "ok" if proc.returncode == 0 else "exit",
            proc.returncode,
            proc.stdout or "",
            proc.stderr or "",
        )


class ContainerCommandExecutor:
    """QF-019: executes parsed argv inside ONE persistent command container.

    Per run the executor starts a container from the pinned qual image with:
    only the run sandbox mounted (rw), cwd=/sandbox, no network. The host
    passes already-parsed argv to `exec` and receives stdout/stderr/exit
    code. The container never receives qualify.py, helper modules, the bench
    pack or the framework checkout — the Worker phase stays judge-side.
    """

    kind = "isolated"
    container_cwd = "/sandbox"

    def __init__(self, runtime: str, image: str):
        self.runtime = runtime
        self.image = image
        self.sandbox: Path | None = None
        self.container_id: str | None = None

    def start(self, sandbox: Path) -> str:
        """Start the persistent command container for one run."""
        proc = subprocess.run(
            [
                self.runtime, "run", "-d", "--rm", "--network", "none",
                "-v", f"{Path(sandbox).resolve()}:/sandbox",
                "-w", self.container_cwd,
                self.image, "sleep", "infinity",
            ],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            raise ExecutorUnavailable(
                f"command container failed to start (exit {proc.returncode}): "
                f"{((proc.stderr or '') + (proc.stdout or '')).strip()[:300]}"
            )
        cid = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
        if not cid:
            raise ExecutorUnavailable("command container returned no id")
        self.sandbox = Path(sandbox).resolve()
        self.container_id = cid
        return cid

    def run(self, argv: list[str], cwd: Path, timeout: int) -> CommandResult:
        if not self.container_id or self.sandbox is None:
            raise ExecutorError("command container is not started")
        if Path(cwd).resolve() != self.sandbox:
            raise ExecutorError(
                f"cwd {cwd} is not the mounted sandbox {self.sandbox}"
            )
        try:
            proc = subprocess.run(
                [self.runtime, "exec", self.container_id, *argv],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return CommandResult("timeout", None, "",
                                 f"command timed out after {timeout}s")
        except OSError as ex:
            return CommandResult("container_error", None, "", f"runtime error: {ex}")
        stderr = proc.stderr or ""
        if proc.returncode in (125, 126, 127) and _RUNTIME_ERROR.search(stderr):
            return CommandResult("container_error", proc.returncode,
                                 proc.stdout or "", stderr)
        stdout = proc.stdout or ""
        malformed = "\ufffd" in (stdout + stderr)
        return CommandResult(
            "ok" if proc.returncode == 0 else "exit",
            proc.returncode,
            stdout,
            stderr,
            "malformed output bytes replaced" if malformed else "",
        )

    def stop(self) -> None:
        if not self.container_id:
            return
        subprocess.run(
            [self.runtime, "stop", "-t", "0", self.container_id],
            capture_output=True, timeout=120,
        )
        self.container_id = None


class IsolatedExecutor:
    """Container boundary: sandbox rw only, no pack/checkout, probe network none.

    The container image is taken from DELTAFUSE_QUAL_IMAGE (must contain a
    CPython interpreter and pytest; no judge material). The runtime is
    auto-detected among docker/podman. Without a working runtime the executor
    is unavailable and the campaign must stay PENDING.
    """

    kind = "isolated"

    def __init__(self, image: str | None = None):
        self.image = image or __import__("os").environ.get("DELTAFUSE_QUAL_IMAGE")
        self.runtime = self._detect_runtime()

    def _detect_runtime(self) -> str | None:
        for runtime in ("docker", "podman"):
            if shutil.which(runtime):
                return runtime
        return None

    def available(self) -> bool:
        if not self.runtime or not self.image:
            return False
        proc = subprocess.run(
            [self.runtime, "image", "inspect", self.image],
            capture_output=True,
        )
        return proc.returncode == 0

    @property
    def release_ready(self) -> bool:
        """QF-019: only an immutable digest reference is accepted for a
        release campaign; a mutable tag is not a campaign identity."""
        image = self.image or ""
        return (
            image.startswith("sha256:")
            and len(image) == 71
            and all(c in "0123456789abcdef" for c in image[7:])
        )

    def inspect_image_id(self) -> str | None:
        """Measured image identity (config digest) from the runtime."""
        if not self.runtime or not self.image:
            return None
        proc = subprocess.run(
            [self.runtime, "image", "inspect", "--format", "{{.Id}}", self.image],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return None
        out = (proc.stdout or "").strip()
        return out.splitlines()[-1] if out else None

    def command_session(self, sandbox: Path) -> ContainerCommandExecutor:
        """QF-019: persistent command container for one run's shell argv."""
        session = ContainerCommandExecutor(self.runtime, self.image)
        session.start(sandbox)
        return session

    def attest(self, probe_report: dict | None = None,
               image_manifest: dict | None = None) -> dict:
        attestation = {
            "kind": _attest("isolated", "declared",
                            basis="runner invocation flag --executor isolated"),
            "runtime": _attest(self.runtime, "measured",
                               method="PATH lookup of docker/podman"),
            "image": _attest(self.image, "declared",
                             basis="DELTAFUSE_QUAL_IMAGE (wheel deltafuse + pytest, no judge material)"),
            "mounts": _attest(
                {"sandbox": "read-write", "judge_pack": "absent", "framework_checkout": "absent"},
                "declared",
                basis="QF-013: only the run sandbox is mounted, read/write",
            ),
            "network_policy": _attest(
                "none", "declared",
                basis="command container and probe run with --network none; the LM "
                      "Studio endpoint is called by the judge host, never by the container",
            ),
        }
        # QF-019: the image identity is measured, and a build manifest is
        # cross-checked — an image whose digest differs from its manifest
        # never attests.
        measured_id = self.inspect_image_id()
        if measured_id:
            attestation["image_digest"] = _attest(
                measured_id, "measured", method="runtime image inspect --format {{.Id}}"
            )
        if image_manifest is not None:
            manifest_id = image_manifest.get("image_id")
            if measured_id and manifest_id != measured_id:
                raise ExecutorError(
                    f"image digest mismatch: runtime reports {measured_id!r} but the "
                    f"build manifest recorded {manifest_id!r}"
                )
            attestation["wheel_sha256"] = _attest(
                image_manifest.get("wheel_sha256"), "derived",
                basis=("qual image build manifest (commit "
                       f"{str(image_manifest.get('commit'))[:12]})"),
            )
        if probe_report is not None:
            attestation["boundary_probe"] = _attest(
                probe_report, "measured", method="embedded probe inside the boundary container"
            )
        return attestation

    def boundary_probe(self, sandbox: Path, sentinel: Path, search_roots: list[str],
                       write_roots: list[str], forbidden_peer: str | None) -> dict:
        """Run the adversarial probe INSIDE the actual boundary container."""
        targets = {
            "sentinel": str(sentinel),
            "search_names": ["cases", "hidden_suite", "oracle"],
            "search_roots": search_roots,
            "write_roots": write_roots,
            "forbidden_peer": forbidden_peer,
        }
        proc = subprocess.run(
            [
                self.runtime, "run", "--rm", "--network", "none",
                "-v", f"{sandbox}:/sandbox",
                self.image,
                "python", "-c", PROBE_SCRIPT,
            ],
            input=json.dumps(targets),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise ExecutorUnavailable(
                f"boundary probe container failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout).strip()[:300]}"
            )
        return json.loads(proc.stdout.strip().splitlines()[-1])


def assert_boundary_clean(report: dict) -> None:
    """Any leak in the adversarial probe blocks the campaign (fail-closed)."""
    leaks = []
    if report.get("sentinel_read") == "LEAK":
        leaks.append("sentinel_read")
    if report.get("pack_found"):
        leaks.append(f"pack_found={report['pack_found'][:3]}")
    if report.get("write_leak"):
        leaks.append(f"write_leak={report['write_leak'][:3]}")
    if report.get("network") == "LEAK":
        leaks.append("network")
    if leaks:
        raise BoundaryViolation(f"release boundary leaks: {'; '.join(leaks)}")


def resolve_executor(mode: str):
    """Resolve --executor into a ready executor or raise (QF-013 item 5)."""
    if mode == "local-dev":
        return LocalDevExecutor()
    if mode == "isolated":
        executor = IsolatedExecutor()
        if not executor.available():
            raise ExecutorUnavailable(
                "no isolated executor on this host: need docker or podman plus "
                "DELTAFUSE_QUAL_IMAGE (wheel deltafuse + pytest, no judge material)"
            )
        if not executor.release_ready:
            # QF-019: a mutable tag is not a release identity. The digest
            # reference is printed by the canonical build script.
            raise ExecutorUnavailable(
                "DELTAFUSE_QUAL_IMAGE must be an immutable digest reference "
                "(sha256:...) for a release campaign; build the canonical image "
                "with `python scripts/build_qual_image.py` and export the digest "
                "reference it prints"
            )
        return executor
    raise ExecutorError(f"unknown executor mode: {mode!r}")


def apply_executor_verdict_cap(manifest: dict, executor_kind: str) -> None:
    """A non-isolated campaign can never produce a release ``pass`` verdict."""
    if executor_kind != "isolated" and manifest.get("verdict") == "pass":
        manifest["verdict"] = "non-release"
