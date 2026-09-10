from deltafuse.core.lock import (
    DEFAULT_CALL_WIDTH,
    format_lock_yaml,
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
