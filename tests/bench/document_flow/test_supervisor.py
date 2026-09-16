"""Unit tests for BenchmarkSupervisor."""

import tempfile
from pathlib import Path
from scripts.document_flow.supervisor import BenchmarkSupervisor


def test_supervisor_initializes_and_inspects_state():
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        # Empty dir will fail next, but supervisor handles initialization
        supervisor = BenchmarkSupervisor(sandbox)
        assert supervisor.sandbox == sandbox.resolve()
