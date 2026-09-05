"""Unit tests for DeltaFuse framework hasher and sensitivity invariant."""

from pathlib import Path
from deltafuse.core.hasher import compute_framework_content_hash


def test_hasher_deterministic(tmp_path: Path):
    process_dir = tmp_path / "process"
    process_dir.mkdir(parents=True)
    (process_dir / "a.txt").write_text("content a", encoding="utf-8")
    (process_dir / "b.txt").write_text("content b", encoding="utf-8")

    h1 = compute_framework_content_hash(tmp_path)
    h2 = compute_framework_content_hash(tmp_path)
    assert h1 == h2
    assert len(h1) == 64


def test_hasher_sensitivity_on_single_char_change(tmp_path: Path):
    process_dir = tmp_path / "process"
    process_dir.mkdir(parents=True)
    f = process_dir / "a.txt"
    f.write_text("canonical content", encoding="utf-8")

    h1 = compute_framework_content_hash(tmp_path)

    # Mutate 1 character
    f.write_text("canonical content.", encoding="utf-8")
    h2 = compute_framework_content_hash(tmp_path)

    assert h1 != h2, "Framework hash must be sensitive to any single character change"
