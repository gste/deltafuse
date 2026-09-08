"""A10-02: isolate frozen single-slice Analyze extras. Does not edit A09 harness on disk."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
A09_HARNESS = ROOT / "backlog" / "analysis" / "experiments" / "A09-01" / "harness"
EXPERIMENT = Path(__file__).resolve().parent

os.environ.setdefault("DELTAFUSE_LLM_URL", "http://127.0.0.1:1240/v1/chat/completions")
os.environ["A09_EXPERIMENT_DIR"] = str(EXPERIMENT)
os.environ["A09_WORK_SUFFIX"] = "-ablate-slices"

OLD_SLICE = (
    "This call writes ONLY one file: docs/changes/<id>/slices/SLICE-01.md "
    "(YAML frontmatter matching slice.schema.yaml, then markdown body). "
    "Keep the body short. Frontmatter claims must list the CR-NNN ids from request.md. "
    "Use status continue. Do not set blocked-on-decision: unknowns are not blocking Decisions "
    "for a single unambiguous feature. "
    "Do not write coverage.yaml, analysis.md, or extra slices."
)
NEW_SLICE = (
    "This call may write one or two slice files: docs/changes/<id>/slices/SLICE-01.md and "
    "optional SLICE-02.md (each YAML frontmatter matching slice.schema.yaml, then markdown body). "
    "If the request spans two capabilities, use two slices and split CR-* accordingly. "
    "Keep bodies short. Use status continue. Do not set blocked-on-decision. "
    "Do not write coverage.yaml or analysis.md."
)
OLD_COV = "Map each CR-NNN id from request.md to slice SLICE-01."
NEW_COV = "Map each CR-NNN id from request.md to SLICE-01 or SLICE-02 matching the slice files on disk."

sys.path.insert(0, str(A09_HARNESS))
import run_case as a09  # noqa: E402

_orig_build = a09.build_messages


def build_messages(phase: str, product: Path, case_id: str, extra_error: str | None):
    messages, _n = _orig_build(phase, product, case_id, extra_error)
    user = messages[1]["content"].replace(OLD_SLICE, NEW_SLICE).replace(OLD_COV, NEW_COV)
    messages[1]["content"] = user
    return messages, len(messages[0]["content"]) + len(user)


a09.build_messages = build_messages

STEPS = [
    ("intake", "routing", 2048),
    ("analyze", "routing", 2048),
    ("analyze", "slices", 4096),
    ("analyze", "coverage", 2048),
    ("specify", "routing", 4096),
]
STOP = {"fail", "timeout", "blocked-on-decision"}


def main() -> int:
    a09.confirm_runtime()
    repeat = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for phase, focus, tokens in STEPS:
        a09.ANALYZE_FOCUS = focus
        a09.MAX_TOKENS = tokens
        print(f"--- S05 ablate-slices r{repeat} {phase} focus={focus} max_tokens={tokens} ---", flush=True)
        row = a09.run_phase("S05", repeat, phase, tag="ablate-slices")
        outcome = str(row.get("outcome") or "")
        print(f"outcome={outcome}", flush=True)
        if outcome in STOP:
            print(f"stop at {phase}: {outcome}", flush=True)
            return 0
    print("S05 ablate-slices completed sequenced phases", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
