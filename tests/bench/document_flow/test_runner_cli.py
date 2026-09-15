"""Tests for benchmark runner CLI and preflight (J03-507)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.document_flow.__main__ import main as cli_main
from scripts.document_flow.preflight import run_preflight_checks
from scripts.document_flow.runner import RunnerError, execute_benchmark_run


def test_preflight_checks_basic():
    res = run_preflight_checks()
    assert res.ok is True
    assert res.diagnostics["python"] == "available"


def test_runner_preflight_only(tmp_path):
    out_dir = tmp_path / "out"
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    outcome = execute_benchmark_run(
        run_id="run-test-preflight",
        output_dir=out_dir,
        sandbox_dir=sandbox,
        preflight_only=True,
    )
    assert outcome.status == "preflight_passed"
    assert outcome.verdict == "none"


def test_runner_rejects_non_empty_output_dir(tmp_path):
    out_dir = tmp_path / "out_busy"
    out_dir.mkdir()
    (out_dir / "existing_file.txt").write_text("busy", encoding="utf-8")
    
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    with pytest.raises(RunnerError, match="output directory is not empty"):
        execute_benchmark_run(
            run_id="run-collision",
            output_dir=out_dir,
            sandbox_dir=sandbox,
        )


def test_runner_cli_e2e(tmp_path, capsys):
    out_dir = tmp_path / "out_e2e"
    sandbox = tmp_path / "sandbox_e2e"
    sandbox.mkdir()

    rc = cli_main(["run", "--run-id", "run-cli-1", "--out", str(out_dir), "--sandbox", str(sandbox), "--preflight-only"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "status=preflight_passed" in captured
