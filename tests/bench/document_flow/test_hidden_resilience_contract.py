"""Contract tests for bounded, receipt-derived resilience scoring."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).parents[3]
HIDDEN = ROOT / "process/bench/cases/J03-document-flow/hidden_suite"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name):
    spec = importlib.util.spec_from_file_location("j03_resilience_" + name, HIDDEN / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resilience_registry_is_fixed_and_complete():
    checks = _load("test_resilience.py").CHECKS
    assert [check["id"] for check in checks] == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]
    assert sum(check["points"] for check in checks) == 600
    assert all(check["assertions"] and check["fault"] for check in checks)


def test_atomicity_registry_is_fixed():
    checks = _load("test_atomicity.py").CHECKS
    assert checks[0]["id"] == "SYS.C01"
    assert checks[0]["points"] == 160
    assert len(checks[0]["assertions"]) == 3


def test_missing_fault_receipt_is_fail_closed():
    resilience = _load("test_resilience.py")
    facts = resilience.derive_facts({})
    assert resilience.earned_points(facts) == 0
    assert resilience.expected_failed_ids(facts) == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]


def test_unacknowledged_fault_cannot_earn_points():
    resilience = _load("test_resilience.py")
    observation = {"fault_receipts": [{"point": "after-commit-before-ack",
                                         "acknowledged": False,
                                         "measured_sequence": 4,
                                         "recovered": True, "effect_count": 1}]}
    assert resilience.earned_points(resilience.derive_facts(observation)) == 0


def test_green_requires_all_explicit_receipts_and_atomic_facts():
    resilience = _load("test_resilience.py")
    observation = {"fault_receipts": [
        {"point": "after-commit-before-ack", "acknowledged": True, "measured_sequence": 1,
         "recovered": True, "effect_count": 1},
        {"point": "after-publish-before-sent", "acknowledged": True, "measured_sequence": 2,
         "recovered": True, "published_count": 1},
        {"point": "topic-replay", "acknowledged": True, "measured_sequence": 3,
         "replayed": True, "audit_count": 4, "unique_event_count": 4},
        {"point": "temporary-outage", "acknowledged": True, "measured_sequence": 4,
         "recovered": True, "partial_state": False},
    ]}
    assert resilience.earned_points(resilience.derive_facts(observation)) == 600


def test_induced_faulty_receipts_fail_exactly_their_named_checks():
    resilience = _load("test_resilience.py")

    def receipts(overrides=None):
        base = [
            {"point": "after-commit-before-ack", "measured_sequence": 1,
             "recovered": True, "effect_count": 1},
            {"point": "after-publish-before-sent", "measured_sequence": 2,
             "recovered": True, "published_count": 1},
            {"point": "topic-replay", "measured_sequence": 3, "replayed": True,
             "audit_count": 4, "unique_event_count": 4},
            {"point": "temporary-outage", "measured_sequence": 4,
             "recovered": True, "partial_state": False},
        ]
        for entry in base:
            entry.setdefault("acknowledged", True)
            entry.update((overrides or {}).get(entry["point"], {}))
        return {"fault_receipts": base}

    duplicate_effect = resilience.derive_facts(
        receipts({"after-commit-before-ack": {"effect_count": 2}}))
    assert resilience.expected_failed_ids(duplicate_effect) == ["SYS.R01"]

    lost_publication = resilience.derive_facts(
        receipts({"after-publish-before-sent": {"recovered": False}}))
    assert resilience.expected_failed_ids(lost_publication) == ["SYS.R02"]

    replay_dupes = resilience.derive_facts(
        receipts({"topic-replay": {"audit_count": 5, "unique_event_count": 4}}))
    assert resilience.expected_failed_ids(replay_dupes) == ["SYS.R03"]

    partial_recovery = resilience.derive_facts(
        receipts({"temporary-outage": {"partial_state": True}}))
    assert resilience.expected_failed_ids(partial_recovery) == ["SYS.R04"]

    atomicity = _load("test_atomicity.py")
    split_state = atomicity.derive_facts({"inbox_outbox_consistent": True,
                                          "delivery_receipt": True,
                                          "cross_service_write_denied": False})
    assert atomicity.expected_failed_ids(split_state) == ["SYS.C01"]
    assert atomicity.earned_points(split_state) == 0


def test_hardcoded_control_fails_every_resilience_check():
    resilience = _load("test_resilience.py")
    control = resilience.hardcoded_happy_path_control()
    assert control["points"] == 0
    assert control["expected_failed_ids"] == ["SYS.R01", "SYS.R02", "SYS.R03", "SYS.R04"]
    assert _load("test_atomicity.py").hardcoded_happy_path_control()["expected_failed_ids"] == ["SYS.C01"]


def test_live_executors_return_atomic_facts_not_exit_derived_scores():
    resilience = _load("test_resilience.py")
    atomicity = _load("test_atomicity.py")
    assert callable(resilience.execute_live) and callable(resilience.arm_run_stack)
    assert callable(atomicity.execute_live)
    for module in (resilience, atomicity):
        assert "exit_code" not in module.earned_points.__code__.co_names


def test_fault_arming_binds_exact_seed_wiring_and_stays_inert_by_default():
    resilience = _load("test_resilience.py")
    seed = ROOT / "process/bench/cases/J03-document-flow/seed"
    assert resilience.BARRIER_MARKER in resilience.HOOK_SOURCE
    assert 'System.getenv("' + resilience.BARRIER_ENV + '")' in resilience.HOOK_SOURCE
    assert "Runtime.getRuntime().halt(" + str(resilience.HALT_EXIT_CODE) + ")" in resilience.HOOK_SOURCE
    assert len(resilience.HOOK_SOURCE) < 4096
    patched_paths = set()
    for target in resilience.ARMING_TARGETS:
        source = (seed / target["path"]).read_text(encoding="utf-8")
        assert source.count(target["original"]) == 1, target["path"]
        # The hook argument is inserted before the constructor's closing paren.
        assert target["replacement"].startswith(target["original"][:-1] + ","), target["path"]
        assert 'J03FaultArm.hook(' in target["replacement"]
        patched_paths.add(target["path"])
    assert patched_paths == {
        "workflow-service/src/main/java/dev/deltafuse/bench/workflow/messaging/"
        "WorkflowMessagingConfiguration.java",
        "document-service/src/main/java/dev/deltafuse/bench/document/messaging/"
        "DocumentMessagingConfiguration.java"}


def test_arm_run_stack_applies_once_and_refuses_reapplication(tmp_path):
    resilience = _load("test_resilience.py")
    seed = ROOT / "process/bench/cases/J03-document-flow/seed"
    run_tree = tmp_path / "run"
    shutil.copytree(seed, run_tree)
    manifest = resilience.arm_run_stack(run_tree)
    assert manifest["armed"] is True and manifest["barrier_env"] == resilience.BARRIER_ENV
    hook = (run_tree / resilience.HOOK_RELATIVE).read_text(encoding="utf-8")
    assert hook == resilience.HOOK_SOURCE
    for target in resilience.ARMING_TARGETS:
        patched = (run_tree / target["path"]).read_text(encoding="utf-8")
        assert target["replacement"] in patched
        assert target["original"] not in patched
    compose_arm = (run_tree / "compose-arm.yaml").read_text(encoding="utf-8")
    assert resilience.BARRIER_ENV in compose_arm
    try:
        resilience.arm_run_stack(run_tree)
    except RuntimeError:
        pass
    else:
        raise AssertionError("re-arming an armed run tree must fail closed")


def _load_driver_modules():
    return _load("test_resilience.py"), _load("test_atomicity.py")


def _live_main():
    import faulthandler
    import subprocess
    import sys
    import time
    from scripts.document_flow.clients import HttpClient, KafkaClient, ReadOnlySqlClient
    from scripts.document_flow.system_runner import CommandResult

    # The run must terminate even if a child call stalls; the watchdog dumps
    # thread stacks to stderr and exits instead of hanging silently.
    faulthandler.dump_traceback_later(1200, exit=True)

    def phase(name):
        print("[j03] phase " + name, file=sys.stderr, flush=True)

    # Compiling the judge Kafka probe per call is pure overhead; memoize it
    # without changing the client contract.
    original_probe = KafkaClient._compiled_probe
    probe_cache = {}

    def memoized_probe(self):
        if "class_bytes" not in probe_cache:
            probe_cache["class_bytes"] = original_probe(self)
        return probe_cache["class_bytes"]

    KafkaClient._compiled_probe = memoized_probe

    def bounded_run(argv, *, cwd, env=None, timeout):
        """Run a child with its whole process tree killed on deadline expiry."""
        started = time.monotonic()
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=30)
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            exit_code = 124
        return CommandResult(tuple(argv), exit_code, stdout or "", stderr or "",
                             int((time.monotonic() - started) * 1000))

    resilience, atomicity = _load_driver_modules()
    stack_dir = Path(os.environ["J03_RESILIENCE_STACK_DIR"]).resolve(strict=True)
    run_id = os.environ["J03_RESILIENCE_RUN_ID"]
    project = os.environ["J03_RESILIENCE_PROJECT"]
    judge = os.environ.get("J03_JUDGE_USER", "j03_judge_readonly")
    settle = float(os.environ.get("J03_SETTLE_SECONDS", "1.0"))
    state = json.loads(Path(os.environ["J03_RUN_STATE_FILE"]).read_text(encoding="utf-8"))
    compose_env = dict(os.environ)
    compose_env.update({"J03_RUN_ID": run_id, "J03_COMPOSE_PROJECT": project,
                        "J03_POSTGRES_PASSWORD": state["postgres"],
                        "J03_DOCUMENT_DB_PASSWORD": state["document"],
                        "J03_WORKFLOW_DB_PASSWORD": state["workflow"],
                        "J03_AUDIT_DB_PASSWORD": state["audit"],
                        "J03_JUDGE_DB_PASSWORD": state["judge"]})
    containers = {name: os.environ["J03_RESILIENCE_CONTAINER_" + name.upper()]
                  for name in ("postgres", "kafka", "workflow", "document", "audit")}
    postgres, kafka_container = containers["postgres"], containers["kafka"]
    def executor(argv, *, cwd, env=None, timeout=60):
        return bounded_run(argv, cwd=cwd, env=env, timeout=timeout)

    document_sql = ReadOnlySqlClient(executor, postgres, "j03_document", judge)
    workflow_sql = ReadOnlySqlClient(executor, postgres, "j03_workflow", judge)
    audit_sql = ReadOnlySqlClient(executor, postgres, "j03_audit", judge)
    kafka = KafkaClient(executor, kafka_container)

    compose_base = ["docker", "compose", "-f", str(stack_dir / "compose.yaml"),
                    "-f", str(stack_dir / "compose-arm.yaml"),
                    "--project-name", project, "--project-directory", str(stack_dir)]
    service_container = {"workflow-service": "workflow", "document-service": "document",
                         "postgres": "postgres", "kafka": "kafka", "audit-service": "audit"}

    def compose(*arguments, timeout=240):
        phase("compose " + " ".join(arguments[:3]))
        return executor(compose_base + list(arguments), cwd=str(stack_dir),
                        env=compose_env, timeout=timeout)

    def write_arm(mapping):
        lines = ["services:"]
        for service in ("workflow-service", "document-service"):
            lines += [f"  {service}:", "    environment:",
                      f'      {resilience.BARRIER_ENV}: "{mapping.get(service, "")}"']
        (stack_dir / "compose-arm.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def container_state(name):
        phase("inspect state " + name)
        result = executor(
            ["docker", "inspect", containers[name], "--format",
             "{{.State.Status}}:{{.State.ExitCode}}"], cwd=".", timeout=15)
        parsed = (result.stdout.strip().split(":") + ["", ""])[:2]
        return {"status": parsed[0], "exit_code": int(parsed[1] or 0),
                "argv": list(result.argv), "inspect_exit": result.exit_code}

    def logs(name):
        result = executor(["docker", "logs", containers[name]],
                          cwd=".", timeout=30)
        return result.stdout + result.stderr

    def await_healthy(name, deadline_seconds):
        deadline = time.monotonic() + deadline_seconds
        while time.monotonic() < deadline:
            result = executor(
                ["docker", "inspect", containers[name], "--format",
                 "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"],
                cwd=".", timeout=15)
            if result.stdout.strip() == "healthy":
                return True
            time.sleep(1.0)
        return False

    def arm(service, barrier):
        phase("arm " + service + " " + (barrier or "(inert)"))
        write_arm({service: barrier})
        started = compose("up", "-d", "--no-deps", service)
        if started.exit_code != 0:
            raise RuntimeError("compose up failed for " + service + ": " + started.stderr[-800:])
        if not await_healthy(service_container[service], 120):
            raise RuntimeError("armed service never became healthy: " + service)

    def fault(service, action):
        """Run-owned outage control: verify the run label, then compose stop/up.

        The driver drives compose directly instead of spawning a shell wrapper;
        a single child process cannot leak pipe-holding grandchildren.
        """
        phase("fault " + service + " " + action)
        listed = compose("ps", "-qa", service, timeout=60)
        if listed.exit_code != 0 or not listed.stdout.strip():
            raise RuntimeError("service is not run-owned or absent: " + service)
        for container_id in listed.stdout.split():
            owner = executor(["docker", "inspect", container_id, "--format",
                              "{{ index .Config.Labels \"dev.deltafuse.run\" }}"],
                             cwd=".", timeout=15)
            if owner.exit_code != 0 or owner.stdout.strip() != run_id:
                raise RuntimeError("ownership mismatch for " + container_id)
        if action == "stop":
            result = compose("stop", "--timeout", "10", service, timeout=120)
        else:
            result = compose("up", "-d", "--no-deps", service, timeout=180)
        exit_code = result.exit_code
        if action != "stop" and exit_code == 0 and not await_healthy(service_container[service], 150):
            exit_code = 1
        return {"service": service, "action": action, "exit": exit_code,
                "argv": list(result.argv), "stdout_tail": result.stdout[-400:],
                "stderr_tail": result.stderr[-800:]}

    def denial(role, database, sql):
        phase("denial probe " + role + " -> " + database)
        result = executor(
            ["docker", "exec", postgres, "psql", "-X", "-v", "ON_ERROR_STOP=1",
             "-U", role, "-d", database, "-c", sql], cwd=".", timeout=30)
        return {"argv": list(result.argv), "exit_code": result.exit_code,
                "stdout": result.stdout, "stderr": result.stderr}

    context = {"executor": executor, "stack_dir": stack_dir, "run_id": run_id,
               "project": project, "containers": containers, "kafka": kafka,
               "document_sql": document_sql, "workflow_sql": workflow_sql,
               "audit_sql": audit_sql, "document_url": os.environ["J03_DOCUMENT_URL"],
               "workflow_url": os.environ["J03_WORKFLOW_URL"], "judge_user": judge,
               "settle_seconds": settle, "sleep": time.sleep, "monotonic": time.monotonic,
               "http": HttpClient,
               "arm": arm, "fault": fault, "logs": logs,
               "container_state": container_state, "await_healthy": await_healthy}

    phase("resilience execute_live")
    live = resilience.execute_live(context)
    phase("atomicity execute_live")
    consistent = atomicity.execute_live(os.environ["J03_DOCUMENT_URL"], document_sql,
                                        workflow_sql, audit_sql, denial,
                                        settle_seconds=settle)
    fail_closed = resilience.derive_facts({
        "fault_receipts": [{key: value for key, value in receipt.items() if key != "acknowledged"}
                           for receipt in live["receipts"]]})
    control_r = resilience.hardcoded_happy_path_control()
    control_a = atomicity.hardcoded_happy_path_control()
    payload = {"label": os.environ["J03_LIVE_LABEL"], "resilience": live,
               "atomicity": consistent,
               "fail_closed_control": {"facts": fail_closed,
                                       "points": resilience.earned_points(fail_closed),
                                       "expected_failed_ids": resilience.expected_failed_ids(fail_closed)},
               "hardcoded_control": {"resilience": control_r, "atomicity": control_a}}
    target = Path(os.environ["J03_LIVE_OUTPUT"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    failed = resilience.expected_failed_ids(live["facts"]) + atomicity.expected_failed_ids(
        consistent["facts"])
    print(json.dumps({"label": payload["label"],
                      "resilience_points": live["points"],
                      "atomicity_points": consistent["points"],
                      "failed_ids": failed,
                      "fail_closed_failed_ids": payload["fail_closed_control"]["expected_failed_ids"],
                      "hardcoded_failed_ids": control_r["expected_failed_ids"]
                          + control_a["expected_failed_ids"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(_live_main())
