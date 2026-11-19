"""The human's acceptance of the specification makes the drafts it routes into active (A-4).

Audit 3: `decide --spec --status accepted` on a Change routed into a draft capability printed
"gate 'specified' failed: capability ... still a draft" together with "spec accepted" and exited
1. No command made the draft active; only a hand edit of docs/spec/_capabilities.yaml did.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.capability import propose_capability
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.installer import install
from deltafuse.core.transitions import set_artifact_status
from tests.fixtures.change_builder import MockChangeBuilder

CATALOG = "docs/spec/_capabilities.yaml"


def _proposed_into_draft(tmp_path: Path, repo_root: Path) -> MockChangeBuilder:
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-311", title="Draft").step_intake().step_analyze()
    builder._core_advance("analyzed")
    propose_capability(tmp_path, "monitoring.usage_stats", summary="Counters", spec="docs/spec/monitoring/usage_stats.md")
    # A second draft this Change does not route into: the verdict is not about it.
    propose_capability(tmp_path, "monitoring.other", summary="Other", spec="docs/spec/monitoring/other.md")
    routing_file = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_file.read_text(encoding="utf-8"))
    for claim in routing["claims"].values():
        claim["primary_capability"] = "monitoring.usage_stats"
    routing_file.write_text(yaml.safe_dump(routing), encoding="utf-8")
    ref = "docs/spec/monitoring/usage_stats.md#REQ-MON-01"
    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["primary_capability"] = "monitoring.usage_stats"
    meta["spec_refs"] = [ref]
    slice_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    spec_dir = tmp_path / "docs" / "spec" / "monitoring"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "usage_stats.md").write_text(
        "# monitoring.usage_stats\n\n## REQ-MON-01 Counters\n\nTHE SYSTEM SHALL count.\n", encoding="utf-8"
    )
    (builder.change_dir / "spec-delta.md").write_text(
        f"---\nchange: {builder.change_id}\nstatus: proposed\nslices: [SLICE-01]\n"
        f"added: [{ref}]\nmodified: []\nremoved: []\n---\n\n# Spec Delta\n",
        encoding="utf-8",
    )
    set_artifact_status(builder.change_dir, status="specification-proposed", change_status=True)
    return builder


def _status(tmp_path: Path, name: str) -> str:
    catalog = yaml.safe_load((tmp_path / CATALOG).read_text(encoding="utf-8"))
    domain, cap = name.split(".")
    return catalog["domains"][domain]["capabilities"][cap]["status"]


def test_accepting_the_spec_activates_the_draft_it_routes_into(tmp_path: Path, repo_root: Path, capsys):
    builder = _proposed_into_draft(tmp_path, repo_root)
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "accepted"]) == 0, capsys.readouterr()
    change = yaml.safe_load((builder.change_dir / "change.yaml").read_text(encoding="utf-8"))
    assert change["status"] == "specified"
    assert _status(tmp_path, "monitoring.usage_stats") == "active"
    assert _status(tmp_path, "monitoring.other") == "draft"

    # Written by the Core with a receipt that vouches for the bytes, so the leash does not
    # read the catalog as a hand edit.
    from deltafuse.core.leash import vouched_digests

    digest = hashlib.sha256((tmp_path / CATALOG).read_bytes()).hexdigest()
    assert digest in vouched_digests(tmp_path).get(CATALOG, set())
    rows = [
        json.loads(line)
        for line in (tmp_path / ".deltafuse" / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    active = [r for r in rows if r.get("kind") == "capability-active"]
    assert active and active[-1]["capabilities"] == ["monitoring.usage_stats"]
    assert active[-1]["change"] == builder.change_id


def test_rejecting_the_spec_leaves_the_draft_a_draft(tmp_path: Path, repo_root: Path, capsys):
    """The twin verdict: saying no answers nothing about the capability."""
    builder = _proposed_into_draft(tmp_path, repo_root)
    assert main(["decide", str(builder.change_dir), "--spec", "--status", "rejected"]) == 0, capsys.readouterr()
    assert _status(tmp_path, "monitoring.usage_stats") == "draft"
    rows = (tmp_path / ".deltafuse" / "transitions.jsonl").read_text(encoding="utf-8")
    assert "capability-active" not in rows


def test_the_committed_activation_passes_the_leash_under_enforce(tmp_path: Path):
    """The nearest bypass: the catalog the Core rewrote lands in a commit, and the leash judges
    that range (hook and CI). A receipt kind it does not know, or bytes no receipt vouches for,
    would make the human's own acceptance read as a hand edit of the catalog."""
    from tests.fixtures.leash_walk import REPO_ROOT, cli, commit, git, leash, put, set_workflow, write

    root = tmp_path / "p"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "core.autocrlf", "false")
    install(target_dir=root, framework_root=REPO_ROOT)
    set_workflow(root, leash="enforce")
    install(target_dir=root, framework_root=REPO_ROOT)
    put(root, "docs/spec/core.md", "# Core\n\n## REQ-01\n\nThe system MUST start.\n")
    put(root, CATALOG, yaml.safe_dump({"schema_version": 3, "domains": {"system": {
        "summary": "Core system", "capabilities": {"core": {
            "summary": "Core capability", "spec": ["docs/spec/core.md"], "code_roots": ["src"]}}}}},
        sort_keys=False))
    commit(root, "init")
    name = "CHG-312-draft"
    change = root / "docs" / "changes" / name
    cli("new", root, name, "--title", "Usage counters")
    request = change / "request.md"
    request.write_text(request.read_text(encoding="utf-8") + "\nCount calls.\n\n## Provenance\n\nTest.\n\n"
                       "## Claims\n\n- CR-001 (expectation): the system counts calls.\n", encoding="utf-8")
    cli("advance", change, "--gate", "intake")
    commit(root, "intake")
    cli("capability", "propose", "monitoring.usage_stats", "--summary", "Counters",
        "--spec", "docs/spec/monitoring/usage_stats.md", "--path", root)
    write(root, "routing", {"identity": "routing", "fields": {"route": "code", "claims": {
        "CR-001": {"summary": "Counters", "primary_capability": "monitoring.usage_stats",
                   "related_capabilities": [], "policies": [], "confidence": "high"}}}}, change=change)
    write(root, "slice", {"identity": "SLICE-01", "fields": {
        "title": "Counters", "primary_capability": "monitoring.usage_stats", "claims": ["CR-001"],
        "spec_refs": ["docs/spec/monitoring/usage_stats.md"]}, "body": "Count calls."}, change=change)
    cli("advance", change, "--gate", "analyzed")
    commit(root, "analyzed")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    put(root, "docs/spec/monitoring/usage_stats.md",
        "# monitoring.usage_stats\n\n## REQ-MON-01 Counters\n\nTHE SYSTEM SHALL count calls.\n")
    write(root, "spec-delta", {"identity": "spec-delta", "fields": {
        "slices": ["SLICE-01"], "added": ["docs/spec/monitoring/usage_stats.md#REQ-MON-01"], "modified": [],
        "removed": []}, "body": "## SLICE-01\n\nAdds REQ-MON-01."}, change=change)
    cli("state", change, "--slice", "SLICE-01", "--status", "specified")
    cli("state", change, "--change", "--status", "specification-proposed")
    commit(root, "specify close")
    code, out = cli("decide", change, "--spec", "--status", "accepted", check=False)
    assert code == 0, out
    assert _status(root, "monitoring.usage_stats") == "active"
    assert commit(root, "specified", verify=True).returncode == 0
    code, data = leash(root, "--base", base, "--head", git(root, "rev-parse", "HEAD").stdout.strip())
    assert code == 0, data
