"""V3-FIX-001/023/024: qualification runner mechanics (no live host needed)."""

from __future__ import annotations

import json
import sys
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
    io.write_envelope = qualify.EnvelopeState("ok", ["docs/spec/**"])
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
    """QF-004: allowed commands keep working under the staging environment
    (controlled interpreter on PATH, work dir is a git repo)."""
    from qualify_staging import StagingRoot

    staging = StagingRoot.create(tmp_path / "staging", build_venv=False)
    qualify.init_sandbox_git(tmp_path)
    io = qualify.SandboxIO(tmp_path)
    io.exec_env = staging.env()
    io.interpreter = staging.interpreter()
    result = io.shell("pytest --version")
    assert result.startswith("exit=0"), result
    result = io.shell("python -m pytest --version")
    assert result.startswith("exit=0"), result
    result = io.shell("git status")
    assert result.startswith("exit=0"), result
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
    io.write_envelope = qualify.EnvelopeState("ok", ["docs/spec/**"])  # from `deltafuse next --json`
    assert "OK" in io.write_file("docs/spec/core.md", "# ok")
    assert "ERROR" in io.write_file("src/evil.py", "# no")
    assert io.envelope_violations == 1


def test_write_envelope_ok_empty_denies_product_writes(tmp_path):
    """QF-001: an ok-but-empty envelope forbids every product write."""
    io = qualify.SandboxIO(tmp_path)
    io.write_envelope = qualify.EnvelopeState("ok", [])
    assert "ERROR" in io.write_file("docs/spec/x.md", "# x")
    assert "ERROR" in io.write_file("src/evil.py", "# evil")
    assert io.envelope_violations == 2
    assert not (tmp_path / "src" / "evil.py").exists()
    # exempt path stays writable
    assert "OK" in io.write_file("README.md", "# readme")


def test_write_envelope_error_denies_and_flags(tmp_path):
    """QF-001: an envelope error denies writes AND is tracked separately."""
    io = qualify.SandboxIO(tmp_path)
    io.write_envelope = qualify.EnvelopeState("error", [], detail="core crashed")
    assert "ERROR" in io.write_file("docs/spec/x.md", "# x")
    assert io.envelope_errors == 1
    assert io.envelope_violations == 0  # unavailability is not a Worker violation
    assert not (tmp_path / "docs" / "spec" / "x.md").exists()


def test_write_envelope_missing_is_fail_closed(tmp_path):
    """QF-001: no envelope fetched yet -> no writes at all."""
    io = qualify.SandboxIO(tmp_path)
    assert io.write_envelope is None
    assert "ERROR" in io.write_file("docs/spec/x.md", "# x")
    assert io.envelope_violations == 1


def test_core_envelope_malformed_json_is_error(monkeypatch, tmp_path):
    """QF-001: garbage Core output is an error state, never `[]`."""
    from deltafuse import cli as cli_mod

    def bad_main(argv):
        print("<<<not json>>>")
        return 0

    monkeypatch.setattr(cli_mod, "main", bad_main)
    state = qualify._core_envelope(tmp_path)
    assert state.status == "error"
    assert state.detail
    assert state.globs == []


def test_core_envelope_nonzero_exit_is_error(monkeypatch, tmp_path):
    """QF-001: a Core failure exit is an error state, never `[]`."""
    from deltafuse import cli as cli_mod

    monkeypatch.setattr(cli_mod, "main", lambda argv: 2)
    state = qualify._core_envelope(tmp_path)
    assert state.status == "error"
    assert "2" in (state.detail or "")


def test_core_envelope_ok_responses(monkeypatch, tmp_path):
    """QF-001: exit=0 + valid JSON keeps ok semantics (globs and ok-empty)."""
    from deltafuse import cli as cli_mod

    monkeypatch.setattr(
        cli_mod, "main",
        lambda argv: print(json.dumps({"envelope": {"write": ["docs/spec/**"]}})) or 0,
    )
    state = qualify._core_envelope(tmp_path)
    assert state.status == "ok" and state.globs == ["docs/spec/**"]

    monkeypatch.setattr(cli_mod, "main", lambda argv: print("{}") or 0)
    state = qualify._core_envelope(tmp_path)
    assert state.status == "ok" and state.globs == []


def test_drive_worker_fails_closed_when_envelope_unavailable(tmp_path, monkeypatch):
    """QF-001: an unavailable envelope aborts the run with a T7 failure,
    it never continues the loop with full write access."""
    from deltafuse import cli as cli_mod

    monkeypatch.setattr(
        qualify, "worker_turn",
        lambda base_url, model, messages: {
            "content": '{"tool": "write_file", "path": "docs/spec/x.md", "content": "# x"}',
            "prompt_tokens": 100,
        },
    )
    monkeypatch.setattr(cli_mod, "main", lambda argv: 2)  # Core unavailable
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert metrics.get("envelope_error")
    verdict, failures = qualify.apply_thresholds(
        {"pass": True, "first_fail": None, "stages": {}, "retries": {}, "defense_checks": {}},
        metrics,
    )
    assert verdict is False
    assert any(f.startswith("T7 envelope_unavailable") for f in failures)
    assert not (tmp_path / "docs" / "spec" / "x.md").exists()


# ------------------------------------------------------- QF-002: T5 per call


def _ok_envelope(monkeypatch):
    """Core always answers with a valid, permissive envelope."""
    from deltafuse import cli as cli_mod

    monkeypatch.setattr(
        cli_mod, "main",
        lambda argv: print(json.dumps({"envelope": {"write": ["**"]}})) or 0,
    )


def _scripted_turns(script):
    """worker_turn stub returning scripted contents in order."""
    state = {"n": 0}

    def fake_turn(base_url, model, messages):
        content = script[min(state["n"], len(script) - 1)]
        state["n"] += 1
        return {"content": content, "prompt_tokens": 100}

    return fake_turn


def test_last_action_read_counts_in_unique_files(tmp_path, monkeypatch):
    """QF-002: a read performed as the call's last action counts in T5."""
    _ok_envelope(monkeypatch)
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "spec" / "core.md").write_text("# core", encoding="utf-8")
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "read_file", "path": "docs/spec/core.md"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert metrics["calls"][0]["unique_files"] == 1, metrics["calls"][0]
    assert metrics["max_unique_files"] == 1


def test_repeated_path_same_call_not_double_counted(tmp_path, monkeypatch):
    """QF-002: repeated paths inside one call form a set, not a counter."""
    io = qualify.SandboxIO(tmp_path)
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    io.write_envelope = qualify.EnvelopeState("ok", ["**"])
    io.begin_call()
    io.read_file("a.md")
    io.read_file("a.md")
    assert len(io.call_paths(io.call_index)) == 1
    io.begin_call()
    io.read_file("a.md")
    io.read_file("b.md")
    assert len(io.call_paths(io.call_index)) == 2


def test_multiple_actions_across_calls_accumulate_per_call(tmp_path, monkeypatch):
    """QF-002: every call is measured by its own path set; the run maximum
    is the maximum of the sets, never their sum."""
    _ok_envelope(monkeypatch)
    for rel in ("a.md", "b.md", "c.md"):
        (tmp_path / rel).write_text(rel, encoding="utf-8")
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "read_file", "path": "a.md"}',
            '{"tool": "read_file", "path": "b.md"}',
            '{"tool": "read_file", "path": "a.md"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert [c["unique_files"] for c in metrics["calls"]] == [1, 1, 1, 0]
    assert metrics["max_unique_files"] == 1  # max of sets, not the sum (3)


def test_tool_event_journal_shape(tmp_path, monkeypatch):
    """QF-002: the typed tool-event journal exists with the agreed shape."""
    from dataclasses import asdict

    _ok_envelope(monkeypatch)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "read_file", "path": "docs/x.md"}',
            '{"tool": "write_file", "path": "docs/y.md", "content": "y"}',
            '{"tool": "shell", "command": "pytest --version"}',
            '{"tool": "read_file", "path": "missing-file.md"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    events = metrics["tool_events"]
    assert len(events) == 4
    for event in events:
        assert set(("call_index", "seq", "tool", "outcome", "paths_read", "paths_written")) <= set(event)
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)  # monotonic, unique
    assert [e["call_index"] for e in events] == [1, 2, 3, 4]
    read_ev, write_ev, shell_ev, err_ev = events
    assert read_ev["tool"] == "read" and read_ev["paths_read"] == ["docs/x.md"]
    assert write_ev["tool"] == "write" and write_ev["paths_written"] == ["docs/y.md"]
    assert shell_ev["tool"] == "shell" and shell_ev["command"] and shell_ev["exit_code"] is not None
    assert err_ev["outcome"].startswith("error")  # rejected/failed action is journaled too
    # journal is serializable into the per-run report
    json.dumps(events)


# ------------------------------------------- QF-003: stage leash / inventory


def _fake_core(monkeypatch, leash_files_seen, leash_order=None, violate=None):
    """cli stub: `next` -> envelope docs/**; `leash` -> recorded, violations
    for any file where violate(file) is true."""
    from deltafuse import cli as cli_mod

    def fake_main(argv):
        if argv[0] == "next":
            print(json.dumps({"envelope": {"write": ["docs/**"]}}))
            return 0
        if argv[0] == "leash":
            files = argv[argv.index("--files") + 1:]
            leash_files_seen.append(files)
            if leash_order is not None:
                leash_order.append(("leash", list(files)))
            violations = [f"uncovered: {f}" for f in files if violate and violate(f)]
            print(json.dumps({"violations": violations}))
            return 0
        return 0

    monkeypatch.setattr(cli_mod, "main", fake_main)


def _stub_advance(monkeypatch, order=None, before_advance=None):
    """Stub only the `deltafuse advance` shell command; everything else runs
    through the real SandboxIO.shell (real git effects, real journal)."""
    real_shell = qualify.SandboxIO.shell

    def fake_shell(self, command, timeout=300):
        if command == "deltafuse advance":
            if before_advance:
                before_advance(self)
            if order is not None:
                order.append(("advance", command))
            return "exit=0\n"
        return real_shell(self, command, timeout=timeout)

    monkeypatch.setattr(qualify.SandboxIO, "shell", fake_shell)


def test_shell_created_file_outside_envelope_fails_t7(tmp_path, monkeypatch):
    """QF-003: a shell-created file outside the envelope is found by the
    inventory diff, enters the stage write-set, and fails T7 via the Core."""
    from qualify_staging import StagingRoot

    staging = StagingRoot.create(tmp_path / "staging", build_venv=False)
    (tmp_path / "leaky_test.py").write_text(
        "from pathlib import Path\n\n"
        "def test_leak():\n"
        "    Path('leak.txt').write_text('leak')\n",
        encoding="utf-8",
    )
    leash_files_seen = []
    _fake_core(monkeypatch, leash_files_seen, violate=lambda f: f == "leak.txt")

    real_shell = qualify.SandboxIO.shell

    def shell_with_staging_env(self, command, timeout=300):
        self.exec_env = staging.env()
        self.interpreter = staging.interpreter()
        return real_shell(self, command, timeout=timeout)

    monkeypatch.setattr(qualify.SandboxIO, "shell", shell_with_staging_env)
    _stub_advance(monkeypatch)
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "shell", "command": "python -m pytest -q leaky_test.py"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert (tmp_path / "leak.txt").exists()  # the shell effect happened
    assert metrics["t7_breakdown"]["leash_violations"] == 1
    assert metrics["envelope_violations"] == 1
    assert "leak.txt" in leash_files_seen[0]
    verdict, failures = qualify.apply_thresholds(
        {"pass": True, "first_fail": None, "stages": {}, "retries": {}, "defense_checks": {}},
        metrics,
    )
    assert verdict is False
    assert any(f.startswith("T7") for f in failures)


def test_reads_never_sent_to_leash(tmp_path, monkeypatch):
    """QF-003: the Core leash receives only the stage write-set, never reads."""
    leash_files_seen = []
    _fake_core(monkeypatch, leash_files_seen)
    _stub_advance(monkeypatch)
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "spec" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "docs" / "spec" / "b.md").write_text("b", encoding="utf-8")
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "write_file", "path": "docs/spec/a.md", "content": "a2"}',
            '{"tool": "read_file", "path": "docs/spec/b.md"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert leash_files_seen == [["docs/spec/a.md"]]  # b.md (read) absent
    assert metrics["envelope_violations"] == 0


def test_past_stage_files_not_rechecked_by_new_envelope(tmp_path, monkeypatch):
    """QF-003: each stage's leash call sees only that stage's writes."""
    leash_files_seen = []
    _fake_core(monkeypatch, leash_files_seen)
    _stub_advance(monkeypatch)
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "write_file", "path": "docs/spec/x.md", "content": "x"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "write_file", "path": "docs/changes/y.md", "content": "y"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert leash_files_seen == [["docs/spec/x.md"], ["docs/changes/y.md"]]
    assert metrics["envelope_violations"] == 0
    assert metrics["t7_breakdown"]["leash_violations"] == 0


def test_leash_runs_per_advance_with_stage_writeset(tmp_path, monkeypatch):
    """QF-003: exactly one leash call per advance, with the closing stage's
    write-set, ordered BEFORE the advance executes."""
    leash_files_seen = []
    order = []
    _fake_core(monkeypatch, leash_files_seen, leash_order=order)
    _stub_advance(monkeypatch, order=order)
    monkeypatch.setattr(
        qualify, "worker_turn",
        _scripted_turns([
            '{"tool": "write_file", "path": "docs/spec/x.md", "content": "x"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "write_file", "path": "docs/changes/y.md", "content": "y"}',
            '{"tool": "shell", "command": "deltafuse advance"}',
            '{"tool": "done", "reason": "ok"}',
        ]),
    )
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    kinds = [k for k, _ in order]
    assert kinds == ["leash", "advance", "leash", "advance"]
    assert order[0][1] == ["docs/spec/x.md"]
    assert order[2][1] == ["docs/changes/y.md"]
    assert metrics["stage_leash"]  # per-stage leash verdicts recorded


def test_inventory_tamper_detected(tmp_path):
    """QF-003: a sandbox HEAD shifted behind the runner's back is tamper."""
    import subprocess

    head = qualify.init_sandbox_git(tmp_path)
    assert len(head) == 40
    (tmp_path / "z.md").write_text("z", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--amend", "-m", "tamper"], cwd=tmp_path, capture_output=True)
    with pytest.raises(qualify.QualificationError, match="inventory_tampered"):
        qualify.inventory(tmp_path, expected_head=head)


def test_unjournaled_change_detected(tmp_path, monkeypatch):
    """QF-003: a file created past the journal is flagged at stage close."""
    leash_files_seen = []
    _fake_core(monkeypatch, leash_files_seen)
    turn_state = {"n": 0}

    def fake_turn(base_url, model, messages):
        turn_state["n"] += 1
        if turn_state["n"] == 2:
            # Worker-side code sneaks a file onto disk, outside the journal.
            (tmp_path / "ghost.md").write_text("g", encoding="utf-8")
            return {"content": '{"tool": "shell", "command": "deltafuse advance"}', "prompt_tokens": 10}
        if turn_state["n"] == 1:
            return {"content": '{"tool": "write_file", "path": "docs/spec/x.md", "content": "x"}', "prompt_tokens": 10}
        return {"content": '{"tool": "done", "reason": "ok"}', "prompt_tokens": 10}

    monkeypatch.setattr(qualify, "worker_turn", fake_turn)
    _stub_advance(monkeypatch)
    metrics = qualify.drive_worker(tmp_path, "http://x", "m", "case", "system")
    assert metrics["t7_breakdown"]["unjournaled_change"] == 1
    assert metrics["envelope_violations"] == 1
    verdict, failures = qualify.apply_thresholds(
        {"pass": True, "first_fail": None, "stages": {}, "retries": {}, "defense_checks": {}},
        metrics,
    )
    assert verdict is False
    assert any(f.startswith("T7") for f in failures)


# --------------------------------------------- QF-004: execution boundary


def test_git_output_option_rejected(tmp_path):
    """QF-004: `git diff --output=...` can no longer write files."""
    io = qualify.SandboxIO(tmp_path)
    assert "ERROR" in io.shell("git diff --output=leak.txt")
    assert "ERROR" in io.shell("git diff --output leak.txt")
    assert not (tmp_path / "leak.txt").exists()


def test_git_any_option_rejected(tmp_path):
    """QF-004: git read-only subcommands take no options at all."""
    for command in ("git log --oneline", "git status --porcelain", "git diff --stat HEAD"):
        io = qualify.SandboxIO(tmp_path)
        assert "ERROR" in io.shell(command), command
    # positional revs: only the exact token HEAD
    io = qualify.SandboxIO(tmp_path)
    assert not io.shell("git diff HEAD").startswith("ERROR")


def test_pytest_plugin_and_config_options_rejected(tmp_path):
    """QF-004: pytest plugin/config/ini/injection options are rejected."""
    for command in (
        "pytest -p evilmod",
        "pytest -c cfg.ini",
        "pytest -o addopts=-p:evil",
        "pytest --rootdir ..",
        "pytest --override-ini=evil=1",
        "pytest @args.txt",
        "pytest --pyargs evilpkg",
        "pytest --import-mode=importlib",
    ):
        io = qualify.SandboxIO(tmp_path)
        assert "ERROR" in io.shell(command), command


def test_pytest_allowed_subset_still_runs(tmp_path):
    """QF-004: the sanctioned pytest subset keeps executing (staging env)."""
    from qualify_staging import StagingRoot

    staging = StagingRoot.create(tmp_path / "staging", build_venv=False)
    io = qualify.SandboxIO(tmp_path)
    io.exec_env = staging.env()
    io.interpreter = staging.interpreter()
    result = io.shell("pytest -q")
    assert result.startswith("exit=") and not result.startswith("ERROR"), result
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "smoke.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    result = io.shell("pytest --tb=line tests/smoke.py")
    assert result.startswith("exit=0"), result


def test_deltafuse_flag_policy():
    """QF-004: deltafuse flags are exactly --json, --gate <name>, --human."""
    argv, reason = qualify.parse_shell_command("deltafuse next --json")
    assert argv is not None and reason is None
    argv, reason = qualify.parse_shell_command("deltafuse advance --gate implement")
    assert argv is not None and reason is None
    argv, reason = qualify.parse_shell_command("deltafuse next --human")
    assert argv is not None and reason is None
    argv, reason = qualify.parse_shell_command("deltafuse next --evil")
    assert argv is None and reason
    argv, reason = qualify.parse_shell_command("deltafuse next -- --json")
    assert argv is None and reason


def test_response_file_and_dashdash_rejected():
    """QF-004: response files and end-of-options separators are rejected."""
    for command in ("pytest @args.txt", "pytest --", "git status --", "git log -- HEAD"):
        argv, reason = qualify.parse_shell_command(command)
        assert argv is None, command
        assert reason, command


def test_unc_and_network_paths_rejected():
    """QF-004: UNC/network/drive paths never reach a command line."""
    for command in (
        "pytest //server/share/x",
        "pytest Z:/x",
    ):
        argv, reason = qualify.parse_shell_command(command)
        assert argv is None, command
        assert reason, command


def test_symlink_and_junction_escape_rejected(tmp_path):
    """QF-004: links inside the sandbox never widen read/write access."""
    io = qualify.SandboxIO(tmp_path)
    io.write_envelope = qualify.EnvelopeState("ok", ["**"])
    outside = tmp_path.parent / "qf004-outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = tmp_path / "lnk"
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(outside), str(link))
    else:
        import os

        os.symlink(outside, link, target_is_directory=True)
    assert "ERROR" in io.write_file("lnk/escape.txt", "x")
    assert not (outside / "escape.txt").exists()
    assert "ERROR" in io.read_file("lnk/secret.txt")


def test_synthetic_campaign_with_failure_is_nonzero_and_saves_all(tmp_path, monkeypatch, capsys):
    """Step 6 acceptance: 3 synthetic runs, one failure -> non-zero exit,
    all three reports plus the campaign verdict saved; manifest.yaml format."""
    import yaml

    monkeypatch.setattr(sys, "argv", ["qualify.py"])
    monkeypatch.setattr(qualify, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(
        qualify, "provenance",
        lambda: {"commit": "a" * 40, "lock_hash": "sha256:" + "0" * 64, "thresholds_revision": "abc123"},
    )
    _patch_probe(monkeypatch)

    calls = {"n": 0}

    def fake_run_case(case_id, index, campaign_id, model_probe, provenance_info):
        calls["n"] += 1
        verdict = "pass" if index != 2 else "fail"
        run_id = f"{campaign_id}-{case_id}-run{index}"
        run_dir = tmp_path / campaign_id / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "report.yaml").write_text(
            yaml.safe_dump({"run_id": run_id, "case": case_id, "verdict": verdict}),
            encoding="utf-8",
        )
        return {
            "run_id": run_id,
            "case": case_id,
            "verdict": verdict,
            "threshold_failures": [] if index != 2 else ["T1 correctness_failed=2"],
            "stages": {}, "correctness": 90.0, "gate_retries": 0,
            "context_peak_tokens": 20000, "framework_input_tokens_max": 10000,
            "max_unique_files": 10, "hallucinated_paths": 0, "envelope_violations": 0,
            "calls": [],
        }

    monkeypatch.setattr(qualify, "run_case", fake_run_case)
    exit_code = qualify.main()
    assert exit_code == 1

    campaign_dir = next(tmp_path.iterdir())  # RUNS_DIR/<campaign-id>
    manifest = yaml.safe_load((campaign_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["verdict"] == "fail"
    assert len(manifest["runs"]) == 9  # default: 3 cases x 3 runs
    assert manifest["framework"]["commit"] == "a" * 40
    assert manifest["thresholds"]["revision"] == "abc123"
    case_dir_runs = list(campaign_dir.glob("*/report.yaml"))
    assert len(case_dir_runs) == 9
    # run with failure preserved
    failed = yaml.safe_load(
        next(p for p in case_dir_runs if p.name == "report.yaml" and "M01-cooldown-run2" in str(p)).read_text(encoding="utf-8")
    )
    assert failed["verdict"] == "fail"


def test_dirty_tree_aborts_campaign(tmp_path, monkeypatch):
    """Step 6: a dirty working tree must abort before any run."""
    monkeypatch.setattr(sys, "argv", ["qualify.py"])
    monkeypatch.setattr(qualify, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(qualify, "tree_dirty", lambda: [" M scripts/x.py"])
    exit_code = qualify.main()
    assert exit_code == 3
