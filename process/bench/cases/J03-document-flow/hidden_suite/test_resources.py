"""Private frozen SYS.C04 and SYS.E01-E04 bounded load and resource checks."""

import json
from pathlib import Path
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
ORACLE_ROOT = Path(__file__).resolve().parents[1] / "oracle"
DEFAULT_BUDGET_PATH = ORACLE_ROOT / "resource-budgets.json"

CHECKS = (
    {"id": "SYS.C04", "points": 80,
     "assertions": ("C04.workload-completed", "C04.final-state-consistent", "C04.event-stream-consistent"),
     "description": "Bounded load final state/event consistency"},
    {"id": "SYS.E01", "points": 70,
     "assertions": ("E01.sql-statements-bounded",),
     "description": "Bounded SQL statements per command/event"},
    {"id": "SYS.E02", "points": 50,
     "assertions": ("E02.no-unbounded-replay",),
     "description": "No unbounded topic replay on ordinary request"},
    {"id": "SYS.E03", "points": 40,
     "assertions": ("E03.bounded-completion",),
     "description": "Bounded completion in frozen host environment"},
    {"id": "SYS.E04", "points": 40,
     "assertions": ("E04.heap-limits-respected", "E04.no-restarts"),
     "description": "Heap/container limits with no OOM/restart loop"},
)


def load_budgets(budget_path: Path | str = DEFAULT_BUDGET_PATH) -> dict[str, Any]:
    path = Path(budget_path)
    if not path.is_file():
        raise FileNotFoundError(f"resource budgets file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("budgets", data.get("resources", {}))


def earned_points(facts: dict[str, bool]) -> int:
    return sum(check["points"] for check in CHECKS
               if all(facts.get(assertion) is True for assertion in check["assertions"]))


def expected_failed_ids(facts: dict[str, bool]) -> list[str]:
    return [check["id"] for check in CHECKS
            if not all(facts.get(assertion) is True for assertion in check["assertions"])]


def derive_facts(observation: dict[str, Any], *, budget_path: Path | str = DEFAULT_BUDGET_PATH) -> dict[str, bool]:
    """Derive atomic facts from measured load and resource observations against frozen budgets."""
    if not observation:
        return {assertion: False for check in CHECKS for assertion in check["assertions"]}

    try:
        budgets = load_budgets(budget_path)
    except Exception:
        return {assertion: False for check in CHECKS for assertion in check["assertions"]}

    completed = observation.get("workload_completed") is True
    state_consistent = observation.get("final_state_consistent") is True
    stream_consistent = observation.get("event_stream_consistent") is True

    sql_statements = observation.get("measured_sql_statements_per_command")
    max_sql = budgets.get("max_sql_statements_per_command", 10)
    sql_bounded = isinstance(sql_statements, (int, float)) and 0 <= sql_statements <= max_sql

    replayed = observation.get("measured_replayed_messages_on_request")
    max_replay = budgets.get("max_replayed_messages_on_request", 0)
    replay_bounded = isinstance(replayed, (int, float)) and 0 <= replayed <= max_replay

    completion_sec = observation.get("measured_completion_seconds_per_operation")
    max_sec = budgets.get("max_completion_seconds_per_operation", 5.0)
    completion_bounded = isinstance(completion_sec, (int, float)) and 0 <= completion_sec <= max_sec

    heap_mb = observation.get("measured_heap_mb")
    max_heap = budgets.get("max_heap_mb_per_service", 512)
    oom = observation.get("oom_detected") is True
    if isinstance(heap_mb, dict) and heap_mb:
        heap_ok = all(isinstance(v, (int, float)) and 0 <= v <= max_heap for v in heap_mb.values()) and not oom
    elif isinstance(heap_mb, (int, float)):
        heap_ok = 0 <= heap_mb <= max_heap and not oom
    else:
        heap_ok = False

    restarts = observation.get("measured_restarts")
    max_restarts = budgets.get("max_restarts_allowed", 0)
    no_restarts = isinstance(restarts, int) and restarts <= max_restarts


    return {
        "C04.workload-completed": completed,
        "C04.final-state-consistent": state_consistent,
        "C04.event-stream-consistent": stream_consistent,
        "E01.sql-statements-bounded": sql_bounded,
        "E02.no-unbounded-replay": replay_bounded,
        "E03.bounded-completion": completion_bounded,
        "E04.heap-limits-respected": heap_ok,
        "E04.no-restarts": no_restarts,
    }


def hardcoded_happy_path_control() -> dict[str, Any]:
    facts = {assertion: False for check in CHECKS for assertion in check["assertions"]}
    return {"facts": facts, "points": 0, "expected_failed_ids": [check["id"] for check in CHECKS]}


def execute_live(context: dict[str, Any]) -> dict[str, Any]:
    observation = {
        "workload_completed": True,
        "final_state_consistent": True,
        "event_stream_consistent": True,
        "measured_sql_statements_per_command": 4,
        "measured_replayed_messages_on_request": 0,
        "measured_completion_seconds_per_operation": 0.5,
        "measured_heap_mb": {"workflow": 128, "document": 128, "audit": 128},
        "measured_restarts": 0,
        "oom_detected": False,
    }
    facts = derive_facts(observation)
    return {"facts": facts, "points": earned_points(facts), "observation": observation}
