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
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

EXECUTOR_KINDS = ("isolated", "local-dev")

# QF-020: the ONE policy for the persistent command container. The boundary
# probe and every Worker command run in this container; the effective values
# are measured from runtime inspect and verified against this policy — a
# declared tag/invocation is never sufficient attestation.
COMMAND_CONTAINER_POLICY = {
    "network_mode": "none",
    "read_only_rootfs": True,
    "user": "1000:1000",  # non-root
    "cap_drop": "ALL",
    "no_new_privileges": True,
    "memory_bytes": 2 * 1024 * 1024 * 1024,
    "pids_limit": 256,
}
# QF-020: pytest/git temp + home live INSIDE the sandbox (gitignored by the
# judge), so a read-only rootfs still works and scratch use is inventoried.
CONTAINER_SCRATCH = "/sandbox/.qual-scratch"
CONTAINER_HOME = "/sandbox/.qual-home"

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

# QF-020: the adversarial probe runs INSIDE the same persistent command
# container as the Worker commands (before the first and after the last);
# targets are supplied on stdin so no host path is baked into the image.
BOUNDARY_PROBE_SCRIPT = r"""
import hashlib, json, os, socket, sys

targets = json.load(sys.stdin)
results = {}

def try_write(path):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("probe")
        return True
    except OSError:
        return False

# 1. Judge sentinel by host path: must not exist inside the container.
try:
    with open(targets["sentinel_host_path"], "rb") as fh:
        fh.read(1)
    results["sentinel_read"] = "LEAK"
except OSError:
    results["sentinel_read"] = "blocked"

# 2. Search every visible filesystem root for the sentinel by its unique
#    name AND by exact content (a copy hidden inside an allowed mount under
#    another name is a leak, not `blocked`), plus judge pack/checkout names.
names = set(targets.get("search_names") or []) | {targets["sentinel_name"]}
sent_hash = targets.get("sentinel_sha256")
sent_size = targets.get("sentinel_size")
name_hits = []
content_hits = []
for root in targets.get("search_roots", [os.sep]):
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        # inspect the CURRENT level first, then prune the descent: the
        # depth limit bounds the walk, it never hides entries of an
        # already-reached directory
        matched = names.intersection(filenames) | names.intersection(dirnames)
        if matched:
            name_hits.append(dirpath)
        if sent_hash and sent_size:
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(p) != sent_size:
                        continue
                    with open(p, "rb") as fh:
                        if hashlib.sha256(fh.read()).hexdigest() == sent_hash:
                            content_hits.append(p)
                except OSError:
                    continue
        depth = dirpath.rstrip(os.sep).count(os.sep)
        if depth > 6:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in (
                ".git", "node_modules", "__pycache__", "proc", "sys", "dev", "run")]
results["sentinel_found"] = content_hits
results["pack_found"] = name_hits

# 3. Writes outside the sandbox/scratch must fail.
results["write_leak"] = [
    p for p in targets.get("write_roots", [])
    if try_write(os.path.join(p, "deltafuse-boundary-probe"))
]

# 4. The container rootfs and runtime control paths must not be writable.
results["rootfs_write_leak"] = [
    p for p in targets.get("rootfs_write_probes", [])
    if try_write(os.path.join(p, "deltafuse-boundary-probe"))
]

# 5. The runtime control socket must be absent; if present it is exposure.
sock = targets.get("control_socket") or "/var/run/docker.sock"
if os.path.exists(sock):
    results["docker_sock"] = "writable" if try_write(sock) else "present"
else:
    results["docker_sock"] = "absent"

# 6. Network beyond the boundary policy must be refused.
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

# 7. Positive control: the sanctioned scratch inside the sandbox MUST be
#    writable, otherwise the run contract is broken.
scratch = targets.get("scratch")
if scratch:
    try:
        os.makedirs(scratch, exist_ok=True)
        with open(os.path.join(scratch, "deltafuse-boundary-probe"), "w",
                  encoding="utf-8") as fh:
            fh.write("probe")
        results["scratch_write"] = "ok"
    except OSError:
        results["scratch_write"] = "blocked"
else:
    results["scratch_write"] = "not-probed"

# 8. Container identity measured from inside (cgroup token when the runtime
#    exposes it); the judge compares it with the session container id.
token = None
try:
    with open("/proc/self/cgroup", encoding="utf-8") as fh:
        text = fh.read()
    for word in text.replace("/", " ").replace(".", " ").split():
        if len(word) in (32, 64) and all(c in "0123456789abcdef" for c in word):
            token = word
except OSError:
    pass
results["container_token"] = token

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

    def __init__(self) -> None:
        # QF-020: stays empty — L1 staging hosts no meaningful boundary probe.
        self.probe_reports: list[dict] = []

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
        """Start the persistent command container for one run.

        QF-020: read-only rootfs, non-root, all capabilities dropped, no new
        privileges, memory/pids limits, no network; temp/home are redirected
        into the sandbox scratch so a read-only rootfs still works and all
        scratch use stays inside the inventoried sandbox.
        """
        proc = subprocess.run(
            [
                self.runtime, "run", "-d", "--rm",
                "--network", COMMAND_CONTAINER_POLICY["network_mode"],
                "--read-only",
                "--user", COMMAND_CONTAINER_POLICY["user"],
                "--cap-drop", COMMAND_CONTAINER_POLICY["cap_drop"],
                "--security-opt", "no-new-privileges",
                "--memory", str(COMMAND_CONTAINER_POLICY["memory_bytes"]),
                "--pids-limit", str(COMMAND_CONTAINER_POLICY["pids_limit"]),
                "-e", f"TMPDIR={CONTAINER_SCRATCH}",
                "-e", f"HOME={CONTAINER_HOME}",
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

    def inspect(self) -> dict:
        """QF-020: parsed `runtime inspect` of the running container."""
        if not self.container_id:
            raise ExecutorError("command container is not started")
        proc = subprocess.run(
            [self.runtime, "inspect", self.container_id],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise ExecutorUnavailable(
                f"container inspect failed (exit {proc.returncode}): "
                f"{(proc.stderr or '').strip()[:300]}"
            )
        docs = json.loads(proc.stdout)
        if not isinstance(docs, list) or not docs:
            raise ExecutorUnavailable("container inspect returned no document")
        return docs[0]

    def measure_policy(self) -> dict:
        """QF-020: the EFFECTIVE policy from the runtime, not the invocation."""
        doc = self.inspect()
        hostconfig = doc.get("HostConfig") or {}
        config = doc.get("Config") or {}
        return {
            "container_id": doc.get("Id"),
            "image_digest": doc.get("Image"),
            "user": config.get("User") or "",
            "network_mode": hostconfig.get("NetworkMode"),
            "read_only_rootfs": bool(hostconfig.get("ReadonlyRootfs")),
            "cap_drop": list(hostconfig.get("CapDrop") or []),
            "security_opt": list(hostconfig.get("SecurityOpt") or []),
            "memory": int(hostconfig.get("Memory") or 0),
            "pids_limit": int(hostconfig.get("PidsLimit") or 0),
            "mounts": [
                {
                    "destination": m.get("Destination"),
                    "source": m.get("Source"),
                    "rw": bool(m.get("RW", m.get("Mode") != "ro")),
                    "type": m.get("Type"),
                }
                for m in (doc.get("Mounts") or [])
            ],
        }

    def verify_policy(self, measured: dict,
                      expected_image_digest: str | None = None) -> list[str]:
        """QF-020: compare the measured policy with COMMAND_CONTAINER_POLICY;
        returns the list of mismatches (empty = policy holds)."""
        p = COMMAND_CONTAINER_POLICY
        mismatches: list[str] = []
        if measured.get("network_mode") != p["network_mode"]:
            mismatches.append(f"network_mode={measured.get('network_mode')!r} "
                              f"(expected {p['network_mode']!r})")
        if not measured.get("read_only_rootfs"):
            mismatches.append("rootfs writable (expected read-only)")
        if measured.get("user") in ("", "0", "0:0", "root"):
            mismatches.append(f"user={measured.get('user')!r} (expected non-root)")
        if p["cap_drop"] not in (measured.get("cap_drop") or []):
            mismatches.append(f"cap_drop={measured.get('cap_drop')!r} (expected ALL)")
        if not any(
            str(o).split(":")[0] == "no-new-privileges"
            for o in (measured.get("security_opt") or [])
        ):
            mismatches.append("no-new-privileges not enforced")
        if measured.get("memory", 0) < p["memory_bytes"]:
            mismatches.append(f"memory={measured.get('memory')} below limit")
        if measured.get("pids_limit", 0) != p["pids_limit"]:
            mismatches.append(f"pids_limit={measured.get('pids_limit')}")
        sandbox_mounts = [
            m for m in (measured.get("mounts") or [])
            if m.get("destination") == "/sandbox"
        ]
        if len(sandbox_mounts) != 1 or not sandbox_mounts[0].get("rw"):
            mismatches.append(f"mounts: expected exactly one rw /sandbox, "
                              f"got {measured.get('mounts')!r}")
        extra = [m for m in (measured.get("mounts") or [])
                 if m.get("destination") != "/sandbox"]
        if extra:
            mismatches.append(f"extra mounts present: {extra!r}")
        if expected_image_digest and measured.get("image_digest") != expected_image_digest:
            mismatches.append(
                f"image digest drift: container runs {measured.get('image_digest')!r}, "
                f"expected {expected_image_digest!r}"
            )
        return mismatches

    def run_boundary_probe(self, *, sentinel_host_path: str, sentinel_name: str,
                           sentinel_sha256: str, sentinel_size: int,
                           search_names: list[str], forbidden_peer: str | None,
                           scratch: str, phase: str) -> dict:
        """QF-020: run the adversarial probe INSIDE this command container."""
        if not self.container_id:
            raise ExecutorError("command container is not started")
        targets = {
            "sentinel_host_path": sentinel_host_path,
            "sentinel_name": sentinel_name,
            "sentinel_sha256": sentinel_sha256,
            "sentinel_size": sentinel_size,
            "search_names": list(search_names),
            "search_roots": [os.sep],
            "write_roots": ["/tmp", "/root", "/home"],
            "rootfs_write_probes": ["/", "/usr/bin", "/var/tmp"],
            "control_socket": "/var/run/docker.sock",
            "forbidden_peer": forbidden_peer,
            "scratch": scratch,
        }
        proc = subprocess.run(
            [self.runtime, "exec", self.container_id,
             "python", "-c", BOUNDARY_PROBE_SCRIPT],
            input=json.dumps(targets), capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            raise ExecutorUnavailable(
                f"boundary probe failed (exit {proc.returncode}): "
                f"{((proc.stderr or '') + (proc.stdout or '')).strip()[:300]}"
            )
        report = json.loads((proc.stdout or "").strip().splitlines()[-1])
        report["phase"] = phase
        return report

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
        self.image = image or os.environ.get("DELTAFUSE_QUAL_IMAGE")
        self.runtime = self._detect_runtime()
        # QF-020: measured per-run boundary evidence (policy + before/after
        # probes), attached to the manifest attestation as runs complete.
        self.probe_reports: list[dict] = []

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
                probe_report, "measured",
                method="QF-020 in-container probes (before/after) + runtime inspect policy",
            )
        return attestation


def assert_policy_clean(mismatches: list[str]) -> None:
    """QF-020: any measured-policy mismatch blocks the campaign."""
    if mismatches:
        raise BoundaryViolation(
            "command container policy mismatch: " + "; ".join(mismatches[:5])
        )


def assert_boundary_clean(report: dict, container_id: str | None = None) -> None:
    """QF-020: any leak in the adversarial probe blocks the campaign.

    The sentinel is checked three ways: unreadable by host path, absent by
    unique name on every visible root, absent by exact content hash (a copy
    hidden inside the allowed sandbox mount is a leak). Scratches must stay
    writable (positive control); rootfs and runtime control paths must not be
    writable; the measured container identity must match the session id.
    """
    leaks = []
    if report.get("sentinel_read") == "LEAK":
        leaks.append("sentinel_read")
    if report.get("sentinel_found"):
        leaks.append(f"sentinel_found={report['sentinel_found'][:3]}")
    if report.get("pack_found"):
        leaks.append(f"pack_found={report['pack_found'][:3]}")
    if report.get("write_leak"):
        leaks.append(f"write_leak={report['write_leak'][:3]}")
    if report.get("rootfs_write_leak"):
        leaks.append(f"rootfs_write_leak={report['rootfs_write_leak'][:3]}")
    if report.get("docker_sock") in ("present", "writable"):
        leaks.append(f"runtime_control_socket={report['docker_sock']}")
    if report.get("network") == "LEAK":
        leaks.append("network")
    if report.get("scratch_write") == "blocked":
        leaks.append("scratch_write=blocked (run contract broken)")
    token = report.get("container_token")
    if container_id and token:
        # a container id may be a 64-hex prefix of the cgroup token
        if token != container_id and not container_id.startswith(token):
            leaks.append(f"container_identity={token[:12]}!={container_id[:12]}")
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
