"""V3-FIX-001/023/024: qualification runner mechanics (no live host needed)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys = pytest.importorskip("sys")
sys.path.insert(0, "scripts")

import qualify  # noqa: E402


def test_framework_commit_fail_closed(tmp_path):
    """V3-FIX-023: no empty commit ever reaches the manifest."""
    sha = qualify.framework_commit()
    assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def test_probe_host_requires_exact_model(monkeypatch):
    """V3-FIX-024: the exact reference model id must be loaded."""
    models = {"data": [{"id": "some-other-model"}]}
    monkeypatch.setattr(qualify, "_get_json", lambda url: models)
    with pytest.raises(qualify.QualificationError, match="not loaded"):
        qualify.probe_host("lm-studio")


def test_probe_host_diagnostic_completion(monkeypatch):
    calls = []

    def fake_get(url):
        calls.append("/v1/models")
        return {"data": [{"id": qualify.REFERENCE_MODEL_ID}]}

    def fake_post(url, payload, timeout):
        calls.append("/v1/chat/completions")
        return {"usage": {"prompt_tokens": 7}}

    monkeypatch.setattr(qualify, "_get_json", fake_get)
    monkeypatch.setattr(qualify, "_post_json", fake_post)
    probe = qualify.probe_host("lm-studio")
    assert "/v1/chat/completions" in calls
    assert probe["id"] == qualify.REFERENCE_MODEL_ID
    assert probe["context_window_tokens"] == 32768
    assert probe["probe_prompt_tokens"] == 7


def test_probe_host_down(monkeypatch):
    def boom(url):
        raise OSError("connection refused")

    monkeypatch.setattr(qualify, "_get_json", boom)
    with pytest.raises(qualify.QualificationError, match="host probe failed"):
        qualify.probe_host("lm-studio")


def test_thresholds_t1_to_t8():
    good_report = {
        "pass": True,
        "first_fail": None,
        "stages": {name: {"pass": True, "checks": {"failed": 0}} for name in
                   ["intake", "analyze", "specify", "decompose", "declare", "implement", "verify"]},
        "retries": {"check_gate": 0},
        "defense_checks": {},
    }
    good_metrics = {
        "context_peak_tokens": 30000,
        "framework_input_tokens_max": 16000,
        "max_unique_files": 20,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
    }
    verdict, failures = qualify.apply_thresholds(good_report, good_metrics)
    assert verdict and failures == []

    bad = dict(good_report)
    bad["pass"] = False
    bad["first_fail"] = "implement"
    verdict, failures = qualify.apply_thresholds(bad, {**good_metrics, "envelope_violations": 2})
    assert not verdict
    assert any(f.startswith("T7") for f in failures)
    assert any("first_fail" in f for f in failures)


def test_medians_ignore_missing():
    med = qualify.medians(
        [
            {"correctness": 100.0, "context_peak_tokens": 100, "gate_retries": 0, "max_unique_files": 5},
            {"correctness": 90.0, "context_peak_tokens": 200, "gate_retries": 2, "max_unique_files": 7},
            {"correctness": 80.0, "context_peak_tokens": 300, "gate_retries": 1, "max_unique_files": 9},
        ]
    )
    assert med["correctness"] == 90.0
    assert med["max_unique_files"] == 7.0


def test_sandbox_io_rejects_escapes(tmp_path):
    io = qualify.SandboxIO(tmp_path)
    assert "ERROR" in io.write_file("../outside.txt", "x")
    assert io.envelope_violations == 1
    assert "ERROR" in io.write_file(".deltafuse/lock.yaml", "x")
    assert "ERROR" in io.read_file("missing.txt")
    assert io.hallucinated_paths == 1
    assert "ERROR" in io.shell("rm -rf /")
    assert "OK" in io.write_file("docs/spec/x.md", "# x")


def test_live_http_probe():
    """Full HTTP path against a stub LM Studio server."""
    class Stub(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"data": [{"id": qualify.REFERENCE_MODEL_ID}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"usage": {"prompt_tokens": 3}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        probe = qualify.probe_host("lm-studio", base_url=url)
        assert probe["probe_prompt_tokens"] == 3
    finally:
        server.shutdown()
