# Dataset structures and loaders for DeltaFuse LLM Evals.

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class EvalCase:
    case_id: str
    title: str
    category: str
    raw_prompt: str
    expected_primary_capability: str
    expected_claims: list[str] = field(default_factory=list)
    expected_slices: list[str] = field(default_factory=lambda: ["SLICE-01"])
    expected_target_gate: str = "converged"
    expected_outcome: str = "pass"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        return cls(
            case_id=data["case_id"],
            title=data.get("title", data["case_id"]),
            category=data.get("category", "feature"),
            raw_prompt=data["raw_prompt"],
            expected_primary_capability=data["expected_primary_capability"],
            expected_claims=list(data.get("expected_claims", ["CR-001"])),
            expected_slices=list(data.get("expected_slices", ["SLICE-01"])),
            expected_target_gate=data.get("expected_target_gate", "converged"),
            expected_outcome=data.get("expected_outcome", "pass"),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "category": self.category,
            "raw_prompt": self.raw_prompt,
            "expected_primary_capability": self.expected_primary_capability,
            "expected_claims": self.expected_claims,
            "expected_slices": self.expected_slices,
            "expected_target_gate": self.expected_target_gate,
            "expected_outcome": self.expected_outcome,
            "metadata": self.metadata,
        }


@dataclass
class EvalDataset:
    name: str
    description: str
    cases: list[EvalCase] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cases)

    def get_case(self, case_id: str) -> EvalCase | None:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None

    def filter_by_category(self, category: str) -> list[EvalCase]:
        return [c for c in self.cases if c.category == category]

    @classmethod
    def load_from_dict(cls, data: dict[str, Any]) -> EvalDataset:
        cases = [EvalCase.from_dict(c) for c in data.get("cases", [])]
        return cls(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            cases=cases,
        )

    @classmethod
    def load_from_file(cls, file_path: Path | str) -> EvalDataset:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid dataset format in {path}: expected YAML mapping")
        return cls.load_from_dict(data)

    def save_to_file(self, file_path: Path | str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "description": self.description,
            "cases": [c.to_dict() for c in self.cases],
        }
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @classmethod
    def get_default_dataset(cls) -> EvalDataset:
        data_file = Path(__file__).parent / "data" / "default_cases.yaml"
        if data_file.is_file():
            return cls.load_from_file(data_file)
        return cls(
            name="default_dataset",
            description="Built-in DeltaFuse Eval dataset",
            cases=[
                EvalCase(
                    case_id="EVAL-FEAT-001",
                    title="Implement Retry Gateway Policy",
                    category="feature",
                    raw_prompt="Implement retry policy for retry gateway.",
                    expected_primary_capability="gateway.retry",
                    expected_claims=["CR-001", "CR-002"],
                    expected_slices=["SLICE-01"],
                    expected_target_gate="converged",
                    expected_outcome="pass",
                )
            ],
        )
