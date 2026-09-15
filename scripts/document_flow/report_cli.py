"""Read-only CLI for report generation and inspection (J03-409)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.document_flow.campaign import CampaignPlan, compare_campaigns, evaluate_campaign
from scripts.document_flow.registry import load_registry
from scripts.document_flow.replay import reevaluate_run_from_store
from scripts.document_flow.reports import (
    render_campaign_markdown,
    render_comparison_markdown,
    render_run_markdown,
)
from scripts.document_flow.store import EvidenceStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeltaFuse J03 report inspector CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run report command
    run_parser = subparsers.add_parser("run", help="Re-evaluate and render run report")
    run_parser.add_argument("--store", required=True, help="Path to run evidence store root")
    run_parser.add_argument("--run-id", default="run", help="Run ID")
    run_parser.add_argument("--root-id", default="root", help="Root ID")
    run_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    run_parser.add_argument("--out", help="Optional output path")

    args = parser.parse_args(argv)

    if args.command == "run":
        store_path = Path(args.store)
        store = EvidenceStore(store_path, args.run_id, args.root_id)
        replay = reevaluate_run_from_store(store)
        
        if args.format == "markdown":
            output_text = render_run_markdown(replay.summary)
        else:
            output_text = json.dumps(replay.run_report, indent=2)

        if args.out:
            Path(args.out).write_text(output_text, encoding="utf-8")
        else:
            print(output_text)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
