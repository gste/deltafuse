"""The evidence summary reads the test run's output in the encoding the run wrote it in.

Audit 2026-11-16 (df-evidence #14): on a Russian Windows a child process writes its pipe in the
ANSI code page (cp1251), and the Core decoded it as UTF-8 with `replace` - the summary of every
record with a Cyrillic message was mojibake.
"""

from __future__ import annotations

import locale
import codecs
import sys
from pathlib import Path

import pytest

from deltafuse.core.evidence import run_evidence
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder

MESSAGE = "Ожидалось 3, получено 0"


def test_summary_decodes_the_locale_encoding(tmp_path: Path, repo_root: Path):
    encoding = locale.getpreferredencoding(False)
    if codecs.lookup(encoding).name == "utf-8":
        pytest.skip("the locale encoding is UTF-8 here, so there is nothing else to decode")
    try:
        MESSAGE.encode(encoding)
    except UnicodeEncodeError:
        pytest.skip(f"{encoding} cannot write the message")
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-211", title="Encoding").step_through_decompose()
    (tmp_path / "tests").mkdir(exist_ok=True)
    script = tmp_path / "tests" / "say.py"
    script.write_text(
        "import sys\n"
        f"sys.stdout.buffer.write({MESSAGE!r}.encode({encoding!r}))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    outcome = run_evidence(
        builder.change_dir, phase="red", task="TASK-001", argv=[sys.executable, "tests/say.py"]
    )
    assert MESSAGE in outcome.payload["summary"]


def test_summary_keeps_utf8_output(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-212", title="Encoding").step_through_decompose()
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "say.py").write_text(
        f"import sys\nsys.stdout.buffer.write({MESSAGE!r}.encode('utf-8'))\nsys.exit(1)\n", encoding="utf-8"
    )
    outcome = run_evidence(
        builder.change_dir, phase="red", task="TASK-001", argv=[sys.executable, "tests/say.py"]
    )
    assert MESSAGE in outcome.payload["summary"]
