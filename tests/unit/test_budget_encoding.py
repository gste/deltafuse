"""The context budget counts a file's text whatever encoding the file is in.

Audit 2026-11-17 (FE-11): files were read as UTF-8 with undecodable bytes dropped, so a legacy
source file in windows-1251 lost every Cyrillic letter before it was counted: 160 000 bytes read
as 9 600 tokens, and a task over such files passed any budget.
"""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.context import anchored_sections, count_files_tokens, validate_task_context_budget

LINE = "// Расчёт процентов по вкладу за период\n"


def test_a_cp1251_source_file_counts_like_the_same_text_in_utf8(tmp_path: Path):
    text = LINE * 4000
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Legacy.java").write_bytes(text.encode("cp1251"))
    (tmp_path / "src" / "Utf8.java").write_bytes(text.encode("utf-8"))
    assert (tmp_path / "src" / "Legacy.java").stat().st_size == 160_000
    legacy = count_files_tokens([tmp_path / "src" / "Legacy.java"])[0]
    utf8 = count_files_tokens([tmp_path / "src" / "Utf8.java"])[0]
    assert legacy == utf8 > 64_000
    errors = validate_task_context_budget({"max_tokens": 64000, "max_files": 24}, [], ["src/Legacy.java"], tmp_path)
    assert any("tokens" in e for e in errors), errors


def test_the_cited_section_of_a_cp1251_spec_module_is_counted_too(tmp_path: Path):
    """The twin reader: a spec_ref with an anchor counts the anchored section, read the same way."""
    body = "Система ДОЛЖНА начислять проценты ежедневно.\n" * 2000
    module = "# Вклады\n\n## REQ-001 Начисление\n\n" + body + "\n## REQ-002 Другое\n\nкоротко\n"
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    spec = tmp_path / "docs" / "spec" / "deposit.md"
    spec.write_bytes(module.encode("cp1251"))
    section = anchored_sections(spec, {"REQ-001"})
    assert section is not None and len(section) > len(body) * 0.9
    errors = validate_task_context_budget({"max_tokens": 16000, "max_files": 24}, ["docs/spec/deposit.md#REQ-001"], [], tmp_path)
    assert any("tokens" in e for e in errors), errors
    assert validate_task_context_budget({"max_tokens": 16000, "max_files": 24}, ["docs/spec/deposit.md#REQ-002"], [], tmp_path) == []


def test_utf16_and_utf8_with_a_bom_count_their_text(tmp_path: Path):
    text = LINE * 100
    plain = tmp_path / "a.txt"
    plain.write_bytes(text.encode("utf-8"))
    want = count_files_tokens([plain])[0]
    for name, data in (("b.txt", b"\xef\xbb\xbf" + text.encode("utf-8")), ("c.txt", text.encode("utf-16"))):
        (tmp_path / name).write_bytes(data)
        assert abs(count_files_tokens([tmp_path / name])[0] - want) <= 1, name
