from deltafuse.core.lock import (
    DEFAULT_CALL_WIDTH,
    LOCK_SCHEMA_VERSION,
    format_lock_yaml,
    lock_schema_version_errors,
    normalize_leash_mode,
    workflow_alignment_errors,
    workflow_from_mapping,
)


def test_workflow_defaults_when_absent():
    width, auto, errors = workflow_from_mapping({})
    assert width == DEFAULT_CALL_WIDTH == "wide"
    assert auto is False
    assert errors == []


def test_workflow_rejects_invalid_call_width():
    width, auto, errors = workflow_from_mapping({"workflow": {"call_width": "ornith"}})
    assert width == "wide"
    assert auto is False
    assert any("call_width" in e for e in errors)


def test_workflow_rejects_invalid_leash():
    width, auto, errors = workflow_from_mapping({"workflow": {"leash": "banana"}})
    assert width == DEFAULT_CALL_WIDTH
    assert auto is False
    assert any("leash" in e for e in errors)


def test_workflow_accepts_yaml11_off_boolean():
    _, _, errors = workflow_from_mapping({"workflow": {"leash": False}})
    assert errors == []
    mode = normalize_leash_mode(False)
    assert mode == "off"


def test_format_lock_yaml_pins_profile():
    text = format_lock_yaml(
        version="2.0.0",
        source="deltafuse://v2.0.0",
        content_hash="abc",
        call_width="narrow",
        auto_accept_decisions=False,
    )
    assert "call_width: narrow" in text
    assert "auto_accept_decisions: false" in text
    assert "content_hash: sha256:abc" in text
    assert f"schema_version: {LOCK_SCHEMA_VERSION}\n" in text


def test_layout_mismatch_call_width():
    errors = workflow_alignment_errors(
        {"workflow": {"call_width": "narrow"}},
        {"workflow": {"call_width": "wide"}},
    )
    assert any("does not match locked call_width" in e for e in errors)


def test_layout_accepts_aligned_narrow():
    assert workflow_alignment_errors(
        {"workflow": {"call_width": "narrow", "auto_accept_decisions": False}},
        {"workflow": {"call_width": "narrow", "auto_accept_decisions": False}},
    ) == []


def test_lock_schema_version_errors_fail_closed():
    assert lock_schema_version_errors({"schema_version": 3}) == []
    assert lock_schema_version_errors({"schema_version": 2})
    assert lock_schema_version_errors({})
    assert lock_schema_version_errors(None)


def test_lock_pin_validates_against_lock_contract_v3():
    import yaml

    from deltafuse.core.schemas import SchemaRegistry

    registry = SchemaRegistry()
    lock = yaml.safe_load(
        format_lock_yaml(
            version="3.0.0",
            source="deltafuse://v3.0.0",
            content_hash="sha256:" + "0" * 64,
        )
    )
    assert registry.validate("lock", lock) == []
    assert registry.validate("lock", {**lock, "schema_version": 2})
    assert registry.validate("lock", {**lock, "framework": {**lock["framework"], "content_hash": "sha256:short"}})
