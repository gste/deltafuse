"""A Change that needs a capability the catalog lacks must be analysable.

Before q8 it was not: routing refuses a name the catalog does not hold, and
`docs/spec/**` is writable only in Specify - after the `analyzed` gate. The
only legal move in Analyze was to route into an existing capability, which is
what M02 run 1 did before failing every downstream check
(backlog/roadmap/runs-2026-09-23).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from deltafuse.core.capability import (
    CapabilityError,
    draft_capabilities,
    propose_capability,
)
from deltafuse.core.context import PHASE_CONTRACTS
from deltafuse.core.integrity import load_capability_catalog, validate_catalog_capability_specs
from deltafuse.core.leash import structural_kind

CATALOG = """schema_version: 3
domains:
  security:
    summary: Security controls
    capabilities:
      ratelimit:
        summary: Token-bucket rate limiter
        spec:
          - docs/spec/security/ratelimit.md
        status: active
        type: supporting
"""


@pytest.fixture()
def product(tmp_path: Path) -> Path:
    spec = tmp_path / "docs" / "spec"
    (spec / "security").mkdir(parents=True)
    (spec / "_capabilities.yaml").write_text(CATALOG, encoding="utf-8")
    (spec / "security" / "ratelimit.md").write_text(
        "# security.ratelimit\n\n## REQ-RL-01 Consume\n\nIt limits.\n", encoding="utf-8"
    )
    return tmp_path


def test_the_worker_never_gets_the_catalog_in_its_envelope():
    """The catalog is the human's file. The Core writes the draft, not the Worker."""
    for phase, contract in PHASE_CONTRACTS.items():
        assert "docs/spec/_capabilities.yaml" not in contract["allowed_write"], phase


def test_a_proposed_capability_is_a_draft(product: Path):
    written = propose_capability(
        product,
        "monitoring.usage_stats",
        summary="Counters of accepted and rejected calls",
        spec="docs/spec/monitoring/usage_stats.md",
        code_roots=["src/monitoring"],
    )
    assert written == {
        "capability": "monitoring.usage_stats",
        "status": "draft",
        "spec": "docs/spec/monitoring/usage_stats.md",
        "path": "docs/spec/_capabilities.yaml",
    }
    catalog = yaml.safe_load((product / "docs/spec/_capabilities.yaml").read_text(encoding="utf-8"))
    entry = catalog["domains"]["monitoring"]["capabilities"]["usage_stats"]
    assert entry["status"] == "draft"
    assert entry["code_roots"] == ["src/monitoring"]
    # The existing catalog is untouched.
    assert catalog["domains"]["security"]["capabilities"]["ratelimit"]["status"] == "active"
    assert draft_capabilities(product, ["monitoring.usage_stats", "security.ratelimit"]) == [
        "monitoring.usage_stats"
    ]


def test_routing_accepts_a_draft_whose_spec_specify_has_not_written_yet(product: Path):
    propose_capability(
        product,
        "monitoring.usage_stats",
        summary="Counters",
        spec="docs/spec/monitoring/usage_stats.md",
    )
    catalog, errors = load_capability_catalog(product)
    assert errors == []
    # The spec file does not exist yet - that is the point of a draft.
    assert not (product / "docs/spec/monitoring/usage_stats.md").exists()
    assert validate_catalog_capability_specs(catalog, product, ["monitoring.usage_stats"]) == []
    # An active capability still has to have its spec on disk.
    assert validate_catalog_capability_specs(catalog, product, ["security.ratelimit"]) == []
    assert validate_catalog_capability_specs(catalog, product, ["security.nope"]) != []


def test_a_proposal_is_refused_when_it_is_not_a_proposal(product: Path):
    with pytest.raises(CapabilityError, match="already exists"):
        propose_capability(product, "security.ratelimit", summary="again", spec="docs/spec/x.md")
    with pytest.raises(CapabilityError, match="<domain>.<capability>"):
        propose_capability(product, "ratelimit", summary="s", spec="docs/spec/x.md")
    with pytest.raises(CapabilityError, match="under docs/spec/"):
        propose_capability(product, "a.b", summary="s", spec="src/a/b.py")
    with pytest.raises(CapabilityError, match="one-line summary"):
        propose_capability(product, "a.b", summary="  ", spec="docs/spec/a/b.md")


def test_the_core_write_leaves_the_digest_that_vouches_for_it(product: Path):
    """The guard knows a `capability propose` the way it knows `deltafuse state`."""
    from deltafuse.core.leash import vouched_digests

    propose_capability(
        product, "monitoring.usage_stats", summary="Counters", spec="docs/spec/monitoring/usage_stats.md"
    )
    written = hashlib.sha256(
        (product / "docs/spec/_capabilities.yaml").read_bytes()
    ).hexdigest()
    assert written in vouched_digests(product).get("docs/spec/_capabilities.yaml", set())

    receipts = [
        json.loads(line)
        for line in (product / ".deltafuse" / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert receipts[-1]["kind"] == "capability-draft"
    assert receipts[-1]["capability"] == "monitoring.usage_stats"

    # The catalog is not a Writer artifact: a human edits it, and that is not
    # a Worker violation.
    assert structural_kind("docs/spec/_capabilities.yaml") is None


def test_a_slice_may_cite_the_spec_a_draft_promises(product: Path):
    """M02 runs 1 and 3 stopped here: the model proposed drafts correctly, then the
    `analyzed` gate refused every slice for citing a spec Specify has not written."""
    from deltafuse.core.integrity import draft_spec_files, validate_spec_ref

    propose_capability(
        product,
        "monitoring.usage_stats",
        summary="Counters of accepted and rejected calls",
        spec="docs/spec/monitoring/usage_stats.md",
    )
    drafts = draft_spec_files(product)
    assert drafts == {"docs/spec/monitoring/usage_stats.md"}

    ref = "docs/spec/monitoring/usage_stats.md#REQ-MON-01"
    assert "does not exist" in (validate_spec_ref(ref, product) or "")
    assert validate_spec_ref(ref, product, drafts=drafts) is None
    # The allowance is for the draft's own file, nothing else that is missing.
    other = "docs/spec/monitoring/other.md#REQ-X-01"
    assert "does not exist" in (validate_spec_ref(other, product, drafts=drafts) or "")


def test_the_allowance_ends_when_the_human_accepts_the_capability(product: Path):
    from deltafuse.core.integrity import draft_spec_files, validate_spec_ref

    propose_capability(
        product, "monitoring.usage_stats", summary="Counters", spec="docs/spec/monitoring/usage_stats.md"
    )
    catalog = product / "docs/spec/_capabilities.yaml"
    catalog.write_text(catalog.read_text(encoding="utf-8").replace("status: draft", "status: active"), encoding="utf-8")
    drafts = draft_spec_files(product)
    assert drafts == frozenset()
    assert validate_spec_ref("docs/spec/monitoring/usage_stats.md#REQ-MON-01", product, drafts=drafts)
