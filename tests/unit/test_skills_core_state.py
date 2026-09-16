"""V3-FIX-010: Worker skills must never instruct hand-editing lifecycle state."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "process" / "skills"

# Imperative hand-write patterns: an instruction to set a status directly.
HAND_WRITE_PATTERNS = [
    re.compile(r"(?i)set (this |the )?(task|change|slice)[^.\n]*status"),
    re.compile(r"(?i)set (task|change|slice)s?[^.\n]*\bto[^.\n]*`?(declared|implemented|verified|specified|specification-proposed)`?"),
    re.compile(r"(?i)status:\s*(declared|implemented|verified|specified)`?"),
]


def test_skills_do_not_instruct_hand_status_writes() -> None:
    offenders: list[str] = []
    for skill in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        for pattern in HAND_WRITE_PATTERNS:
            for match in pattern.finditer(text):
                # `deltafuse state ... --status X` is the Core-owned path.
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                line = text[line_start: line_end if line_end != -1 else len(text)]
                if "deltafuse state" in line:
                    continue
                offenders.append(f"{skill.name}: {line.strip()}")
    assert not offenders, "skills instruct hand-editing status:\n" + "\n".join(offenders)


def test_single_step_skills_advance_after_check_gate() -> None:
    """V3-FIX-011: every single-step skill stamps the transition with advance."""
    gates = {
        "intake": "intake",
        "analyze": "analyzed",
        "specify": "specified",
        "decompose": "decomposed",
        "declare": "declaring",
        "implement": "implemented",
    }
    for skill, gate in gates.items():
        text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        assert f"--gate {gate}`. Halt if it exits non-zero." in text, skill
        advance_pos = text.find("deltafuse advance")
        checkgate_pos = text.find(f"check-gate <change-dir> --gate {gate}")
        assert checkgate_pos != -1, skill
        assert advance_pos > checkgate_pos, f"{skill}: advance must follow check-gate"


# Step 3 of the completion plan: exact Core-command contract per skill.
SKILL_CORE_CONTRACT = {
    # skill: (gate stamped by exactly one advance, task/slice/state commands)
    "intake": ("intake", 0),
    "analyze": ("analyzed", 0),
    "specify": ("specified", 2),  # slice state + Change in-flight state
    "decompose": ("decomposed", 0),
    "declare": ("declaring", 1),  # task -> declared
    "implement": ("implemented", 1),  # task -> implemented
    "verify": ("converged", 1),  # task -> verified
}


def test_skill_core_command_contract(repo_root: Path):
    """Exactly one advance per skill, ordered after its check-gate; artifact
    state changes go only through `deltafuse state`."""
    for skill, (gate, state_calls) in SKILL_CORE_CONTRACT.items():
        text = (repo_root / "process" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        advances = [m.start() for m in re.finditer(r"deltafuse advance <change-dir> --gate (\S+)", text)]
        gates = [text[m.start():].split("--gate ", 1)[1].split("`")[0].split(" ")[0] for m in
                 re.finditer(r"deltafuse advance <change-dir> --gate", text)]
        assert len(advances) == 1, f"{skill}: expected exactly one advance, got {gates}"
        assert gates[0].rstrip("`.,") == gate, f"{skill}: wrong gate {gates[0]}"
        states = re.findall(r"deltafuse state <change-dir>", text)
        assert len(states) == state_calls, f"{skill}: expected {state_calls} state calls, got {len(states)}"
        checkgate = text.find(f"check-gate <change-dir> --gate {gate}")
        assert checkgate != -1 and checkgate < advances[0], f"{skill}: advance must follow check-gate"
        # run-mode duplication: a through-mode skill may not repeat single-step gates
        assert text.count("deltafuse advance") == 1, skill


def test_run_skill_defers_advance_to_single_gate_cycle(repo_root: Path):
    """Through-mode stays generic: one advance per gate cycle, never per gate name."""
    text = (repo_root / "process" / "skills" / "run" / "SKILL.md").read_text(encoding="utf-8")
    assert text.count("deltafuse advance") == 1
    assert "--gate <gate>" in text
