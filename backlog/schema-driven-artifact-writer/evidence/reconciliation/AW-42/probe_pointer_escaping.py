#!/usr/bin/env python3
"""AW-42 probe: is RFC 6901 pointer *escaping* actually exercised anywhere?

AW39-R3 requires "Verify JSON Pointer escaping and missing nested paths". The
retained regression named for it (tests/unit/test_artifact_writer_eval.py::
test_aw39_json_pointer_escaping_and_nested_removal) addresses only plain
pointers, so its name claims more than it asserts.

This probe separates the two questions the backlog must not conflate:

1. behaviour - do the shipped pointer resolvers honour ~0 / ~1?
2. coverage  - does any committed test fail if that behaviour is removed?

Run:  python probe_pointer_escaping.py
Exit 0 = behaviour correct; a coverage gap is reported as text, not failure.
Exit 1 = behaviour defect.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from deltafuse.core.artifact_patch import _parse_pointer  # noqa: E402
from evaluate_artifact_writer import _resolve_json_pointer  # noqa: E402

DOC = {"claims": {"CR-001": {"a/b": {"m~n": {"value": "hit"}}}}}
POINTER = "/claims/CR-001/a~1b/m~0n/value"
DOCBAR = {"a/b": {"m~n": 1}}


def check_behaviour() -> list[str]:
    failures: list[str] = []
    tokens = _parse_pointer(POINTER)
    print(f"_parse_pointer({POINTER!r}) -> {tokens}")
    if tokens != ["claims", "CR-001", "a/b", "m~n", "value"]:
        failures.append("artifact_patch._parse_pointer does not unescape ~1/~0")

    found, _parent, current, _key = _resolve_json_pointer(DOC, POINTER)
    print(f"oracle _resolve_json_pointer({POINTER!r}) -> found={found} value={current!r}")
    if not (found and current == "hit"):
        failures.append("evaluate_artifact_writer._resolve_json_pointer does not unescape ~1/~0")

    missing_found, _, _, _ = _resolve_json_pointer(DOCBAR, "/a~1b/absent")
    print(f"oracle missing nested lookup -> found={missing_found} (must be False)")
    if missing_found:
        failures.append("oracle reports a missing nested path as found")
    return failures


def check_coverage() -> list[str]:
    hits: list[str] = []
    pattern = re.compile(r'["\'][^"\']*/[^"\']*~[01][^"\']*["\']')
    for src in sorted((REPO / "tests").rglob("*.py")):
        text = src.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if pattern.search(stripped):
                hits.append(f"{src.relative_to(REPO)}:{number}: {stripped}")
    print(f"committed test assertions using an escaped pointer literal: {len(hits)}")
    for hit in hits:
        print(f"  {hit}")
    return hits


def main() -> int:
    failures = check_behaviour()
    hits = check_coverage()
    if failures:
        print("BEHAVIOUR DEFECT:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    if not hits:
        print("COVERAGE GAP ONLY: behaviour is correct, but no committed regression "
              "asserts ~0/~1 unescaping, so deleting that code would fail no test.")
    else:
        print("behaviour and committed coverage both present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
