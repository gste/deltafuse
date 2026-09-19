#!/usr/bin/env python3
"""Bounded backlog consistency checker for the Artifact Writer queue (AW-45).

Validates a queue.json document structurally:
- unique card and acceptance-check IDs,
- every ``depends_on`` reference exists and the dependency graph is acyclic,
- valid status tokens and queue / card (/ result) status agreement,
- dependency-ready entry selection (planned and in_progress count as
  unfinished; a completed dependency is a prerequisite by status only),
- the observed ``AW-20'' pattern: an unfinished card with an unfinished
  dependency must not carry all-passed acceptance labels,
- environment-blocker reporting for the first dependency-ready card.

This checker verifies statuses, references and navigation only. It NEVER
certifies raw evidence truth from status strings: a PASS label or a completed
dependency still requires inspected, source-bound evidence before execution
(EXECUTOR gate 6).

Usage::

    python check_backlog.py [queue.json] [--no-file-checks] [--json] [--entry-only]

Exit codes: 0 = structural checks pass; 1 = violations found (or usage error).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

CARD_STATUSES = {"planned", "in_progress", "completed"}
CHECK_STATUSES = {"open", "passed", "not_run", "failed", "blocked"}
DEFAULT_QUEUE = Path("backlog/schema-driven-artifact-writer/queue.json")

STATUS_RE = re.compile(r"^\s*(?:-\s*)?Status:\s*([A-Za-z0-9_]+)")


def _card_status_token(line: str) -> str | None:
    m = STATUS_RE.match(line)
    return m.group(1) if m else None


def _read_status_line(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        token = _card_status_token(line)
        if token is not None:
            return token
    return None


def _unfinished(card: dict) -> bool:
    return card.get("status") not in ("completed",)


def _check_ids(cards: list[dict], violations: list[str]) -> None:
    seen: set[str] = set()
    for card in cards:
        cid = card.get("id")
        if not cid:
            violations.append("card without id")
            continue
        if cid in seen:
            violations.append(f"duplicate card id: {cid}")
        seen.add(cid)
        check_ids = [a.get("id") for a in card.get("acceptance_checks", [])]
        if len(check_ids) != len(set(check_ids)):
            violations.append(f"duplicate acceptance-check id in {cid}")
        for aid in check_ids:
            if not aid or not aid.startswith(cid.split("-")[0] + "-"):
                # acceptance ids must share the card prefix (e.g. AW40-R1 on AW-40)
                if aid and not re.match(rf"^[A-Z]{{2}}\d{{2}}-(R|F)\d+$", aid):
                    violations.append(f"{cid}: malformed acceptance-check id: {aid!r}")


def _check_dependencies(cards: list[dict], violations: list[str]) -> None:
    by_id = {c.get("id"): c for c in cards}
    for card in cards:
        cid = card.get("id")
        for dep in card.get("depends_on", []):
            if dep not in by_id:
                violations.append(f"{cid}: unknown dependency {dep!r}")
    # acyclicity (DFS on unfinished graph is enough for a bounded check)
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in done:
            return
        if node in visiting:
            cycle = " -> ".join(stack + [node])
            violations.append(f"dependency cycle: {cycle}")
            return
        visiting.add(node)
        for dep in by_id[node].get("depends_on", []):
            if dep in by_id:
                visit(dep, stack + [node])
        visiting.discard(node)
        done.add(node)

    for card in cards:
        if card.get("id"):
            visit(card["id"], [])


def _check_statuses(cards: list[dict], violations: list[str]) -> None:
    for card in cards:
        cid = card.get("id")
        status = card.get("status")
        if status not in CARD_STATUSES:
            violations.append(f"{cid}: invalid card status {status!r}")
        for check in card.get("acceptance_checks", []):
            cstatus = check.get("status")
            if cstatus not in CHECK_STATUSES:
                violations.append(f"{cid} {check.get('id')}: invalid check status {cstatus!r}")
        if _unfinished(card) and card.get("acceptance_checks") and card.get("depends_on"):
            deps = card.get("depends_on", [])
            all_passed = all(
                a.get("status") == "passed" for a in card.get("acceptance_checks", [])
            )
            unfinished_deps = [d for d in deps if not any(
                c["id"] == d and c.get("status") == "completed" for c in cards
            )]
            if all_passed and unfinished_deps:
                violations.append(
                    f"{cid}: all acceptance checks passed while unfinished "
                    f"dependencies exist ({', '.join(unfinished_deps)})"
                )


def _check_top_level(doc: dict, cards: list[dict], violations: list[str]) -> None:
    top_status = doc.get("status")
    if top_status not in CARD_STATUSES:
        violations.append(f"invalid top-level status {top_status!r}")
    unfinished = [c.get("id") for c in cards if _unfinished(c)]
    if unfinished and top_status == "completed":
        violations.append(
            "false no-work-remaining claim: top-level status completed while "
            f"unfinished cards exist ({', '.join(unfinished)})"
        )
    if unfinished and not doc.get("execution_order"):
        violations.append("execution_order missing/empty while unfinished cards exist")


def _select_entry(doc: dict, cards: list[dict]) -> tuple[str | None, dict | None]:
    """First unfinished card in execution_order whose dependencies are all
    completed (by status). Returns (card_id, card)."""
    by_id = {c.get("id"): c for c in cards}
    for cid in doc.get("execution_order", []):
        card = by_id.get(cid)
        if card is None:
            continue
        if not _unfinished(card):
            continue
        deps_ok = all(
            by_id.get(d) is not None and by_id[d].get("status") == "completed"
            for d in card.get("depends_on", [])
        )
        if deps_ok:
            return cid, card
    return None, None


def _check_entry(doc: dict, cards: list[dict], violations: list[str],
                 report: dict) -> None:
    entry_id, entry_card = _select_entry(doc, cards)
    unfinished = [c.get("id") for c in cards if _unfinished(c)]
    if unfinished and entry_id is None:
        violations.append(
            "no dependency-ready card found although unfinished cards exist "
            f"({', '.join(unfinished)})"
        )
        report["entry"] = None
        return
    report["entry"] = entry_id
    declared = doc.get("entry")
    if entry_id is not None and declared != entry_id:
        violations.append(
            f"stale handoff: declared entry {declared!r}, computed {entry_id!r}"
        )
    if entry_card is not None:
        blocker = entry_card.get("environment_blocker")
        if isinstance(blocker, dict) and blocker.get("requirement"):
            report["environment_blocked"] = blocker["requirement"]
            print(
                f"note: first dependency-ready card {entry_id} is ready by "
                f"dependency but blocked by environment: "
                f"{blocker['requirement']}"
            )
            print(
                "note: independent ready work may proceed; dependent work may not."
            )


def _check_files(doc: dict, cards: list[dict], violations: list[str],
                 queue_path: Path) -> None:
    base = queue_path.resolve().parent
    for card in cards:
        cid = card.get("id")
        status = card.get("status")
        card_path = card.get("card_path")
        if card_path:
            p = base / card_path
            if not p.is_file():
                violations.append(f"{cid}: card file missing: {card_path}")
            else:
                token = _read_status_line(p)
                if token is None:
                    violations.append(f"{cid}: card file has no Status line: {card_path}")
                elif token != status:
                    violations.append(
                        f"{cid}: card/queue status mismatch: {token!r} vs {status!r}"
                    )
        result_path = card.get("result_path")
        if result_path:
            p = base / result_path
            if not p.is_file():
                violations.append(f"{cid}: result file missing: {result_path}")
            else:
                token = _read_status_line(p)
                if token is not None and token != status:
                    violations.append(
                        f"{cid}: result/queue status mismatch: {token!r} vs {status!r}"
                    )


def check(doc: dict, queue_path: Path = DEFAULT_QUEUE,
          file_checks: bool = True) -> tuple[list[str], dict]:
    violations: list[str] = []
    report: dict = {
        "entry": None,
        "environment_blocked": None,
        "cards": 0,
        "unfinished": [],
    }
    if not isinstance(doc, dict):
        return ["queue document is not an object"], report
    cards = doc.get("cards")
    if not isinstance(cards, list):
        return ["queue document has no cards list"], report
    report["cards"] = len(cards)
    report["unfinished"] = [c.get("id") for c in cards if _unfinished(c)]

    _check_ids(cards, violations)
    _check_dependencies(cards, violations)
    _check_statuses(cards, violations)
    _check_top_level(doc, cards, violations)
    _check_entry(doc, cards, violations, report)
    if file_checks:
        _check_files(doc, cards, violations, queue_path)
    return violations, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("queue", nargs="?", default=str(DEFAULT_QUEUE))
    parser.add_argument("--no-file-checks", action="store_true",
                        help="skip card/result file existence and status checks")
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    parser.add_argument("--entry-only", action="store_true",
                        help="print only the computed dependency-ready entry")
    args = parser.parse_args(argv)

    queue_path = Path(args.queue)
    try:
        doc = json.loads(queue_path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {queue_path}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {queue_path}: {exc}", file=sys.stderr)
        return 1

    violations, report = check(doc, queue_path=queue_path,
                               file_checks=not args.no_file_checks)

    print("note: status-string checks only; PASS labels and completed "
          "dependencies still require inspected source-bound evidence before "
          "execution (EXECUTOR gate 6).")
    if args.entry_only:
        print(report["entry"] or "(none)")
        return 0 if not violations else 1
    print(f"cards: {report['cards']}; unfinished: {len(report['unfinished'])}")
    print(f"declared entry: {doc.get('entry')!r}; computed entry: {report['entry']!r}")
    if report["environment_blocked"]:
        print(f"environment blocker: {report['environment_blocked']}")
    if violations:
        print(f"violations ({len(violations)}):")
        for v in violations:
            print(f"  - {v}")
    else:
        print("no violations")
    if args.json:
        print(json.dumps({"violations": violations, "report": report}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())