"""q4 decision D, phase 1: the code a Change touched against the capabilities routing named."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from deltafuse.core.ownership import _root_prefix, owners, under_routing

CHANGE = "docs/changes/CHG-710-own"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=o@test", "-c", "user.name=o", "-c", "commit.gpgsign=false", *args],
        cwd=root, check=True, capture_output=True, text=True,
    )


def _product(tmp_path: Path, roots: dict[str, list[str]], routed: dict[str, list[str]]) -> Path:
    """A catalog with `roots`, a Change routed to `routed` (primary -> related), committed."""
    caps = {name.split(".")[1]: {"summary": name, "spec": [], "code_roots": r} for name, r in roots.items()}
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(
        yaml.safe_dump({"schema_version": 3, "domains": {"app": {"summary": "App", "capabilities": caps}}}),
        encoding="utf-8",
    )
    change = tmp_path / CHANGE
    change.mkdir(parents=True)
    (change / "change.yaml").write_text("id: CHG-710-own\n", encoding="utf-8")
    claims = {
        f"CR-00{i + 1}": {"primary_capability": primary, "related_capabilities": related}
        for i, (primary, related) in enumerate(routed.items())
    }
    (change / "routing.yaml").write_text(yaml.safe_dump({"change": "CHG-710-own", "claims": claims}), encoding="utf-8")
    for prefixes in roots.values():
        for prefix in prefixes:
            (tmp_path / prefix).mkdir(parents=True, exist_ok=True)
            (tmp_path / prefix / "__init__.py").write_text("", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "intake")
    return tmp_path


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n", encoding="utf-8")


def test_root_prefixes_normalise():
    assert _root_prefix("src/ratelimit") == "src/ratelimit/"
    assert _root_prefix("src/ratelimit/**") == "src/ratelimit/"
    assert _root_prefix("document-service") == "document-service/"
    assert owners("src/a/x.py", {"app.a": ["src/a/"], "app.ab": ["src/"]}) == {"app.a", "app.ab"}


def test_code_in_an_unrouted_capability_is_named(tmp_path: Path):
    root = _product(tmp_path, {"app.limits": ["src/limits"], "app.audit": ["src/audit"]}, {"app.limits": []})
    _touch(root, "src/limits/core.py")
    _touch(root, "src/audit/log.py")
    record = under_routing(root, root / CHANGE)
    assert record["measurable"] is True
    assert record["unrouted"] == {"app.audit": ["src/audit/log.py"]}
    assert record["resolution"] == 0.0


def test_a_related_capability_covers_its_code(tmp_path: Path):
    root = _product(
        tmp_path, {"app.limits": ["src/limits"], "app.audit": ["src/audit"]}, {"app.limits": ["app.audit"]}
    )
    _touch(root, "src/audit/log.py")
    assert under_routing(root, root / CHANGE)["unrouted"] == {}


def test_shared_roots_report_their_blindness(tmp_path: Path):
    """Bench case M02: three capabilities, one root. The check cannot tell them apart."""
    root = _product(
        tmp_path,
        {"app.limits": ["src/ratelimit"], "app.policy": ["src/ratelimit"], "app.stats": ["src/ratelimit"]},
        {"app.limits": []},
    )
    _touch(root, "src/ratelimit/stats.py")
    record = under_routing(root, root / CHANGE)
    assert record["unrouted"] == {} and record["resolution"] == 1.0


def test_unowned_code_is_recorded_not_judged(tmp_path: Path):
    root = _product(tmp_path, {"app.limits": ["src/limits"]}, {"app.limits": []})
    _touch(root, "shared/contracts.py")
    _touch(root, "tests/test_limits.py")
    record = under_routing(root, root / CHANGE)
    assert record["unowned"] == ["shared/contracts.py"] and record["unrouted"] == {}


def test_without_code_roots_or_git_nothing_is_measured(tmp_path: Path):
    root = _product(tmp_path, {"app.limits": ["src/limits"]}, {"app.limits": []})
    assert under_routing(root, root / CHANGE)["reason"] == "no code paths touched"
    bare = tmp_path / "bare"
    (bare / "docs" / "spec").mkdir(parents=True)
    (bare / "docs" / "spec" / "_capabilities.yaml").write_text("schema_version: 3\ndomains: {}\n", encoding="utf-8")
    record = under_routing(bare, bare / "docs" / "changes" / "CHG-1")
    assert record["measurable"] is False and record["reason"] == "catalog declares no code_roots"
