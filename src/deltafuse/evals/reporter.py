# Formatting and reporting utilities for DeltaFuse LLM Evals.

from __future__ import annotations
import json
from pathlib import Path
from deltafuse.evals.metrics import EvalReport


def export_report(report: EvalReport, format_type: str = "text", output_file: Path | str | None = None) -> str:
    if format_type == "json":
        output = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    elif format_type == "markdown":
        output = report.to_markdown()
    else:
        output = report.to_summary_text()

    if output_file is not None:
        p = Path(output_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output, encoding="utf-8")

    return output
