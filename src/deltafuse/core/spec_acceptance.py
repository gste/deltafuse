"""What the Core itself knows about a Change's specification: the tree at Intake, the text accepted.

Audit 2026-11 (FL-1, FL-13). Two gates rested on labels the Worker writes: "the specification
is unchanged" was read from `intent: bugfix` and an absent spec-delta.md, and the human's
acceptance covered the bytes of spec-delta.md only - anchors, not the requirement text behind
them. A feature relabelled `bugfix` added its requirement to `docs/spec/**` and converged with no
Human Gate; an accepted requirement was rewritten in Decompose and converged as accepted.

The Core records two facts of its own, in journals the leash guards:

- the first transition of a Change (the `intake` gate) carries `spec_tree`, a digest of every
  file under `docs/spec/`, and `intent` as Intake left it. "Did the specification change" is the
  diff of that tree against the disk, whatever change.yaml says now;
- the `decide --spec --status accepted` receipt carries `spec_sections`, a digest of the text of
  every section the spec delta and the slices cite. An edit of such a section after the verdict
  makes every later gate refuse (owner decision R3).

Digests are taken over text with CRLF folded to LF, so a checkout under `core.autocrlf` reads as
the same specification.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

SPEC_ROOT = "docs/spec"
MISSING = "missing"

_HEADING = re.compile(r"^(#{1,6})[ \t]+\S")
_FENCE = re.compile(r"^[ \t]*(```|~~~)")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def spec_tree(product_root: Path | str) -> dict[str, str]:
    """{path: digest} of every file under `docs/spec/`, paths relative to the product root."""
    root = Path(product_root)
    base = root / SPEC_ROOT
    out: dict[str, str] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        try:
            out[path.relative_to(root).as_posix()] = _digest(path.read_bytes())
        except OSError:
            out[path.relative_to(root).as_posix()] = MISSING
    return out


def spec_tree_changes(base: dict[str, str], product_root: Path | str) -> list[str]:
    """What differs between a recorded tree and the disk: `<path> (added|modified|removed)`."""
    now = spec_tree(product_root)
    out: list[str] = []
    for rel in sorted(set(base) | set(now)):
        if rel not in base:
            out.append(f"{rel} (added)")
        elif rel not in now:
            out.append(f"{rel} (removed)")
        elif base[rel] != now[rel]:
            out.append(f"{rel} (modified)")
    return out


def _section_lines(lines: list[str], anchor: str) -> list[str] | None:
    """The lines of the section that holds `anchor`: from its heading to the next heading of the
    same or a higher level. An anchor outside any heading (an id in running text, an HTML anchor
    before the first heading) takes the nearest heading above it, or the text up to the first
    heading."""
    token = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(anchor)}(?![A-Za-z0-9_-])")
    headings: list[tuple[int, int]] = []  # (line index, level), fenced code left out
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING.match(line)
        if match:
            headings.append((index, len(match.group(1))))
    hit = next((i for i, _ in headings if token.search(lines[i])), None)
    if hit is None:
        hit = next((i for i, line in enumerate(lines) if token.search(line)), None)
        if hit is None:
            return None
    above = [(i, level) for i, level in headings if i <= hit]
    if not above:
        end = headings[0][0] if headings else len(lines)
        return lines[:end]
    start, level = above[-1]
    end = next((i for i, lvl in headings if i > start and lvl <= level), len(lines))
    return lines[start:end]


def section_digest(product_root: Path | str, spec_ref: str) -> str:
    """Digest of the text a spec reference cites: its section, or the whole file without an anchor.

    `missing` when the file or the anchor is not there.
    """
    file_part, _, anchor = str(spec_ref).partition("#")
    path = Path(product_root) / file_part.strip()
    try:
        data = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return MISSING
    anchor = anchor.strip()
    if not anchor:
        return hashlib.sha256(data).hexdigest()
    lines = _section_lines(data.decode("utf-8", errors="replace").split("\n"), anchor)
    if lines is None:
        return MISSING
    text = "\n".join(line.rstrip() for line in lines).strip("\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def section_digests(product_root: Path | str, spec_refs: Iterable[Any]) -> dict[str, str]:
    refs = sorted({ref.strip().replace("\\", "/") for ref in spec_refs if isinstance(ref, str) and ref.strip()})
    return {ref: section_digest(product_root, ref) for ref in refs}


def cited_spec_refs(change_path: Path | str) -> list[str]:
    """Every reference the human's acceptance covers: what the spec delta adds or modifies, and
    the `spec_refs` of the Change's slices."""
    from deltafuse.core.frontmatter import iter_frontmatter, parse_frontmatter

    change_path = Path(change_path)
    refs: list[Any] = []
    try:
        meta, _ = parse_frontmatter((change_path / "spec-delta.md").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a missing or unreadable delta is the gate's own finding
        meta = {}
    if isinstance(meta, dict):
        for key in ("added", "modified"):
            raw = meta.get(key)
            refs += raw if isinstance(raw, list) else []
    for _, slice_meta in iter_frontmatter(change_path / "slices"):
        raw = slice_meta.get("spec_refs")
        refs += raw if isinstance(raw, list) else []
    return sorted({ref.strip().replace("\\", "/") for ref in refs if isinstance(ref, str) and ref.strip()})


def changed_sections(product_root: Path | str, accepted: dict[str, Any]) -> list[str]:
    """References whose text no longer is what the acceptance recorded."""
    return [
        ref
        for ref, digest in sorted(accepted.items())
        if isinstance(ref, str) and section_digest(product_root, ref) != digest
    ]
