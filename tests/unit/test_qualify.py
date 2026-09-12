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


V0_PARAMS = {
    "id": qualify.REFERENCE_MODEL_ID,
    "state": "loaded",
    "max_context_length": 32768,
    "arch": "llama",
    "quantization": "Q4_K_M",
}


def _patch_probe(monkeypatch, v0_entry=None, usage=None, ids=None):
    ids = ids if ids is not None else [qualify.REFERENCE_MODEL_ID]
    monkeypatch.setattr(
        qualify, "_get_json",
        lambda url: (
            {"data": [{"id": i} for i in ids]}
            if url.endswith("/v1/models")
            else {"data": [v0_entry if v0_entry is not None else V0_PARAMS]}
        ),
    )
    monkeypatch.setattr(
        qualify, "_post_json", lambda url, payload, timeout: {"usage": usage or {"prompt_tokens": 7}}
    )


def test_probe_host_requires_exact_model(monkeypatch):
    """Step 5: the exact reference model id must be loaded."""
    _patch_probe(monkeypatch, ids=["some-other-model"])
    with pytest.raises(qualify.QualificationError, match="not loaded"):
        qualify.probe_host("lm-studio")


def test_probe_host_requires_measured_context(monkeypatch):
    """Step 5: context limit is measured, not assumed; a short window blocks."""
    _patch_probe(monkeypatch, v0_entry={**V0_PARAMS, "max_context_length": 8192})
    with pytest.raises(qualify.QualificationError, match="context limit"):
        qualify.probe_host("lm-studio")


def test_probe_host_requires_param_endpoint(monkeypatch):
    """Step 5: without the parameter endpoint the campaign is blocked."""
    def no_v0(url):
        if "/api/v0/" in url:
            raise OSError("not found")
        return {"data": [{"id": qualify.REFERENCE_MODEL_ID}]}

    monkeypatch.setattr(qualify, "_get_json", no_v0)
    with pytest.raises(qualify.QualificationError, match="parameter probe"):
        qualify.probe_host("lm-studio")


def test_probe_host_requires_usage_result(monkeypatch):
    """Step 5: the diagnostic completion must return a valid usage result."""
    _patch_probe(monkeypatch, usage={"prompt_tokens": 0})
    with pytest.raises(qualify.QualificationError, match="tokenization"):
        qualify.probe_host("lm-studio")


def test_probe_host_diagnostic_completion(monkeypatch):
    calls = []

    def fake_get(url):
        calls.append(url.rsplit("/", 2)[-2])
        if url.endswith("/v1/models"):
            return {"data": [{"id": qualify.REFERENCE_MODEL_ID}]}
        return {"data": [V0_PARAMS]}

    def fake_post(url, payload, timeout):
        calls.append("/v1/chat/completions")
        return {"usage": {"prompt_tokens": 7}}

    monkeypatch.setattr(qualify, "_get_json", fake_get)
    monkeypatch.setattr(qualify, "_post_json", fake_post)
    probe = qualify.probe_host("lm-studio")
    assert "/v1/chat/completions" in calls
    assert probe["id"] == qualify.REFERENCE_MODEL_ID
    assert probe["context_window_tokens_measured"] == 32768
    assert probe["context_window_tokens_required"] == 32768
    assert probe["model_params"]["quantization"] == "Q4_K_M"
    assert probe["cloud_fallback"] is False
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
            if "/api/v0/" in self.path:
                body = json.dumps({"data": [V0_PARAMS]}).encode()
            else:
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


def test_score_product_report_satisfies_thresholds_shape(tmp_path, repo_root):
    """Step 1: apply_thresholds consumes a REAL score_product result.

    A finished synthetic run must reach the threshold evaluation without
    AttributeError, and any failing check must surface in T1.
    """
    from deltafuse.bench.init_product import init_bench_product
    from deltafuse.bench.score import score_product

    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    report = score_product(product, pack_root=str(repo_root))

    metrics = {
        "context_peak_tokens": 10000,
        "framework_input_tokens_max": 8000,
        "max_unique_files": 10,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
    }
    verdict, failures = qualify.apply_thresholds(report, metrics)
    # The bare sandbox fails gates; that must show as T1/T2, never crash.
    assert verdict is False
    assert any(f.startswith("T1") or f.startswith("T2") for f in failures)
    assert all("unmeasured" not in f for f in failures)

    # One failing check must surface in T1 with the exact count.
    failing_before = sum(
        int(row.get("checks_total") or 0) - int(row.get("checks_passed") or 0)
        for row in (report.get("stages") or {}).values()
    )
    forged = dict(report)
    stages = dict(report.get("stages") or {})
    first = next(iter(stages))
    stages[first] = {
        **stages[first],
        "checks_passed": int(stages[first].get("checks_passed") or 0),
        "checks_total": int(stages[first].get("checks_total") or 0) + 1,
    }
    forged["stages"] = stages
    verdict2, failures2 = qualify.apply_thresholds(forged, metrics)
    t1 = next(f for f in failures2 if f.startswith("T1"))
    assert f"correctness_failed={failing_before + 1}" in t1


def test_missing_measurement_fails_closed():
    """Step 1/4: a missing metric is a failure, not an implicit pass."""
    report = {"pass": True, "first_fail": None, "stages": {}, "retries": {}, "defense_checks": {}}
    verdict, failures = qualify.apply_thresholds(report, {})
    assert verdict is False
    assert any("T4" in f and "unmeasured" in f for f in failures)
    assert any("T5" in f for f in failures)
    assert any("T6" in f for f in failures)
    assert any("T7" in f for f in failures)


ADVERSARIAL_COMMANDS = [
    "deltafuse next & whoami",
    "deltafuse next && whoami",
    "deltafuse next | cat",
    "deltafuse next; whoami",
    "deltafuse next > ../out.txt",
    "deltafuse next < ../in.txt",
    "deltafuse next 2> err.txt",
    "deltafuse next $(whoami)",
    "deltafuse next `whoami`",
    "powershell -c Get-ChildItem",
    "pwsh -Command ls",
    "cmd /c dir",
    "bash -c 'ls'",
    "sh -c ls",
    "python -c 'import os'",
    "python exploit.py",
    "node -e 1",
    "deltafuse ../../etc/passwd",
    "cat C:\Windows\win.ini",
    "cat /etc/passwd",
    "git push origin main",
    "deltafuse bench score .",
    "deltafuse",
    "",
    "pytest; rm x",
]


def test_adversarial_shell_commands_are_rejected(tmp_path):
    """Step 2: shell operators, interpreters, absolute paths never execute."""
    io = qualify.SandboxIO(tmp_path)
    outside = tmp_path.parent / "outside-probe.txt"
    for command in ADVERSARIAL_COMMANDS:
        result = io.shell(command)
        assert result.startswith("ERROR"), command
        assert io.envelope_violations >= 1
    assert not outside.exists()
    # nothing executed outside the sandbox
    assert not (tmp_path / "err.txt").exists()


def test_allowed_shell_commands_still_run(tmp_path):
    """Step 2: allowed DeltaFuse/pytest/git read-only commands keep working."""
    io = qualify.SandboxIO(tmp_path)
    result = io.shell("pytest --version")
    assert result.startswith("exit=0"), result
    result = io.shell("python -m pytest --version")
    assert result.startswith("exit=0"), result
    result = io.shell("git status")
    assert result.startswith("exit="), result  # not a sandbox repo; may be nonzero
    assert not result.startswith("ERROR")
    result = io.shell("deltafuse version-unknown-sub")
    assert result.startswith("ERROR")  # unknown subcommand rejected


def _passing_report_and_metrics():
    report = {
        "pass": True,
        "first_fail": None,
        "stages": {
            name: {"pass": True, "checks_passed": 3, "checks_total": 3, "gate_retries": 0}
            for name in ["intake", "analyze", "specify", "decompose", "declare", "implement", "verify"]
        },
        "retries": {"check_gate": 0},
        "defense_checks": {},
    }
    metrics = {
        "context_peak_tokens": 20000,
        "framework_input_tokens_max": 12000,
        "max_unique_files": 12,
        "hallucinated_paths": 0,
        "envelope_violations": 0,
    }
    return report, metrics


def test_mutation_on_each_threshold_boundary_flips_verdict():
    """Step 4 acceptance: each T1-T8 boundary mutation must yield fail."""
    report, metrics = _passing_report_and_metrics()
    verdict, failures = qualify.apply_thresholds(report, metrics)
    assert verdict is True, failures

    mutations = []

    # T1: one failed oracle check
    bad = {**report, "stages": {**report["stages"], "intake": {**report["stages"]["intake"], "checks_total": 4}}}
    mutations.append(("T1", dict(bad), metrics))
    # T2: one stage not completed
    bad2 = {**report, "stages": {**report["stages"], "verify": {**report["stages"]["verify"], "pass": False}}}
    mutations.append(("T2", bad2, metrics))
    # T3: total retries over budget / per-stage retry over budget
    mutations.append(("T3", {**report, "retries": {"check_gate": 3}}, metrics))
    bad3 = {**report, "stages": {**report["stages"], "analyze": {**report["stages"]["analyze"], "gate_retries": 2}}}
    mutations.append(("T3-stage", bad3, metrics))
    # T4: context peak / framework input over budget; unmeasured
    mutations.append(("T4", report, {**metrics, "context_peak_tokens": 33000}))
    mutations.append(("T4-fw", report, {**metrics, "framework_input_tokens_max": 16001}))
    mutations.append(("T4-unmeasured", report, {**metrics, "context_peak_tokens": None}))
    # T5: unique files over budget
    mutations.append(("T5", report, {**metrics, "max_unique_files": 25}))
    # T6: hallucinated path
    mutations.append(("T6", report, {**metrics, "hallucinated_paths": 1}))
    # T7: envelope violation
    mutations.append(("T7", report, {**metrics, "envelope_violations": 1}))
    # T8: defense check failing
    bad8 = {**report, "defense_checks": {"synthetic_evidence": {"pass": False}}}
    mutations.append(("T8", bad8, metrics))
    # report pass=false
    mutations.append(("report", {**report, "pass": False, "first_fail": "implement"}, metrics))

    for label, rep, met in mutations:
        verdict, failures = qualify.apply_thresholds(rep, met)
        assert verdict is False, f"{label}: mutation did not fail the run"
        assert failures, label


def test_envelope_gated_write_rejected(tmp_path):
    """Step 4 T7: write_file obeys the Core envelope, not just sandbox roots."""
    io = qualify.SandboxIO(tmp_path)
    io.write_globs = ["docs/spec/**"]  # as fetched from `deltafuse next --json`
    assert "OK" in io.write_file("docs/spec/core.md", "# ok")
    assert "ERROR" in io.write_file("src/evil.py", "# no")
    assert io.envelope_violations == 1
    # empty envelope (Worker must not write) still allows exempt/Core paths only
    io2 = qualify.SandboxIO(tmp_path)
    assert "OK" in io2.write_file("docs/spec/x.md", "# x")
