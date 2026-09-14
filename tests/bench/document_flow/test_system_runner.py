import json
from pathlib import Path

import pytest

from scripts.document_flow.clients import KafkaClient, ReadOnlySqlClient, UnsafeObservation
from scripts.document_flow.faults import BarrierReceipt, FaultController, FaultDenied
from scripts.document_flow.system_runner import (
    CommandResult, PRODUCT_BUILD_FAILURE, INFRASTRUCTURE_INVALID,
    SystemRunner, tree_identity,
)


class FakeExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, argv, *, cwd, env=None, timeout=None):
        self.calls.append((tuple(argv), Path(cwd), dict(env or {}), timeout))
        return self.results.pop(0)


def test_kafka_client_uses_runtime_java_boundary_not_missing_native_cli(monkeypatch):
    ok = CommandResult(("docker",), 0, "message\n", "", 1)
    executor = FakeExecutor([ok, ok, ok, ok])
    client = KafkaClient(executor, "j03-probe-kafka-kafka-1")
    monkeypatch.setattr(client, "_compiled_probe", lambda: b"class-bytes")
    published = client.publish("j03.document-events", "key-1", '{"schema_name":"unknown"}')
    consumed = client.consume("j03.workflow-dlq", max_messages=1)
    assert published.exit_code == consumed.exit_code == 0
    flattened = [part for call in executor.calls for part in call[0]]
    assert "/opt/kafka/bin/kafka-console-consumer.sh" not in flattened
    assert "j03-probe-kafka-workflow-service-1" in flattened
    assert "J03KafkaProbe.class" in " ".join(flattened)


def result(exit_code=0, stdout="", stderr=""):
    return CommandResult(tuple(), exit_code, stdout, stderr, 1)


def snapshot(tmp_path):
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / "source.txt").write_text("bounded\n", encoding="utf-8")
    return root


def test_bad_image_is_infrastructure_invalid_with_diagnostics(tmp_path):
    executor = FakeExecutor([
        result(),
        result(1, stderr="manifest unknown: image digest unavailable"),
        result(stdout="[]"), result(stdout="pull failed"),
    ])
    evidence = SystemRunner(executor).execute(snapshot(tmp_path), "run-bad-image", tmp_path / "evidence")
    assert evidence.exit_code == INFRASTRUCTURE_INVALID == 3
    assert evidence.classification == "infrastructure-invalid"
    assert evidence.phase == "build"
    assert evidence.commands[-1]["exit_code"] == 1
    assert (tmp_path / "evidence/system.json").is_file()


def test_worker_java_compilation_is_product_build_failure(tmp_path):
    executor = FakeExecutor([
        result(1, stderr="[ERROR] COMPILATION ERROR cannot find symbol"),
        result(stdout="[]"), result(stdout="compiler output"),
    ])
    evidence = SystemRunner(executor).execute(snapshot(tmp_path), "run-compile", tmp_path / "evidence")
    assert evidence.exit_code == PRODUCT_BUILD_FAILURE == 1
    assert evidence.classification == "product-build-failure"


def test_dropped_judge_connection_is_infrastructure_invalid(tmp_path):
    executor = FakeExecutor([
        result(), result(), result(),
        result(7, stderr="connection refused"),
        result(stdout="ps"), result(stdout="logs"), result(),
    ])
    evidence = SystemRunner(executor).execute(snapshot(tmp_path), "run-drop", tmp_path / "evidence")
    assert evidence.exit_code == 3
    assert evidence.phase == "readiness"
    assert evidence.diagnostics


@pytest.mark.parametrize("sql", [
    "DELETE FROM route", "SELECT * FROM route; DROP TABLE route",
    "UPDATE route SET state='APPROVED'", "SELECT pg_sleep(1)",
    "WITH changed AS (DELETE FROM route RETURNING *) SELECT * FROM changed",
])
def test_sql_observer_denies_arbitrary_or_mutating_sql(sql):
    client = ReadOnlySqlClient(FakeExecutor([]), "postgres-1", "j03_workflow", "j03_judge")
    with pytest.raises(UnsafeObservation):
        client.query(sql)


def test_sql_observer_allows_named_projection_and_forces_read_only(tmp_path):
    executor = FakeExecutor([result(stdout="[{\"state\":\"PENDING\"}]")])
    client = ReadOnlySqlClient(executor, "postgres-1", "j03_workflow", "j03_judge")
    rows = client.query("SELECT state FROM route WHERE route_id = 'route-1'")
    assert rows == [{"state": "PENDING"}]
    argv = executor.calls[0][0]
    assert argv[:3] == ("docker", "exec", "postgres-1")
    assert "BEGIN READ ONLY" in argv[-1]


def test_fault_requires_barrier_and_exact_run_label(tmp_path):
    denied = FaultController(FakeExecutor([]), "run-1")
    with pytest.raises(FaultDenied):
        denied.kill("service-1", BarrierReceipt("b-1", False, 0))
    wrong = FakeExecutor([result(stdout="run-other")])
    with pytest.raises(FaultDenied):
        FaultController(wrong, "run-1").kill("service-1", BarrierReceipt("b-1", True, 12))
    executor = FakeExecutor([result(stdout="run-1"), result()])
    receipt = FaultController(executor, "run-1").kill(
        "service-1", BarrierReceipt("b-1", True, 12))
    assert receipt["measured_sequence"] == 12
    assert executor.calls[-1][0] == ("docker", "kill", "service-1")


def test_snapshot_identity_is_deterministic_and_rejects_links(tmp_path):
    root = snapshot(tmp_path)
    assert tree_identity(root) == tree_identity(root)
    if hasattr(Path, "symlink_to"):
        link = root / "escape"
        try:
            link.symlink_to(tmp_path / "outside")
        except OSError:
            pytest.skip("symlink creation unavailable")
        with pytest.raises(ValueError, match="link"):
            tree_identity(root)


def test_unique_project_and_run_labels_are_passed_without_host_mounts(tmp_path):
    executor = FakeExecutor([result(), result(), result(), result(), result(stdout="[]"), result(stdout="logs"), result()])
    root = snapshot(tmp_path)
    evidence = SystemRunner(executor).execute(root, "run-unique", tmp_path / "evidence")
    assert evidence.exit_code == 0
    calls = [call[0] for call in executor.calls]
    assert any("--project-name" in argv and "j03-run-unique" in argv for argv in calls)
    assert all("/var/run/docker.sock" not in " ".join(argv) for argv in calls)
    saved = json.loads((tmp_path / "evidence/system.json").read_text(encoding="utf-8"))
    assert saved["snapshot_sha256"] == tree_identity(root)
