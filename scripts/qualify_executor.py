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
import shutil
import subprocess
from pathlib import Path

EXECUTOR_KINDS = ("isolated", "local-dev")

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

    def attest(self, probe_report: dict | None = None) -> dict:
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
                "probe:none", "declared",
                basis="adversarial probe runs with --network none; Worker-run networking "
                      "is limited to the configured LM Studio endpoint by the boundary image",
            ),
        }
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
        return executor
    raise ExecutorError(f"unknown executor mode: {mode!r}")


def apply_executor_verdict_cap(manifest: dict, executor_kind: str) -> None:
    """A non-isolated campaign can never produce a release ``pass`` verdict."""
    if executor_kind != "isolated" and manifest.get("verdict") == "pass":
        manifest["verdict"] = "non-release"
