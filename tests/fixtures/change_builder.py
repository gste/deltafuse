"""Helper fixture builder for constructing mock DeltaFuse change packages programmatically."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.core.hasher import compute_product_baseline_revision


class MockChangeBuilder:
    def __init__(
        self,
        root_dir: Path,
        change_id: str = "CHG-001",
        title: str = "Mock Change",
        route: str = "code",
    ): 
        self.root_dir = root_dir
        self.change_dir = root_dir / "docs" / "changes" / f"{change_id}-test"
        self.change_dir.mkdir(parents=True, exist_ok=True)
        self.change_id = change_id
        self.title = title
        self.route = route
        spec_dir = self.root_dir / "docs" / "spec"
        spec_core = spec_dir / "core.md"
        if spec_dir.is_dir() and not spec_core.exists():
            spec_core.write_text("# Core Spec\n## REQ-01\nCore requirement.\n", encoding="utf-8")
        if spec_dir.is_dir() and spec_core.is_file():
            self._ensure_core_capability()

    def _ensure_core_capability(self) -> None:
        catalog_path = self.root_dir / "docs" / "spec" / "_capabilities.yaml"
        data: dict[str, Any] = {"schema_version": 2, "domains": {}}
        if catalog_path.is_file():
            loaded = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        domains = data.setdefault("domains", {})
        if not isinstance(domains, dict):
            domains = {}
            data["domains"] = domains
        system = domains.setdefault("system", {})
        if not isinstance(system, dict):
            system = {}
            domains["system"] = system
        system.setdefault("summary", "Core system")
        caps = system.setdefault("capabilities", {})
        if not isinstance(caps, dict):
            caps = {}
            system["capabilities"] = caps
        caps.setdefault(
            "core",
            {
                "summary": "Core capability",
                "spec": ["docs/spec/core.md"],
            },
        )
        catalog_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _baseline_revision(self) -> str:
        return compute_product_baseline_revision(self.root_dir)

    def _update_change_yaml(self, updates: dict[str, Any]) -> None:
        cfile = self.change_dir / "change.yaml"
        if cfile.is_file():
            data = yaml.safe_load(cfile.read_text(encoding="utf-8"))
        else:
            data = {}
        data.update(updates)
        cfile.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def step_intake(self, claims: list[str] | None = None) -> MockChangeBuilder:
        if claims is None:
            claims = ["CR-001"]
        self.claims = list(claims)
        claims_text = "\n".join(f"- {c}: Description for {c}" for c in self.claims)
        (self.change_dir / "request.md").write_text(f"# Request\n{claims_text}\n", encoding="utf-8")
        lock_file = self.root_dir / ".deltafuse" / "lock.yaml"
        fw_hash = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        if lock_file.is_file():
            try:
                ldata = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
                fw_hash = ldata.get("framework", {}).get("content_hash", fw_hash)
            except Exception:
                pass

        change_yaml = {
            "schema_version": 2,
            "id": self.change_id,
            "title": self.title,
            "status": "normalized",
            "framework": {
                "version": "2.0.0",
                "content_hash": fw_hash,
            },
            "intent": "feature",
            "risk": "low",
            "source": {"request": "request.md", "intake_refs": []},
            "deltas": [],
            "slices": [],
            "decisions": [],
            "tasks": [],
            "verification": None,
        }
        if self.route != "code":
            change_yaml["route"] = self.route
        (self.change_dir / "change.yaml").write_text(yaml.safe_dump(change_yaml, sort_keys=False), encoding="utf-8")
        return self

    def step_analyze(self, slices: list[str] | None = None) -> MockChangeBuilder:
        if slices is None:
            slices = ["SLICE-01"]
        claims = list(getattr(self, "claims", ["CR-001"]))
        routing_claims = {
            cid: {
                "summary": f"Claim {cid}",
                "primary_capability": "system.core",
                "related_capabilities": [],
                "policies": [],
                "confidence": "high",
            }
            for cid in claims
        }
        routing = {
            "change": self.change_id,
            "claims": routing_claims,
        }
        if self.route != "code":
            routing["route"] = self.route
        (self.change_dir / "routing.yaml").write_text(yaml.safe_dump(routing), encoding="utf-8")
        (self.change_dir / "analysis.md").write_text("# Analysis\nAnalysis summary.", encoding="utf-8")
        slices_dir = self.change_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        slice_objs = []
        claims_yaml = "[" + ", ".join(claims) + "]"
        for sl in slices:
            slice_objs.append({
                "id": sl,
                "file": f"slices/{sl}.md",
                "status": "draft",
            })
            slice_md = (
                f"---\n"
                f"id: {sl}\n"
                f"change: {self.change_id}\n"
                f"title: Title for {sl}\n"
                f"status: draft\n"
                f"primary_capability: system.core\n"
                f"related_capabilities: []\n"
                f"policies: []\n"
                f"spec_refs: [docs/spec/core.md#REQ-01]\n"
                f"claims: {claims_yaml}\n"
                f"depends_on: []\n"
                f"context_budget: {{max_tokens: 16000, max_files: 20}}\n"
                f"---\n\n# {sl}\nDetails\n"
            )
            (slices_dir / f"{sl}.md").write_text(slice_md, encoding="utf-8")
        cov_claims = {
            cid: {
                "slice": "SLICE-01",
                "tasks": [],
                "spec_refs": ["docs/spec/core.md#REQ-01"],
                "evidence": {},
                "status": "pending",
            }
            for cid in claims
        }
        cov = {
            "change": self.change_id,
            "claims": cov_claims,
        }
        (self.change_dir / "coverage.yaml").write_text(yaml.safe_dump(cov), encoding="utf-8")
        self._update_change_yaml({
            "status": "analyzed",
            "analysis": {"routing": "routing.yaml", "summary": "analysis.md"},
            "slices": slice_objs,
        })
        return self

    def step_specify(self) -> MockChangeBuilder:
        spec_delta = (
            f"---\n"
            f"change: {self.change_id}\n"
            f"status: proposed\n"
            f"slices: [SLICE-01]\n"
            f"added: []\n"
            f"modified: []\n"
            f"removed: []\n"
            f"---\n\n# Spec Delta\nDetails\n"
        )
        (self.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
        self._update_change_yaml({"status": "specification-proposed"})
        from deltafuse.core.decide import apply_decision

        apply_decision(self.change_dir, status="accepted", spec=True)
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
        task_ids = []
        for t in tasks:
            tid = t["id"]
            task_ids.append(tid)
            slice_id = t.get("slice", "SLICE-01")
            deps = t.get("depends_on", [])
            deps_str = str(deps).replace("'", "")
            if "allowed_paths" in t:
                allowed = t["allowed_paths"]
            elif self.route == "docs":
                allowed = ["docs/spec/core.md"]
            elif self.route == "ops":
                allowed = ["docs/ops/runbook.md"]
            else:
                allowed = ["src/core.py"]
            allowed_str = "[" + ", ".join(allowed) + "]"
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
                f"allowed_paths: {allowed_str}\n"
                f"forbidden_paths: [src/secret.py]\n"
                f"context_budget: {{max_tokens: 16000, max_files: 24}}\n"
                f"---\n\n# {tid}\nImplementation details\n"
            )
            (tasks_dir / f"{tid}.md").write_text(task_md, encoding="utf-8")

        # Update coverage with tasks
        cov_file = self.change_dir / "coverage.yaml"
        if cov_file.is_file():
            cov = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
            if "claims" in cov and "CR-001" in cov["claims"]:
                cov["claims"]["CR-001"]["tasks"] = task_ids
            cov_file.write_text(yaml.safe_dump(cov), encoding="utf-8")

        self._update_change_yaml({
            "status": "decomposed",
            "tasks": task_ids,
        })
        return self

    def step_declare(self, task_id: str = "TASK-001") -> MockChangeBuilder:
        red_dir = self.change_dir / "evidence" / "red"
        red_dir.mkdir(parents=True, exist_ok=True)
        if self.route == "docs":
            ev = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "red",
                "timestamp": "2026-09-05T12:00:00Z",
                "command": "python -c \"from pathlib import Path; raise SystemExit(0 if Path('docs/spec/core.md').is_file() else 1)\"",
                "exit_code": 0,
                "result": "already-green",
                "summary": "Spec file oracle already on disk",
                "changed_paths": ["docs/spec/core.md"],
                "spec_status": "unchanged",
            }
        elif self.route == "ops":
            ev = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "red",
                "timestamp": "2026-09-05T12:00:00Z",
                "command": "python -c \"from pathlib import Path; raise SystemExit(0 if Path('docs/ops/runbook.md').is_file() else 1)\"",
                "exit_code": 1,
                "result": "expected-failure",
                "failure_category": "missing-artifact",
                "summary": "Ops file not yet written",
                "changed_paths": ["docs/ops/runbook.md"],
                "spec_status": "unchanged",
            }
        else:
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

        cov_file = self.change_dir / "coverage.yaml"
        if cov_file.is_file():
            cov = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
            if "claims" in cov and "CR-001" in cov["claims"]:
                cov["claims"]["CR-001"]["evidence"]["red"] = f"evidence/red/{task_id}.yaml"
            cov_file.write_text(yaml.safe_dump(cov), encoding="utf-8")

        self._update_change_yaml({"status": "targeting"})
        return self

    def step_implement(self, task_id: str = "TASK-001") -> MockChangeBuilder:
        green_dir = self.change_dir / "evidence" / "green"
        green_dir.mkdir(parents=True, exist_ok=True)
        if self.route == "docs":
            ev_green = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "green",
                "timestamp": "2026-09-05T12:10:00Z",
                "command": "python -c \"from pathlib import Path; raise SystemExit(0 if Path('docs/spec/core.md').is_file() else 1)\"",
                "exit_code": 0,
                "result": "passed",
                "summary": "Docs file oracle passed",
                "changed_paths": ["docs/spec/core.md"],
                "spec_status": "unchanged",
                "base_revision": self._baseline_revision(),
            }
            (green_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_green), encoding="utf-8")
            ev_reg = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "regression",
                "timestamp": "2026-09-05T12:15:00Z",
                "command": "python -c \"print('docs-route: no product pytest')\"",
                "exit_code": 0,
                "result": "passed",
                "summary": "No src regression for docs route",
                "changed_paths": ["docs/spec/core.md"],
                "spec_status": "unchanged",
                "base_revision": self._baseline_revision(),
            }
            reg_dir = self.change_dir / "evidence" / "regression"
            reg_dir.mkdir(parents=True, exist_ok=True)
            (reg_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_reg), encoding="utf-8")
        elif self.route == "ops":
            ev_green = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "green",
                "timestamp": "2026-09-05T12:10:00Z",
                "command": "python -c \"from pathlib import Path; raise SystemExit(0 if Path('docs/ops/runbook.md').is_file() else 1)\"",
                "exit_code": 0,
                "result": "passed",
                "summary": "Ops file oracle passed",
                "changed_paths": ["docs/ops/runbook.md"],
                "spec_status": "unchanged",
                "base_revision": self._baseline_revision(),
            }
            (green_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_green), encoding="utf-8")
            ev_reg = {
                "schema_version": 2,
                "change": self.change_id,
                "task": task_id,
                "phase": "regression",
                "timestamp": "2026-09-05T12:15:00Z",
                "command": "python -c \"print('ops-route: no product pytest')\"",
                "exit_code": 0,
                "result": "passed",
                "summary": "No src regression for ops route",
                "changed_paths": ["docs/ops/runbook.md"],
                "spec_status": "unchanged",
                "base_revision": self._baseline_revision(),
            }
            reg_dir = self.change_dir / "evidence" / "regression"
            reg_dir.mkdir(parents=True, exist_ok=True)
            (reg_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_reg), encoding="utf-8")
        else:
            reg_dir = self.change_dir / "evidence" / "regression"
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
                "base_revision": self._baseline_revision(),
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
                "base_revision": self._baseline_revision(),
            }
            (reg_dir / f"{task_id}.yaml").write_text(yaml.safe_dump(ev_reg), encoding="utf-8")

        task_file = self.change_dir / "tasks" / f"{task_id}.md"
        if task_file.is_file():
            meta, body = parse_frontmatter(task_file.read_text(encoding="utf-8"))
            meta["status"] = "implemented"
            front = yaml.safe_dump(meta, sort_keys=False)
            task_file.write_text(f"---\n{front}---\n{body}", encoding="utf-8")

        cov_file = self.change_dir / "coverage.yaml"
        if cov_file.is_file():
            cov = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
            if "claims" in cov and "CR-001" in cov["claims"]:
                cov["claims"]["CR-001"]["evidence"]["green"] = f"evidence/green/{task_id}.yaml"
                cov["claims"]["CR-001"]["evidence"]["regression"] = f"evidence/regression/{task_id}.yaml"
            cov_file.write_text(yaml.safe_dump(cov), encoding="utf-8")

        self._update_change_yaml({"status": "implemented"})
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
            "command": (
                "pytest tests/"
                if self.route == "code"
                else "python -c \"print('verify: file and traceability oracle')\""
            ),
            "exit_code": 0,
            "result": "passed",
            "summary": "Verification pass passed",
            "changed_paths": [],
            "spec_status": "unchanged",
            "base_revision": self._baseline_revision(),
        }
        (ver_dir / "run.yaml").write_text(yaml.safe_dump(ev_ver), encoding="utf-8")

        tasks_dir = self.change_dir / "tasks"
        if tasks_dir.is_dir():
            for tf in tasks_dir.glob("*.md"):
                meta, body = parse_frontmatter(tf.read_text(encoding="utf-8"))
                meta["status"] = "verified"
                front = yaml.safe_dump(meta, sort_keys=False)
                tf.write_text(f"---\n{front}---\n{body}", encoding="utf-8")

        cov_file = self.change_dir / "coverage.yaml"
        if cov_file.is_file():
            cov = yaml.safe_load(cov_file.read_text(encoding="utf-8"))
            if "claims" in cov and "CR-001" in cov["claims"]:
                cov["claims"]["CR-001"]["evidence"]["verification"] = "evidence/verification/run.yaml"
                cov["claims"]["CR-001"]["status"] = "verified"
            cov_file.write_text(yaml.safe_dump(cov), encoding="utf-8")

        self._update_change_yaml({"status": "converged"})
        return self
