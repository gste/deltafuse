"""DAG and dependency graph analyzer with cycle detection and topological sorting."""

from __future__ import annotations
from typing import Collection

class DependencyCycleError(Exception):
    """Raised when a circular dependency is detected in tasks or slices."""
    def __init__(self, cycle_nodes: list[str]):
        chain = " -> ".join(cycle_nodes)
        super().__init__(f"Circular dependency detected among nodes: {chain}")
        self.cycle_nodes = cycle_nodes

def topological_sort(graph: dict[str, Collection[str]]) -> list[str]:
    """Performs topological sort on a dependency graph using Kahn's algorithm."""
    in_degree = {node: 0 for node in graph}
    dependents: dict[str, list[str]] = {node: [] for node in graph}

    for node, deps in graph.items():
        for dep in deps:
            if dep in graph:
                in_degree[node] += 1
                dependents[dep].append(node)

    queue = [node for node, deg in in_degree.items() if deg == 0]
    result: list[str] = []

    while queue:
        current = queue.pop(0)
        result.append(current)

        for dep_node in dependents.get(current, []):
            in_degree[dep_node] -= 1
            if in_degree[dep_node] == 0:
                queue.append(dep_node)

    if len(result) != len(graph):
        unresolved = [node for node, deg in in_degree.items() if deg > 0]
        raise DependencyCycleError(unresolved)

    return result
