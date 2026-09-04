import pytest
from deltafuse.core.graph import topological_sort, DependencyCycleError

def test_empty_graph():
    assert topological_sort({}) == []

def test_linear_dependency():
    graph = {
        "TASK-001": [],
        "TASK-002": ["TASK-001"],
        "TASK-003": ["TASK-002"]
    }
    order = topological_sort(graph)
    assert order == ["TASK-001", "TASK-002", "TASK-003"]

def test_branching_and_merging_dag():
    graph = {
        "TASK-001": [],
        "TASK-002": ["TASK-001"],
        "TASK-003": ["TASK-001"],
        "TASK-004": ["TASK-002", "TASK-003"]
    }
    order = topological_sort(graph)
    assert order.index("TASK-001") == 0
    assert order.index("TASK-004") == 3
    assert set(order[1:3]) == {"TASK-002", "TASK-003"}

def test_direct_cycle():
    graph = {
        "TASK-001": ["TASK-002"],
        "TASK-002": ["TASK-001"]
    }
    with pytest.raises(DependencyCycleError) as exc:
        topological_sort(graph)
    assert "TASK-001" in str(exc.value) or "TASK-002" in str(exc.value)

def test_indirect_cycle():
    graph = {
        "TASK-001": ["TASK-003"],
        "TASK-002": ["TASK-001"],
        "TASK-003": ["TASK-002"]
    }
    with pytest.raises(DependencyCycleError):
        topological_sort(graph)
