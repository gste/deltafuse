# Acceptance tests for S10: resume without duplication/loss, then re-slice safely.
# Hidden from the executing model. change_data is assembled by the A09 harness.


def test_same_change_after_resume(change_data):
    original = change_data.get("change_id")
    resumed = change_data.get("resume_change_id", original)
    assert original, "Missing original change_id"
    assert resumed == original, f"Resume created a different change: {original} vs {resumed}"
    extras = change_data.get("duplicate_change_ids", [])
    assert extras == [], f"Resume duplicated changes: {extras}"


def test_red_evidence_preserved(change_data):
    red = change_data.get("red_evidence", [])
    task_ids = [e.get("task") for e in red]
    assert "TASK-001" in task_ids, "Interrupted TASK-001 Red evidence was lost on resume"


def test_no_duplicate_tasks(change_data):
    tasks = change_data.get("tasks", [])
    ids = [t.get("id") for t in tasks]
    dupes = [i for i in ids if ids.count(i) > 1]
    assert dupes == [], f"Duplicate task ids after resume/re-slice: {dupes}"


def test_reslice_keeps_cancelled_on_disk(change_data):
    tasks = change_data.get("tasks", [])
    terminal = [t for t in tasks if t.get("status") in ("cancelled", "superseded")]
    deleted = change_data.get("deleted_task_files", [])
    assert terminal, "Re-slice did not cancel or supersede obsolete tasks"
    assert deleted == [], f"Cancelled/superseded task files were deleted: {deleted}"


def test_implemented_work_retained(change_data):
    tasks = {t.get("id"): t for t in change_data.get("tasks", [])}
    first = tasks.get("TASK-001", {})
    assert first.get("status") in ("implemented", "verified"), \
        f"Completed TASK-001 was lost or reset: {first.get('status')}"
    code_changes = change_data.get("code_modifications", [])
    assert len(code_changes) > 0, "Implemented consume-history code is missing after re-slice"


def test_converge_with_cancelled_tasks(change_data):
    status = change_data.get("status", "")
    gate_errors = change_data.get("converged_gate_errors", [])
    cancelled = [e for e in gate_errors if "cancelled" in e or "superseded" in e]
    assert status in ("converged", "archived"), f"Expected converge after re-slice, got {status}"
    assert cancelled == [], f"Cancelled/superseded tasks blocked converge: {cancelled}"
