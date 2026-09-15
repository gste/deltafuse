"""Markdown and JSON report rendering and inspection CLI (J03-409)."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from scripts.document_flow.campaign import CampaignComparison, CampaignSummary
from scripts.document_flow.canonical import canonical_bytes
from scripts.document_flow.evaluate import RunSummary


def _escape(text: Any) -> str:
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def render_run_markdown(summary: RunSummary, title: str = "Benchmark Run Report") -> str:
    """Render a human-readable, safe Markdown table for a run evaluation summary."""
    lines = [f"# {_escape(title)}", ""]
    lines.append(f"- **Status**: `{_escape(summary.status)}`")
    lines.append(f"- **Release Verdict**: `{_escape(summary.release_verdict)}`")
    lines.append(f"- **Raw Score**: `{summary.raw_score if summary.raw_score is not None else 'N/A'}`")
    lines.append(f"- **Final Score**: `{summary.final_score if summary.final_score is not None else 'N/A'}`")
    if summary.first_failure:
        lines.append(f"- **First Failure**: `{_escape(summary.first_failure)}`")
    lines.append("")

    if summary.applied_ceilings:
        lines.append("## Applied Ceilings")
        for c in summary.applied_ceilings:
            lines.append(f"- `{_escape(c.kind)}`: limit `{c.limit}`")
        lines.append("")

    if summary.hard_failures:
        lines.append("## Hard Failures")
        for f in summary.hard_failures:
            lines.append(f"- `{_escape(f)}`")
        lines.append("")

    if summary.stages:
        lines.append("## Lifecycle Stages")
        lines.append("| Stage | Correctness (600) | Discipline (250) | Efficiency (150) | Total (1000) |")
        lines.append("|---|---|---|---|---|")
        for stage, sc in summary.stages.items():
            lines.append(
                f"| `{_escape(stage)}` | {sc.correctness} | {sc.discipline} | {sc.efficiency} | **{sc.total}** |"
            )
        lines.append("")

    if summary.system_groups:
        lines.append("## System Groups")
        lines.append("| Group | Points Awarded | Max Points |")
        lines.append("|---|---|---|")
        max_points = {"functional": 1800, "resilience": 600, "compatibility": 400, "efficiency": 200}
        for grp, pts in summary.system_groups.items():
            lines.append(f"| `{_escape(grp)}` | {pts} | {max_points.get(grp, 'N/A')} |")
        lines.append("")

    return "\n".join(lines)


def render_campaign_markdown(summary: CampaignSummary, title: str = "Benchmark Campaign Report") -> str:
    """Render human-readable safe Markdown for a campaign summary."""
    lines = [f"# {_escape(title)}", ""]
    lines.append(f"- **Campaign ID**: `{_escape(summary.campaign_id)}`")
    lines.append(f"- **Status**: `{_escape(summary.status)}`")
    lines.append(f"- **Campaign Score**: `{summary.campaign_score if summary.campaign_score is not None else 'N/A'}`")
    lines.append(f"- **Pass Rate**: `{summary.pass_rate}`")
    if summary.first_failure:
        lines.append(f"- **First Failure**: `{_escape(summary.first_failure)}`")
    lines.append("")

    lines.append("## Diagnostics")
    lines.append(f"- **Scores**: {list(summary.scores)}")
    lines.append(f"- **Median**: {summary.median if summary.median is not None else 'N/A'}")
    lines.append(f"- **Minimum**: {summary.minimum if summary.minimum is not None else 'N/A'}")
    lines.append(f"- **Mean**: {summary.mean if summary.mean is not None else 'N/A'}")
    lines.append(f"- **Population Variance**: {summary.population_variance if summary.population_variance is not None else 'N/A'}")
    lines.append("")

    if summary.stage_deltas:
        lines.append("## Stage Deltas & Means")
        lines.append("| Stage | Score Delta | Stage Mean |")
        lines.append("|---|---|---|")
        for stage in sorted(summary.stage_deltas):
            lines.append(f"| `{_escape(stage)}` | {summary.stage_deltas[stage]} | {summary.stage_means[stage]} |")
        lines.append("")

    return "\n".join(lines)


def render_comparison_markdown(comp: CampaignComparison, title: str = "Campaign Comparison") -> str:
    """Render comparison between two campaigns."""
    lines = [f"# {_escape(title)}", ""]
    lines.append(f"- **Status**: `{_escape(comp.status)}`")
    if comp.reason:
        lines.append(f"- **Reason**: `{_escape(comp.reason)}`")
    if comp.score_delta is not None:
        lines.append(f"- **Score Delta (Right - Left)**: `{comp.score_delta}`")
    lines.append("")

    if comp.stage_deltas:
        lines.append("## Stage Mean Deltas")
        lines.append("| Stage | Delta |")
        lines.append("|---|---|")
        for stage, delta in comp.stage_deltas.items():
            lines.append(f"| `{_escape(stage)}` | {delta} |")
        lines.append("")

    return "\n".join(lines)
