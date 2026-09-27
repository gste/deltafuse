"""Pinned wording of the Worker skills: no hand-written lifecycle state, one
advance per gate cycle, and no instruction that reads as the opposite of the
Core's actual contract (V3-FIX-010, V3-FIX-011, audit F16-F18)."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "process" / "skills"
DOCS_DIR = REPO_ROOT / "docs"

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


def _worker_section(skill: str) -> str:
    text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    return text.split("## Worker (LLM)", 1)[1].split("\n## ", 1)[0]


def test_red_rules_say_which_cli_exits_zero() -> None:
    """F16: an authentic Red is two exit codes, and "CLI exit 0" named both.

    `deltafuse evidence` exits 0 because it recorded the run; the test command
    exits non-zero because the behavior is missing (cli.py:944-964, fsm.py
    red_is_authentic). A Worker reading "Require CLI exit 0" as the test
    command's code has to make the oracle pass in Declare to get it.
    """
    declare = (SKILLS_DIR / "declare" / "SKILL.md").read_text(encoding="utf-8")
    assert "Require CLI exit 0" not in declare
    rule = [line for line in declare.splitlines() if "authentic red" in line.lower()]
    assert rule, "declare: no rule names authentic Red"
    assert "`deltafuse evidence` exits 0" in rule[0]
    assert "test command exits non-zero" in rule[0]

    implement = (SKILLS_DIR / "implement" / "SKILL.md").read_text(encoding="utf-8")
    assert "CLI exit 0 is required" not in implement
    rule = [line for line in implement.splitlines()
            if "Green and regression" in line and "changed_paths" in line]
    assert rule, "implement: no rule covers Green and regression"
    assert "test command exits 0" in rule[0]
    assert "`deltafuse evidence`" in rule[0]

    for name, stale in (("workflow.md", "Authentic Red is CLI exit 0"),
                        ("workflow.ru.md", "Authentic Red — exit 0 у CLI")):
        text = (DOCS_DIR / name).read_text(encoding="utf-8")
        assert stale not in text, name
        rule = [line for line in text.splitlines() if "Authentic Red" in line]
        assert rule and "`deltafuse evidence`" in rule[0], name


def test_verify_worker_list_stamps_converged_before_archiving() -> None:
    """F17: archive applies only from status 'converged', which `advance` writes.

    `check-gate` proves content and moves nothing (transitions.advance_change),
    so the Worker list that said "after the gate passes, archive" sent the
    Worker straight into the refusal - the path the audit's CHG-102 took.
    """
    worker = _worker_section("verify")
    assert "deltafuse advance <change-dir> --gate converged" in worker
    assert worker.index("deltafuse advance") < worker.index("deltafuse archive")

    for name, heading in (("workflow.md", "### Archiving"),
                          ("workflow.ru.md", "### Архивация")):
        section = (DOCS_DIR / name).read_text(encoding="utf-8").split(heading, 1)[1]
        section = section.split("\n---\n", 1)[0]
        assert "deltafuse advance <change-dir> --gate converged" in section, name
        assert section.index("deltafuse advance") < section.index("deltafuse archive"), name


def test_specify_propose_retry_stops_at_a_human_gate_refusal() -> None:
    """F18: "fix the listed errors and run it again" loops on a refusal that is
    not the Worker's to fix - an unresolved blocking Decision, or a capability
    the catalog still carries as `draft` (fsm.py `_draft_capability_errors`,
    `_check_gate` blocked-on-decision). Both are answered by a human.
    """
    text = (SKILLS_DIR / "specify" / "SKILL.md").read_text(encoding="utf-8")
    rule = [line for line in text.splitlines() if "fix the listed errors" in line]
    assert rule, "specify: propose step no longer tells the Worker what a refusal means"
    assert "blocked-on-decision" in rule[0]
    assert "status: draft" in rule[0]
    assert re.search(r"\bstop\b", rule[0], re.IGNORECASE)
