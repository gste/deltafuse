# LLM Provider interfaces and Mock Provider for deterministic CI evals.

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable
import yaml
from deltafuse.evals.dataset import EvalCase
from deltafuse.core.hasher import compute_product_baseline_revision


class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def generate_change_package(self, case: EvalCase, target_dir: Path) -> Path:
        pass


class MockLLMProvider(LLMProvider):
    """Deterministic Mock LLM Provider supporting golden, schema violation,
    FSM violation, routing mismatch, and hallucination scenarios.
    """

    def __init__(
        self,
        scenario: str = "golden",
        custom_overrides: dict[str, Any] | None = None,
    ):
        self.scenario = scenario
        self.custom_overrides = custom_overrides or {}

    @property
    def name(self) -> str:
        return f"mock:{self.scenario}"

    def generate_change_package(self, case: EvalCase, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        # Ensure specification directory exists for eval packages
        repo_root = target_dir.parent
        spec_dir = repo_root / "docs" / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_file = spec_dir / "core.md"
        if not spec_file.is_file():
            spec_file.write_text("# Specification\n## REQ-01\nRequirement 01\n", encoding="utf-8")
        baseline = compute_product_baseline_revision(repo_root)
        cid = case.case_id if case.case_id.startswith("CHG-") else f"CHG-999-{case.case_id.lower().replace('_', '-')}"

        # 1. request.md
        if self.scenario == "claim_hallucination":
            claims = ["CR-999"]
            claims_text = "- CR-999: Spurious hallucinated claim"
        else:
            claims = case.expected_claims if case.expected_claims else ["CR-001"]
            claims_text = "\n".join(f"- {c}: Requirement for {c} in {case.title}" for c in claims)

        (target_dir / "request.md").write_text(f"# Request\n{claims_text}\n", encoding="utf-8")

        # 2. change.yaml
        status_map = {
            "intake": "normalized",
            "analyzed": "analyzed",
            "specified": "specified",
            "decomposed": "decomposed",
            "targeting": "targeting",
            "implemented": "implemented",
            "converged": "converged",
            "not-reproduced": "not-reproduced",
        }
        final_status = status_map.get(case.expected_target_gate, "converged")
        intent_val = "bugfix" if case.category == "bug" else "feature"

        slice_objs = [
            {
                "id": sl,
                "file": f"slices/{sl}.md",
                "status": "draft",
            }
            for sl in case.expected_slices
        ]

        change_yaml: dict[str, Any] = {
            "schema_version": 2,
            "id": cid,
            "title": case.title,
            "status": final_status,
            "framework": {
                "version": "2.0.0",
                "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            },
            "intent": intent_val,
            "risk": case.metadata.get("risk", "low"),
            "source": {"request": "request.md", "intake_refs": []},
            "deltas": [],
            "slices": slice_objs if final_status != "normalized" else [],
            "decisions": [],
            "tasks": ["TASK-001"] if final_status not in {"normalized", "analyzed", "specified"} else [],
            "verification": None,
        }

        if final_status != "normalized":
            change_yaml["analysis"] = {"routing": "routing.yaml", "summary": "analysis.md"}

        if self.scenario == "schema_violation":
            del change_yaml["schema_version"]
            del change_yaml["id"]
            change_yaml["status"] = "INVALID_STATUS_ENUM"

        (target_dir / "change.yaml").write_text(yaml.safe_dump(change_yaml, sort_keys=False), encoding="utf-8")

        if case.expected_target_gate == "intake":
            return target_dir

        # 3. routing.yaml & analysis.md
        cap = case.expected_primary_capability
        if self.scenario == "routing_mismatch":
            cap = "wrong.mismatch.capability"

        routing_claims: dict[str, Any] = {}
        for c in claims:
            routing_claims[c] = {
                "summary": f"Routing summary for {c}",
                "primary_capability": cap,
                "related_capabilities": [],
                "policies": [],
                "confidence": "high",
            }

        routing_data = {
            "change": cid,
            "claims": routing_claims,
        }

        if self.scenario == "schema_violation":
            routing_data = {"corrupted": "no change id or claims"}

        (target_dir / "routing.yaml").write_text(yaml.safe_dump(routing_data, sort_keys=False), encoding="utf-8")
        (target_dir / "analysis.md").write_text(f"# Analysis\nAnalysis for {case.title}.", encoding="utf-8")

        # 4. Slices & coverage.yaml
        slices_dir = target_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        for sl in case.expected_slices:
            slice_md = (
                f"---\n"
                f"id: {sl}\n"
                f"change: {cid}\n"
                f"title: Title for {sl}\n"
                f"status: draft\n"
                f"primary_capability: {cap}\n"
                f"related_capabilities: []\n"
                f"policies: []\n"
                f"spec_refs: [docs/spec/core.md#REQ-01]\n"
                f"claims: [{', '.join(claims)}]\n"
                f"depends_on: []\n"
                f"context_budget: {{max_tokens: 16000, max_files: 20}}\n"
                f"---\n\n# {sl}\nDetails\n"
            )
            (slices_dir / f"{sl}.md").write_text(slice_md, encoding="utf-8")

        has_tasks = final_status not in {"normalized", "analyzed", "specified"}
        cov_claims: dict[str, Any] = {}
        for i, c in enumerate(claims):
            sl = case.expected_slices[i % len(case.expected_slices)]
            ev_map: dict[str, str] = {}
            if has_tasks and self.scenario != "fsm_violation":
                ev_map["red"] = "evidence/red/TASK-001.yaml"
            if final_status in {"implemented", "converged"}:
                ev_map["green"] = "evidence/green/TASK-001.yaml"
                ev_map["regression"] = "evidence/regression/TASK-001.yaml"
            if final_status == "converged":
                ev_map["verification"] = "evidence/verification/run.yaml"

            cov_claims[c] = {
                "slice": sl,
                "tasks": ["TASK-001"] if has_tasks else [],
                "spec_refs": ["docs/spec/core.md#REQ-01"],
                "evidence": ev_map,
                "status": "verified" if final_status == "converged" else "pending",
            }

        coverage_data = {
            "change": cid,
            "claims": cov_claims,
        }
        (target_dir / "coverage.yaml").write_text(yaml.safe_dump(coverage_data, sort_keys=False), encoding="utf-8")

        if case.expected_target_gate in {"analyzed", "not-reproduced"}:
            return target_dir

        # 5. spec-delta.md
        spec_delta = (
            f"---\n"
            f"change: {cid}\n"
            f"status: proposed\n"
            f"slices: [{', '.join(case.expected_slices)}]\n"
            f"added: []\n"
            f"modified: []\n"
            f"removed: []\n"
            f"---\n\n# Spec Delta\nDetails\n"
        )
        (target_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")

        if case.expected_target_gate == "specified":
            return target_dir

        # 6. Tasks
        tasks_dir = target_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_status = "verified" if final_status == "converged" else ("implemented" if final_status == "implemented" else "pending")
        task_md = (
            f"---\n"
            f"id: TASK-001\n"
            f"change: {cid}\n"
            f"slice: {case.expected_slices[0]}\n"
            f"kind: feature\n"
            f"status: {task_status}\n"
            f"depends_on: []\n"
            f"requirement_delta: added\n"
            f"spec_refs: [docs/spec/core.md#REQ-01]\n"
            f"design_ref: null\n"
            f"allowed_paths: [src/core.py]\n"
            f"forbidden_paths: [src/secret.py]\n"
            f"context_budget: {{max_tokens: 16000, max_files: 24}}\n"
            f"---\n\n# TASK-001\nImplementation details\n"
        )
        (tasks_dir / "TASK-001.md").write_text(task_md, encoding="utf-8")

        if case.expected_target_gate == "decomposed":
            return target_dir

        # 7. Red evidence (skipped in fsm_violation)
        if self.scenario != "fsm_violation":
            red_dir = target_dir / "evidence" / "red"
            red_dir.mkdir(parents=True, exist_ok=True)
            ev_red = {
                "schema_version": 2,
                "change": cid,
                "task": "TASK-001",
                "phase": "red",
                "timestamp": "2026-09-05T12:00:00Z",
                "command": "pytest tests/test_task.py",
                "exit_code": 1,
                "result": "expected-failure",
                "failure_category": "behavioral-mismatch",
                "summary": "Expected test failure in red phase",
                "changed_paths": ["tests/test_task.py"],
                "spec_status": "unchanged",
            }
            (red_dir / "TASK-001.yaml").write_text(yaml.safe_dump(ev_red, sort_keys=False), encoding="utf-8")

        if case.expected_target_gate in {"targeting", "target-confirmed"}:
            return target_dir

        # 8. Green & Regression evidence
        green_dir = target_dir / "evidence" / "green"
        reg_dir = target_dir / "evidence" / "regression"
        green_dir.mkdir(parents=True, exist_ok=True)
        reg_dir.mkdir(parents=True, exist_ok=True)

        ev_green = {
            "schema_version": 2,
            "change": cid,
            "task": "TASK-001",
            "phase": "green",
            "timestamp": "2026-09-05T12:10:00Z",
            "command": "pytest tests/test_task.py",
            "exit_code": 0,
            "result": "passed",
            "summary": "Green test pass",
            "changed_paths": ["src/core.py"],
            "spec_status": "unchanged",
            "base_revision": baseline,
        }
        (green_dir / "TASK-001.yaml").write_text(yaml.safe_dump(ev_green, sort_keys=False), encoding="utf-8")

        ev_reg = {
            "schema_version": 2,
            "change": cid,
            "task": "TASK-001",
            "phase": "regression",
            "timestamp": "2026-09-05T12:15:00Z",
            "command": "pytest tests/",
            "exit_code": 0,
            "result": "passed",
            "summary": "Regression suite pass",
            "changed_paths": ["src/core.py"],
            "spec_status": "unchanged",
            "base_revision": baseline,
        }
        (reg_dir / "TASK-001.yaml").write_text(yaml.safe_dump(ev_reg, sort_keys=False), encoding="utf-8")

        if case.expected_target_gate == "implemented":
            return target_dir

        # 9. Verification evidence
        (target_dir / "verification.md").write_text("# Verification\nAll verified.", encoding="utf-8")
        ver_dir = target_dir / "evidence" / "verification"
        ver_dir.mkdir(parents=True, exist_ok=True)
        ev_ver = {
            "schema_version": 2,
            "change": cid,
            "phase": "verification",
            "timestamp": "2026-09-05T12:20:00Z",
            "command": "pytest tests/",
            "exit_code": 0,
            "result": "passed",
            "summary": "Full verification run passed",
            "changed_paths": [],
            "spec_status": "unchanged",
            "base_revision": baseline,
        }
        (ver_dir / "run.yaml").write_text(yaml.safe_dump(ev_ver, sort_keys=False), encoding="utf-8")

        return target_dir


class CallableLLMProvider(LLMProvider):
    def __init__(self, name: str, generator: Callable[[EvalCase, Path], Path]):
        self._name = name
        self._generator = generator

    @property
    def name(self) -> str:
        return self._name

    def generate_change_package(self, case: EvalCase, target_dir: Path) -> Path:
        return self._generator(case, target_dir)


class RealLLMProvider(LLMProvider):
    """Real LLM Provider calling OpenAI / Anthropic / Gemini API if API key is present."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        import os
        self.model = model
        self.api_key = api_key or os.getenv("DELTAFUSE_API_KEY") or os.getenv("OPENAI_API_KEY")

    @property
    def name(self) -> str:
        return f"real:{self.model}"

    def generate_change_package(self, case: EvalCase, target_dir: Path) -> Path:
        if not self.api_key:
            raise RuntimeError(
                "RealLLMProvider requires DELTAFUSE_API_KEY or OPENAI_API_KEY environment variable. "
                "Use --provider mock for deterministic offline execution."
            )
        # Network integration stub: if key is present, real calls can be dispatched
        raise NotImplementedError("Online remote LLM invocation requires active API endpoint.")
