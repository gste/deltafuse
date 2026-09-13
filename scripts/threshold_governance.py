"""QF-022: threshold governance — numeric release gates change only via a
pre-recorded maintainer Decision.

Two checks back the qualification tooling:

- `undocumented_numeric_gates(source, documented)` — scans the release
  runner source for allowance-shaped numeric constants (ALLOWANCE /
  TOLERANCE / SLACK) whose value is not present in the documented
  thresholds/decisions text. QF-015 added `TOKENIZER_CONSISTENCY_ALLOWANCE
  = 48` after implementation without a Decision; this scanner keeps that
  class of change out.
- `check_revision(revision, decisions_path)` — the frozen thresholds file
  (its `git hash-object` revision, as recorded into campaign manifests) is
  release-approved only when an ACCEPTED Decision section in
  backlog/product/v3/decisions.md lists it under "Approved thresholds
  revisions". `qualify.assert_threshold_governance` blocks the campaign
  otherwise.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECISIONS_DOC = REPO / "backlog" / "product" / "v3" / "decisions.md"

_ALLOWANCE_CONSTANT = re.compile(
    r"\b([A-Z0-9_]*(?:ALLOWANCE|TOLERANCE|SLACK)[A-Z0-9_]*)\s*=\s*(-?\d+)\b"
)
_STATUS_ACCEPTED = re.compile(r"\*\*Статус:\*\*\s*accepted", re.IGNORECASE)
_APPROVED_LINE = re.compile(r"\*\*Approved thresholds revisions:\*\*\s*(.*)")
_REVISION_TOKEN = re.compile(r"\b[0-9a-f]{6,40}\b")


def undocumented_numeric_gates(source: str, documented: str) -> list[str]:
    """Allowance-shaped numeric constants not covered by the documentation."""
    undocumented = []
    for match in _ALLOWANCE_CONSTANT.finditer(source):
        name, value = match.group(1), match.group(2)
        if value not in documented:
            undocumented.append(f"{name}={value}")
    return undocumented


def _sections(text: str):
    parts = text.split("\n## ")
    if parts and text.lstrip().startswith("#"):
        parts = parts[1:] or [text]
    return parts


def approved_revisions(decisions_path: Path | str = DECISIONS_DOC) -> set[str]:
    """Revision prefixes listed by ACCEPTED Decision sections only."""
    text = Path(decisions_path).read_text(encoding="utf-8")
    approved: set[str] = set()
    for section in _sections(text):
        if not _STATUS_ACCEPTED.search(section):
            continue  # draft/superseded decisions approve nothing
        for line in section.splitlines():
            match = _APPROVED_LINE.search(line)
            if match:
                approved.update(_REVISION_TOKEN.findall(match.group(1)))
    return approved


def check_revision(revision: str, decisions_path: Path | str = DECISIONS_DOC) -> bool:
    """True when the thresholds revision is covered by an accepted Decision.

    A Decision may record the full hash while campaign manifests carry its
    12-character prefix (and vice versa); prefix matching requires at least
    6 hex characters on the shorter side.
    """
    rev = (revision or "").strip().lower()
    if len(rev) < 6:
        return False
    for token in approved_revisions(decisions_path):
        token = token.lower()
        if token == rev or (len(rev) >= 6 and token.startswith(rev)) or \
                (len(token) >= 6 and rev.startswith(token)):
            return True
    return False
