"""DeltaFuse Framework Core Package."""

from importlib.metadata import version
from pathlib import Path


_source_version = Path(__file__).resolve().parents[2] / "VERSION"
if _source_version.is_file():
    __version__ = _source_version.read_text(encoding="utf-8").strip()
else:
    __version__ = version("deltafuse")
