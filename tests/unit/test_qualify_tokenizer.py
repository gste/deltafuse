"""QF-015: token measurement is fail-closed — release verdict `pass` requires
a measured full input usage AND measured framework-controlled input from a
compatible tokenizer. `chars // 4` never supports a release pass."""

from __future__ import annotations

import sys
import urllib.error

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import qualify  # noqa: E402


# ------------------------------------------------- probe: absent = blocking


def _tokenize_probe(monkeypatch, behavior):
    def post(url, payload, timeout):
        if url.endswith("/api/v0/tokenize"):
            return behavior(url)
        if url.endswith("/v1/chat/completions"):
            return {"usage": {"prompt_tokens": 40}}
        raise AssertionError(url)

    monkeypatch.setattr(qualify, "_get_json", lambda url: (
        {"data": [{"id": qualify.REFERENCE_MODEL_ID}]}
        if url.endswith("/v1/models") else {"data": [{
            "id": qualify.REFERENCE_MODEL_ID, "state": "loaded",
            "max_context_length": 32768,
        }]}
    ))
    monkeypatch.setattr(qualify, "_post_json", post)


@pytest.mark.parametrize("kind", ["absent", "http404", "timeout", "conn"])
def test_tokenizer_unavailable_blocks_campaign(monkeypatch, kind):
    """404 / absent / timeout / connection error all block: no fallback."""
    def behavior(url):
        if kind == "absent":
            raise OSError("no endpoint")
        if kind == "http404":
            raise urllib.error.HTTPError(url, 404, "nope", hdrs=None, fp=None)
        if kind == "timeout":
            raise TimeoutError("timed out")
        raise ConnectionError("refused")

    _tokenize_probe(monkeypatch, behavior)
    with pytest.raises(qualify.QualificationError, match="tokenizer"):
        qualify.probe_host("lm-studio")


@pytest.mark.parametrize("answer", [
    {"tokens": -3}, {"tokens": True}, {"tokens": "many"}, {"nope": 1},
])
def test_tokenizer_invalid_counts_block(monkeypatch, answer):
    _tokenize_probe(monkeypatch, lambda url: answer)
    with pytest.raises(qualify.QualificationError, match="tokenizer"):
        qualify.probe_host("lm-studio")


def test_tokenizer_consistency_range_enforced(monkeypatch):
    """Diagnostic completion usage on the calibration text must agree with
    the tokenizer count within the documented template allowance."""
    _tokenize_probe(monkeypatch, lambda url: {"tokens": [1] * 200})
    # completion usage (40) is far below the tokenizer count (200)
    with pytest.raises(qualify.QualificationError, match="consistency"):
        qualify.probe_host("lm-studio")


def test_chars_div_4_underestimates_unicode():
    """Motivating evidence: chars//4 underestimates for Cyrillic/emoji/code;
    that is why the estimate can never support a pass."""
    text = "Проверка токенизации 🚀🚀🚀 def x(): pass\n" * 10
    assert len(text) // 4 > 0  # the estimate exists but is provenance-capped


# --------------------------------------------- T4: estimates never pass


def _passing_metrics(method, tokens=100):
    return {
        "context_peak_tokens": 1000,
        "framework_input_tokens_max": tokens,
        "framework_input_chars_max": 400,
        "framework_input_tokens_method": method,
        "max_unique_files": 1,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
        "t7_breakdown": {},
    }


def _passing_report():
    from deltafuse.core.lifecycle import LIFECYCLE

    return {
        "stages": {name: {"pass": True, "checks_total": 1, "checks_passed": 1,
                          "gate_retries": 0} for name in LIFECYCLE},
        "retries": {"check_gate": 0},
        "defense_checks": {k: {"pass": True} for k in qualify.REQUIRED_T8_CHECKS},
        "pass": True,
        "correctness": 100.0,
    }


@pytest.mark.parametrize("method", ["chars-div-4", "estimated-nonrelease", "unavailable", "mixed", None])
def test_non_measured_tokenizer_method_never_passes(method):
    verdict, failures = qualify.apply_thresholds(
        _passing_report(), _passing_metrics(method)
    )
    assert verdict is False
    assert any("T4" in f and "tokenizer" in f for f in failures)


def test_measured_method_can_pass():
    verdict, failures = qualify.apply_thresholds(
        _passing_report(), _passing_metrics("host-tokenize")
    )
    assert verdict, failures


# --------------------------------------------- fingerprint drift


def test_fingerprint_drift_invalidates(monkeypatch):
    assert qualify.tokenizer_fingerprint_matches("aa", "aa")
    assert not qualify.tokenizer_fingerprint_matches("aa", "bb")
    assert not qualify.tokenizer_fingerprint_matches("aa", None)


def test_drive_worker_marks_estimate_nonrelease(tmp_path, monkeypatch):
    """Without a host tokenizer the per-call method is estimated-nonrelease."""
    from deltafuse import cli as cli_mod
    import json as _json

    monkeypatch.setattr(
        cli_mod, "main",
        lambda argv: print(_json.dumps({"envelope": {"write": ["**"]}})) or 0,
    )
    monkeypatch.setattr(qualify, "worker_turn", lambda *a, **k: {
        "content": '{"tool": "done", "reason": "ok"}', "prompt_tokens": 100})
    monkeypatch.setattr(qualify, "_host_tokenize", lambda base_url, text: None)
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "sys")
    assert metrics["calls"][0]["framework_input_tokens_method"] == "estimated-nonrelease"
    assert metrics["framework_input_tokens_method"] == "estimated-nonrelease"
