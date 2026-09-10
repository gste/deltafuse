"""Install a product tree for an agent-agnostic bench case. Does not copy the oracle."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from deltafuse.bench import BenchError
from deltafuse.bench.loader import load_case, resolve_cases_root
from deltafuse.core.hasher import compute_file_sha256
from deltafuse.core.installer import install


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def init_bench_product(
    case_id: str,
    product_dir: Path | str,
    *,
    framework_root: Path | str | None = None,
    pack_root: Path | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Create a worker sandbox. Oracle and hidden_suite stay in the judge pack."""
    product = Path(product_dir).resolve()
    marker = product / ".deltafuse" / "bench.yaml"
    if marker.is_file() and not force:
        raise BenchError(f"{product} already has a bench workspace (use --force)")
    cases = resolve_cases_root(pack_root, default_framework=True)
    case = load_case(case_id, cases, oracle=False)
    case_dir: Path = case["dir"]
    product.mkdir(parents=True, exist_ok=True)
    install(target_dir=product, framework_root=framework_root, force=True)
    _copy_tree(case_dir / "seed", product)
    intake_name = str(case.get("intake_name") or f"{case_id}.md")
    intake_src = case_dir / "input.md"
    if intake_src.is_file():
        dest = product / "docs" / "intake" / intake_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(intake_src, dest)
    worker = case_dir / "WORKER.md"
    if worker.is_file():
        shutil.copy2(worker, product / "BENCH.md")
    seed_hashes: dict[str, str] = {}
    for rel in case.get("seed_must_stay_until_implement") or []:
        path = product / str(rel)
        if path.is_file():
            seed_hashes[str(rel).replace("\\", "/")] = compute_file_sha256(path)
    meta = {
        "case": case["id"],
        "intake": f"docs/intake/{intake_name}",
        "seed_hashes": seed_hashes,
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
    return meta


def format_worker_start_prompt(meta: dict[str, Any]) -> str:
    """Copy-paste prompt for the Worker agent after a successful init."""
    intake = str(meta.get("intake") or "docs/intake/")
    return (
        "You are the Worker in this DeltaFuse product. Read BENCH.md. "
        f"Intake is {intake}.\n"
        "\n"
        "Run `deltafuse next`. Load the skill it names. Write only what that step allows. "
        "Repeat until `deltafuse next` has nothing ready.\n"
        "\n"
        "Stay inside this project. Human Gates stay human."
    )
