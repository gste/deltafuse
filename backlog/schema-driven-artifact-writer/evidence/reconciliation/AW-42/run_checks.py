#!/usr/bin/env python3
"""AW-42 final-tree check driver: run each required check, capture argv, exit,
stdout and stderr verbatim, and index the raw logs with SHA256.

Usage:
    python run_checks.py [--repo ROOT]

Writes raw/<name>.log, raw/<name>.exit and check-index.json (whose own digest is
recorded externally, never inside itself).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CHECKS = [
    ("wheel-and-cli-suite", [sys.executable, "-m", "pytest",
                             "tests/integration/test_artifact_cli.py",
                             "tests/integration/test_wheel_smoke.py",
                             "tests/integration/test_wheel_evidence.py",
                             "-v", "--no-header", "-rA"], 1800),
    ("policy-security-eval-suite", [sys.executable, "-m", "pytest",
                                    "tests/unit/test_artifact_writer_eval.py",
                                    "tests/unit/test_artifact_policy.py",
                                    "tests/unit/test_artifact_registry.py",
                                    "tests/integration/test_artifact_security.py",
                                    "-v", "--no-header", "-rA"], 900),
    ("backlog-checker", [sys.executable, "backlog/schema-driven-artifact-writer/"
                         "check_backlog.py",
                         "backlog/schema-driven-artifact-writer/queue.json"], 300),
    ("backlog-checker-tests", [sys.executable, "-m", "pytest",
                               "backlog/schema-driven-artifact-writer/tests/"
                               "test_check_backlog.py", "-v", "--no-header"], 300),
    ("asset-sync-check", [sys.executable, "scripts/sync_assets.py", "--check"], 300),
    ("diff-hygiene", ["git", "diff", "--check"], 120),
    ("status-hygiene", ["git", "status", "--porcelain=v1"], 120),
    ("smoke-ps1", ["pwsh", "-NoProfile", "-File", "tests/smoke-test.ps1"], 1800),
    ("smoke-sh", ["bash", "tests/smoke-test.sh"], 1800),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--only", default=None, help="run only this check name")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    bundle = repo / "backlog" / "schema-driven-artifact-writer" / "evidence" \
        / "reconciliation" / "AW-42"
    raw = bundle / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    results = []
    for name, argv, timeout in CHECKS:
        if args.only and name != args.only:
            continue
        try:
            proc = subprocess.run(argv, cwd=repo, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
            exit_code, out, err = proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError as exc:
            exit_code, out, err = 127, "", f"launcher unavailable: {exc}"
        except subprocess.TimeoutExpired as exc:
            exit_code, out, err = 124, (exc.stdout or ""), f"timeout after {timeout}s"
        (raw / f"{name}.log").write_text(out + ("\n--- stderr ---\n" + err if err else ""),
                                         encoding="utf-8", newline="\n")
        (raw / f"{name}.exit").write_text(str(exit_code), encoding="utf-8", newline="\n")
        results.append({"name": name, "argv": [str(a) for a in argv], "exit": exit_code,
                        "raw_log": f"raw/{name}.log",
                        "raw_log_sha256": hashlib.sha256(
                            (raw / f"{name}.log").read_bytes()).hexdigest()})
        tail = (out.strip().splitlines() or ["<no stdout>"])[-1]
        print(f"{name}: exit={exit_code} :: {tail[:150]}")

    index = {
        "card": "AW-42",
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python": sys.version.split()[0],
            "node": _first_line(["node", "--version"]),
            "filesystem_note": "Windows NTFS worktree; POSIX checks are not run here",
        },
        "checks": results,
    }
    (bundle / "check-index.json").write_text(json.dumps(index, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps({"ran": len(results),
                      "nonzero": [r["name"] for r in results if r["exit"] != 0]}))
    return 0


def _first_line(argv: list[str]) -> str:
    try:
        return subprocess.run(argv, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
