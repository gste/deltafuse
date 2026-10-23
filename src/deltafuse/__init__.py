"""DeltaFuse Framework Core Package."""

from pathlib import Path


_source_version = Path(__file__).resolve().parents[2] / "VERSION"
if _source_version.is_file():
    __version__ = _source_version.read_text(encoding="utf-8").strip()
else:
    # Only an installed wheel has no VERSION beside it; importing the metadata machinery
    # costs ~0.2 s, which every `deltafuse` call from a checkout used to pay.
    from importlib.metadata import version

    __version__ = version("deltafuse")
