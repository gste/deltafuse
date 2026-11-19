"""The Core's stamp on an evidence record holds after the record is read back from YAML.

Audit 2026-11-17 (FE-14): the stamp was computed over the payload in memory, and YAML does not
give every string back as written - U+0085, U+2028 and U+2029 are line breaks to it. A test
whose output held one of them (a summary is the tail of the runner's log) wrote a record its own
gate then refused: "evidence stamp does not match the recorded payload".
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deltafuse.core.evidence import evidence_stamp_error, stamp_evidence, write_stamped_evidence

ODD = {
    "nel": "\x85", "line-separator": "\u2028", "paragraph-separator": "\u2029", "cr": "\r", "crlf": "\r\n",
    "bom": "\ufeff", "replacement": "\ufffd", "c1": "\x9f", "del": "\x7f", "escape": "\x1b[31m", "tab": "\t",
}
SHAPES = ("FAILED tests/test_x.py::test_a - AssertionError: expected 'a{c}b'", "line one{c}\nline two\n  indented{c}",
          "{c}", " {c} ", "trailing space \n{c}\n\n")


def _payload(**fields) -> dict:
    base = {"schema_version": 3, "change": "CHG-001", "task": "TASK-001", "phase": "red",
            "timestamp": "2026-11-16T10:00:00Z", "command": "pytest", "exit_code": 1,
            "result": "expected-failure", "failure_category": "behavioral-mismatch", "summary": "plain"}
    base.update(fields)
    return base


@pytest.mark.parametrize("char", sorted(ODD))
@pytest.mark.parametrize("shape", SHAPES)
def test_a_summary_with_an_odd_character_keeps_its_stamp(tmp_path: Path, char: str, shape: str):
    dest = tmp_path / "evidence" / "red" / "TASK-001.yaml"
    written = write_stamped_evidence(dest, _payload(summary=shape.format(c=ODD[char])), tmp_path)
    back = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert evidence_stamp_error(back, tmp_path) is None
    assert back == written  # what the caller holds is what the file says


@pytest.mark.parametrize("char", ["nel", "line-separator", "paragraph-separator", "cr"])
def test_the_same_characters_in_other_fields_and_through_a_plain_dump(tmp_path: Path, char: str):
    """The twins: a test id and a command hold runner text too, and a record may be dumped by
    another writer after `stamp_evidence`."""
    c = ODD[char]
    payload = _payload(command=f"pytest -k 'a{c}b'", changed_paths=[f"tests/te{c}st.py"],
                       tests={"source": "junitxml", "failed": [f"tests.test_x::test_a[{c}]"], "passed": [],
                              "not_run": [], "skipped": []})
    stamped = stamp_evidence(payload, tmp_path)
    text = yaml.safe_dump(stamped, sort_keys=False, allow_unicode=True)
    assert evidence_stamp_error(yaml.safe_load(text), tmp_path) is None
    text = yaml.safe_dump(stamped, sort_keys=True, allow_unicode=False, width=40)
    assert evidence_stamp_error(yaml.safe_load(text), tmp_path) is None


def test_a_changed_record_still_loses_its_stamp(tmp_path: Path):
    dest = tmp_path / "evidence" / "red" / "TASK-001.yaml"
    write_stamped_evidence(dest, _payload(summary="a\x85b"), tmp_path)
    back = yaml.safe_load(dest.read_text(encoding="utf-8"))
    back["exit_code"] = 0
    assert evidence_stamp_error(back, tmp_path) == "evidence stamp does not match the recorded payload"
