"""Helper fixture builder for constructing mock DeltaFuse change packages programmatically."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

class MockChangeBuilder:
    def __init__(self, root_dir: Path, change_id: str = "CHG-001", title: str = "Mock Change"): 
        self.change_dir = root_dir / "docs" / "changes" / f"{change_id}-test"
        self.change_dir.mkdir(parents=True, exist_ok=True)
        self.change_id = change_id
        self.title = title

    def step_intake(self, claims: list[str] | None = None) -> MockChangeBuilder:
        if claims is None:
            claims = ["CR-001"]
        claims_text = "\n".join(f"- {c}: Description for {c}" for c in claims)
        (self.change_dir / "request.md").write_text(f"# Request\n{claims_text}\n", encoding="utf-8")
        change_yaml = {
            "schema_version": 2,
            "id": self.change_id,
            "title": self.title,
            "status": "normalized",
            "framework": {
                "version": "2.0.0",
                "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            },
            "intent": "feature",
            "risk": "low",
            "source": {"request": "request.md", "intake_refs": []},
            "analysis": {"routing": "routing.yaml", "summary": "analysis.md"},
            "deltas": [],
            "slices": [],
            "decisions": [],
            "tasks": [],
            "verification": None,
        }
        (self.change_dir / "change.yaml").write_text(yaml.safe_dump(change_yaml), encoding="utf-8")
        return self

    def step_analyze(self, slices: list[str] | None = None) -> MockChangeBuilder:
        if slices is None:
            slices = ["SLICE-01"]
        routing = {
            "change": self.change_id,
            "claims": {
                "CR-001": {
                    "summary": "Claim 1",
                    "primary_capability": "system.core",
                    "related_capabilities": [],
                    "policies": [],
                    "confidence": "high",
                }
            },
        }
        (self.change_dir / "routing.yaml").write_text(yaml.safe_dump(routing), encoding="utf-8")
        (self.change_dir / "analysis.md").write_text("# Analysis\nAnalysis summary.", encoding="utf-8")
        slices_dir = self.change_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        for sl in slices:
            slice_md = (
                f"---\n"
                f"id: {sl}\n"
                f"change: {self.change_id}\n"
                f"title: Title for {sl}\n"
                f"status: draft\n"
                f"primary_capability: system.core\n"
                f"related_capabilities: []\n"
                f"policies: []\n"
                f"spec_refs: [docs/spec/core.md]\n"
                f"claims: [CR-001]\n"
                f"depends_on: []\n"
                f"context_budget: {{max_tokens: 16000, max_files: 20}}\n"
                f"---\n\n# {sl}\nDetails\n"
            )
            (slices_dir / f"{sl}.md").write_text(slice_md, encoding="utf-8")
        cov = {
            "change": self.change_id,
            "claims": {
                "CR-001": {
                    "slice": "SLICE-01",
                    "tasks": ["TASK-001"],
                    "spec_refs": ["docs/spec/core.md"],
                    "evidence": {
                        "red": "evidence/red/TASK-001.yaml",
                        "green": "evidence/green/TASK-001.yaml",
                        "regression": "evidence/regression/TASK-001.yaml",
                        "verification": "evidence/verification/run.yaml",
                    },
                    "status": "pending",
                }
            },
        }
        (self.change_dir / "coverage.yaml").write_text(yaml.safe_dump(cov), encoding="utf-8")
        return self

    def step_specify(self) -> MockChangeBuilder:
        spec_delta = (
            f"---\n"
            f"change: {self.change_id}\n"
            f"status: proposed\n"
            f"slices: [SLICE-01]\n"
            f"added: [docs/spec/core.md#REQ-01]\n"
            f"modified: []\n"
            f"removed: []\n"
            f"---\n\n# Spec Delta\nDetails\n"
        )
        (self.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
        return self

    def step_decompose(self, tasks: list[dict[str, Any]] | None = None) -> MockChangeBuilder:
        if tasks is None:
            tasks = [{
                "id": "TASK-001",
                "slice": "SLICE-01",
                "depends_on": [],
            }]
        tasks_dir = self.change_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        for t in tasks:
            tid = t["id"]
            slice_id = t.get("slice", "SLICE-01")
            deps = t.get("depends_on", [])
            deps_str = str(deps).replace("'", "")
            task_md = (
                f"---\n"
                f"id: {tid}\n"
                f"change: {self.change_id}\n"
                f"slice: {slice_id}\n"
                f"kind: feature\n"
                f"status: pending\n"
                f"depends_on: {deps_str}\n"
                f"requirement_delta: added\n"
                f"spec_refs: [docs/spec/core.md#REQ-01]\n"
                f"design_ref: null\n"
                f"allowed_paths: [src/core.py]\n"
                f"forbidden_paths: [src/secret.py]\n"
                f"---\n\n# {tid}\nImplementation details\n"
            )
            (tasks_dir / f"{tid}.md").write_text(task_md, encoding="utf-8")
        return self

    def step_target(self, task_id: str = "TASK-001") -> MockChangeBuilder:
        red_dir = self.change_dir / "evidence" / "red"
        red_dir.mkdir(parents=True, exist_ok=True)
        ev = {
            "schema_version": 2,
            "change": self.change_id,
            "task": task_id,
            "phase": "red",
            "timestamp": "2026-09-05T12:00:00Z",
            "command": f"pytest tests/test_{task_id.lower()}.py",
            "exit_code": 1,
            "result": "expected-failure",
            "failure_category": "behavioral-mismatch",
            "summary": "Test failed as expected",
            "changed_paths": [f"tests/test_{task_id.lower()}.py"],
            "spec_status": "unchanged",
        }
        (red_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev), encoding="utf-8")
        return self

    def step_implement(self, task_id: str = "TASK-001") -> MockChangeBuilder:
        green_dir = self.change_dir / "evidence" / "green"
        reg_dir = self.change_dir / "evidence" / "regression"
        green_dir.mkdir(parents=True, exist_ok=True)
        reg_dir.mkdir(parents=True, exist_ok=True)
        ev_green = {
            "schema_version": 2,
            "change": self.change_id,
            "task": task_id,
            "phase": "green",
            "timestamp": "2026-09-05T12:10:00Z",
            "command": f"pytest tests/test_{task_id.lower()}.py",
            "exit_code": 0,
            "result": "passed",
            "summary": "Test passed after implementation",
            "changed_paths": ["src/core.py"],
            "spec_status": "unchanged",
        }
        (green_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_green), encoding="utf-8")
        ev_reg = {
            "schema_version": 2,
            "change": self.change_id,
            "task": task_id,
            "phase": "regression",
            "timestamp": "2026-09-05T12:15:00Z",
            "command": "pytest tests/",
            "exit_code": 0,
            "result": "passed",
            "summary": "Full test suite passed",
            "changed_paths": ["src/core.py"],
            "spec_status": "unchanged",
        }
        (reg_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_reg), encoding="utf-8")
        return self

    def step_verify(self) -> MockChangeBuilder:
        (self.change_dir / "verification.md").write_text("# Verification\nAll claims verified.", encoding="utf-8")
        ver_dir = self.change_dir / "evidence" / "verification"
        ver_dir.mkdir(parents=True, exist_ok=True)
        ev_ver = {
            "schema_version": 2,
            "change": self.change_id,
            "phase": "verification",
            "timestamp": "2026-09-05T12:20:00Z",
            "command": "pytest tests/",
            "exit_code": 0,
            "result": "passed",
            "summary": "Verification pass passed",
            "changed_paths": [],
            "spec_status": "unchanged",
        }
        (ver_dir / "run.yaml").write_text(yaml.safe_dump(ev_ver), encoding="utf-8")
        return self
