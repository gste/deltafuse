"""A claim that adds a name to a family another capability lists is routed to that capability.

Bench case M04, 2026-10-04..21: every failed run made security.ratelimit the primary of the claim
asking for the audit event `ratelimit.penalty_started`, with monitoring.audit as related only - no
slice, so the event never reached the audit catalogue. Over the 126 bench runs on disk the rule
flags those 9 runs and no other (M01-M03: none).
"""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.analyze import claim_texts, new_name_family_errors

AUDIT_SPEC = (
    "# monitoring.audit\n\n## REQ-AU-02 Event catalogue\n\n| event | meaning |\n| --- | --- |\n"
    "| `auth.denied` | refused login |\n| `ratelimit.rejected` | the limiter refused a request |\n"
)
RATELIMIT_SPEC = "# security.ratelimit\n\nWHEN consume is refused THE SYSTEM SHALL record `ratelimit.rejected` (see monitoring.audit).\n"
SPECS = {
    "security.ratelimit": {"docs/spec/security/ratelimit.md": RATELIMIT_SPEC},
    "monitoring.audit": {"docs/spec/monitoring/audit.md": AUDIT_SPEC},
}
REQUEST = """# Request

- **CR-001** (expectation): `TokenBucketLimiter` MUST accept `penalty_seconds` in `security.ratelimit`.
- **CR-002** (expectation): Security operations MUST see when a key enters the penalty, the same
  way they see rejected requests: event `ratelimit.penalty_started` with the key.
"""


def _claims(primary_of_cr002: str, related: list[str]) -> dict:
    return {
        "CR-001": {"summary": "penalty parameter", "primary_capability": "security.ratelimit"},
        "CR-002": {"summary": "audit the penalty start", "primary_capability": primary_of_cr002,
                   "related_capabilities": related},
    }


def test_the_audit_event_routed_to_the_limiter_only_is_refused_with_the_fix():
    claims = _claims("security.ratelimit", ["monitoring.audit"])
    errors = new_name_family_errors(claims, claim_texts(REQUEST, claims), SPECS)
    assert len(errors) == 1
    assert "CR-002 adds the name `ratelimit.penalty_started`" in errors[0]
    assert "monitoring.audit's specification (docs/spec/monitoring/audit.md: `ratelimit.rejected`)" in errors[0]
    assert "Route CR-002 to monitoring.audit as primary" in errors[0]


def test_the_claim_routed_to_the_capability_that_lists_the_family_passes():
    claims = _claims("monitoring.audit", ["security.ratelimit"])
    assert new_name_family_errors(claims, claim_texts(REQUEST, claims), SPECS) == []


def test_an_existing_name_a_capability_id_or_a_file_is_not_a_new_member():
    request = (
        "- **CR-001** (expectation): keep recording `ratelimit.rejected` from `security.ratelimit`;\n"
        "  see `ratelimit.md` and `limiter.py`.\n"
    )
    claims = {"CR-001": {"primary_capability": "security.ratelimit"}}
    assert new_name_family_errors(claims, claim_texts(request, claims), SPECS) == []


def test_a_new_name_whose_family_no_other_capability_lists_passes():
    request = "- **CR-001** (expectation): add the setting `limiter.penalty_seconds`.\n"
    claims = {"CR-001": {"primary_capability": "security.ratelimit"}}
    assert new_name_family_errors(claims, claim_texts(request, claims), SPECS) == []


def test_the_analyzed_gate_refuses_it(tmp_path: Path, repo_root: Path):
    import yaml

    from deltafuse.core.fsm import check_gate
    from deltafuse.core.installer import install
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-401", title="Audit").step_intake().step_analyze()
    catalog_path = tmp_path / "docs" / "spec" / "_capabilities.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    catalog["domains"]["monitoring"] = {
        "summary": "Operational visibility",
        "capabilities": {"audit": {"summary": "Audit log and its event catalogue", "status": "active",
                                   "type": "supporting", "spec": ["docs/spec/monitoring/audit.md"],
                                   "code_roots": ["src/audit"], "test_roots": ["tests"]}},
    }
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    (tmp_path / "docs" / "spec" / "monitoring").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "monitoring" / "audit.md").write_text(AUDIT_SPEC, encoding="utf-8")
    request = builder.change_dir / "request.md"
    request.write_text(
        request.read_text(encoding="utf-8")
        + "\n- **CR-001** (expectation): operations see the event `ratelimit.penalty_started`.\n",
        encoding="utf-8",
    )
    errors = check_gate(builder.change_dir, "analyzed")
    assert any("adds the name `ratelimit.penalty_started`" in e for e in errors), errors
