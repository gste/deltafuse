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


# --- Audit 2026-11-17 (FE-6), owner decision R7 ------------------------------------------------------
#
# The family was the first dotted segment of any name, and a member was any text starting with it.
# On a JVM product every spec names classes by package, so `ru.` was one family shared by all of
# them: a claim naming a new package had to be primary in every capability, and `analyzed` could
# not close. A family is for event and key names of the form `family.member`; package and property
# prefixes are not families.

JVM_SPECS = {
    "system.core": {"docs/spec/core.md": "# Core\n## REQ-01\n`ru.bank.core.rates` holds the rate tables.\n"},
    "system.account": {"docs/spec/account.md": "# account\n`ru.bank.account.service.MainService` SHALL answer.\n"},
    "system.debitcard": {"docs/spec/debitcard.md": "# debitcard\n`ru.bank.debitcard.service.MainService` SHALL answer.\n"},
}


def _one_claim(text: str, primary: str = "system.core") -> list[str]:
    claims = {"CR-001": {"summary": "s", "primary_capability": primary}}
    return claims, claim_texts(f"- **CR-001** (expectation): {text}\n", claims)


def test_a_new_package_is_not_a_member_of_a_family_of_every_spec():
    claims, texts = _one_claim("add the package `ru.bank.core.limits` with a daily limit calculator")
    assert new_name_family_errors(claims, texts, JVM_SPECS) == []


def test_package_and_property_prefixes_are_not_families_in_their_short_forms_either():
    """The bypass: the same prefixes with two segments, where the form alone does not tell."""
    specs = {
        "system.core": {"docs/spec/core.md": "# Core\n"},
        "system.other": {"docs/spec/other.md": (
            "# other\n`ru.bank` is the root package; `com.acme` the vendor's; `org.slf4j` logs;\n"
            "`spring.profiles` and `java.time` are used; `ru.bank.core.rates` and `ratelimit.rejected.total` too.\n"
        )},
    }
    for name in ("ru.limits", "com.partner", "org.junit", "spring.datasource", "java.util", "ratelimit.penalty_started"):
        claims, texts = _one_claim(f"use `{name}` here")
        assert new_name_family_errors(claims, texts, specs) == [], name


def test_a_name_longer_than_family_member_is_a_path_not_a_member():
    claims, texts = _one_claim("emit `ratelimit.penalty.started` and read `auth.tokens.ttl`", primary="security.ratelimit")
    assert new_name_family_errors(claims, texts, SPECS) == []


def test_a_member_is_a_whole_name_of_the_spec_not_the_start_of_a_longer_one():
    specs = {
        "security.ratelimit": {"docs/spec/security/ratelimit.md": "# ratelimit\n"},
        "monitoring.audit": {"docs/spec/monitoring/audit.md": "# audit\nThe class `ratelimit.rejected.Handler` and ratelimit.unquoted exist.\n"},
    }
    claims, texts = _one_claim("event `ratelimit.penalty_started`", primary="security.ratelimit")
    assert new_name_family_errors(claims, texts, specs) == []


def test_the_analyzed_gate_closes_on_a_jvm_product_whose_specs_name_packages(tmp_path: Path, repo_root: Path):
    import yaml

    from deltafuse.core.fsm import check_gate
    from deltafuse.core.installer import install
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-920", title="New package")
    spec = tmp_path / "docs" / "spec"
    catalog = yaml.safe_load((spec / "_capabilities.yaml").read_text(encoding="utf-8"))
    for name in ("account", "debitcard"):
        catalog["domains"]["system"]["capabilities"][name] = {"summary": name, "spec": [f"docs/spec/{name}.md"]}
        (spec / f"{name}.md").write_text(JVM_SPECS[f"system.{name}"][f"docs/spec/{name}.md"], encoding="utf-8")
    (spec / "_capabilities.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    (spec / "core.md").write_text(JVM_SPECS["system.core"]["docs/spec/core.md"], encoding="utf-8")
    builder.step_intake(["CR-001"])
    (builder.change_dir / "request.md").write_text(
        "# Request\n- CR-001: add the package `ru.bank.core.limits` with a daily limit calculator\n", encoding="utf-8")
    builder.step_analyze()
    assert [e for e in check_gate(builder.change_dir, "analyzed") if "family" in e] == []
