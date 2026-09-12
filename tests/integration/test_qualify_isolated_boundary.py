"""QF-013 integration: the adversarial matrix runs INSIDE the actual release
boundary (a container), not through monkeypatching.

These tests require a real isolated boundary: a responding docker/podman
daemon plus DELTAFUSE_QUAL_IMAGE (wheel DeltaFuse + pytest + git, no judge
material). Without one they SKIP — a skip never counts as boundary evidence
(QF-018 requires a saved run of this matrix).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import qualify_executor  # noqa: E402

_image = __import__("os").environ.get("DELTAFUSE_QUAL_IMAGE")
_executor = None
try:
    _candidate = qualify_executor.IsolatedExecutor()
    if _candidate.available():
        _executor = _candidate
except Exception:
    _executor = None

pytestmark = pytest.mark.skipif(
    _executor is None,
    reason="no isolated boundary available (docker/podman daemon + DELTAFUSE_QUAL_IMAGE)",
)


def _probe(tmp_path, executor, forbidden_peer=None):
    runs = tmp_path / "campaign"
    runs.mkdir()
    sentinel = runs / ".judge-sentinel"
    sentinel.write_text(uuid.uuid4().hex, encoding="utf-8")
    report = executor.boundary_probe(
        runs, sentinel,
        search_roots=["/"],
        write_roots=[str(tmp_path / "outside"), str(Path.home())],
        forbidden_peer=forbidden_peer or "127.0.0.1:9",
    )
    return report, sentinel


def test_sentinel_unreadable_inside_boundary(tmp_path):
    report, _ = _probe(tmp_path, _executor)
    assert report["sentinel_read"] == "blocked"


def test_judge_pack_not_findable_inside_boundary(tmp_path):
    report, _ = _probe(tmp_path, _executor)
    assert report["pack_found"] == []


def test_no_writes_outside_sandbox(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "canary.txt").write_text("intact", encoding="utf-8")
    report, _ = _probe(tmp_path, _executor)
    assert report["write_leak"] == []
    assert (outside / "canary.txt").read_text(encoding="utf-8") == "intact"
    assert not (outside / "deltafuse-boundary-probe").exists()


def test_network_beyond_policy_refused(tmp_path):
    report, _ = _probe(tmp_path, _executor)
    assert report["network"] == "blocked"


def test_full_boundary_matrix_clean(tmp_path):
    report, _ = _probe(tmp_path, _executor)
    qualify_executor.assert_boundary_clean(report)  # must not raise
