import json
from pathlib import Path
import pytest
from deltafuse.cli import main


def test_cli_eval_golden_scenario(capsys):
    rc = main(["eval", "--scenario", "golden", "--output", "text"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Schema Compliance Rate  : 100.0%" in captured.out
    assert "Gate Pass Rate          : 100.0%" in captured.out


def test_cli_eval_json_output(tmp_path: Path, capsys):
    out_file = tmp_path / "eval_report.json"
    rc = main(["eval", "--scenario", "golden", "--output", "json", "--out-file", str(out_file)])
    assert rc == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["metrics"]["schema_compliance_rate"] == 100.0
    assert data["metrics"]["gate_pass_rate"] == 100.0


def test_cli_eval_markdown_output(tmp_path: Path, capsys):
    out_file = tmp_path / "eval_report.md"
    rc = main(["eval", "--scenario", "golden", "--output", "markdown", "--out-file", str(out_file)])
    assert rc == 0
    assert out_file.is_file()
    text = out_file.read_text(encoding="utf-8")
    assert "# DeltaFuse LLM Evaluation Report" in text


def test_cli_eval_min_threshold_failure(capsys):
    rc = main(["eval", "--scenario", "schema_violation", "--min-schema-compliance", "90.0"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "is below required 90.0%" in captured.err
