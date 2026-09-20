"""AW-40 delivery probe: verify exact multi-line prompt delivery at the child-process boundary.

Replays the frozen live_paired_runner.py invocation path (same argv construction via
shutil.which -> little-coder.CMD -> cmd.exe) for the CASE-01 arm-B multiline prompt,
with the local observability extension attached, then byte-compares the model-visible
user message captured in .pi/observability/trace.ndjson against the intended prompt.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE
REPO = HERE.parents[2]
sys.path.insert(0, str(EVAL))

from live_paired_runner import arm_b_prompt, arm_a_prompt, MODEL  # noqa: E402

CORPUS = json.loads(
    (REPO / "tests" / "fixtures" / "artifact_writer_eval" / "eval_corpus.json").read_text(encoding="utf-8")
)
LITTLE_CODER = shutil.which("little-coder") or "little-coder"
EXTENSION = r"C:\Users\ghost\workspace\gste\little-coder-extensions\observability-extension\index.ts"
TRACE = REPO / ".pi" / "observability" / "trace.ndjson"
OUT_DIR = HERE / "delivery-probe-2026-09-20"
OUT_DIR.mkdir(exist_ok=True)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def run_case(case: dict, label: str, prompt: str) -> dict:
    sys_prompt = (
        "You are a precise structured-data authoring assistant. You have no "
        "tools and must never mention or emit tool_calls. You must follow the "
        "user's output-format instruction exactly: output ONLY the requested "
        "structure, with EXACTLY the requested values, and never add extra "
        "fields (no status, changeId, author, created, name, type, "
        "lifecycleStage, metadata or other invented keys)."
    )
    transport = sys.argv[1] if len(sys.argv) > 1 else "cmd-shim"
    if transport.startswith("node-direct"):
        node = shutil.which("node")
        entry = (Path(shutil.which("little-coder") or "").parent
                 / "node_modules" / "little-coder" / "bin" / "little-coder.mjs")
        prefix = [node, str(entry)]
    else:
        prefix = [LITTLE_CODER]
    argv = prefix + ["--model", MODEL, "--no-tools", "--no-session",
                     "--mode", "text", "--no-extensions", "--extension", EXTENSION,
                     "--system-prompt", sys_prompt, "-p", prompt]
    # Neutral-cwd variants: run the child outside any repo with AGENTS.md so the
    # CLI's built-in project-context injection has nothing to load.
    child_cwd = None
    if transport == "node-direct-neutral":
        child_cwd = tempfile.mkdtemp(prefix="aw40-neutral-cwd-")
    started = time.time()
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=child_cwd,
                          encoding="utf-8", errors="replace", timeout=240)
    trace_path = TRACE
    if child_cwd:
        trace_path = Path(child_cwd) / ".pi" / "observability" / "trace.ndjson"
    return {
        "label": label,
        "case_id": case["id"],
        "intended_prompt": prompt,
        "intended_sha256": sha256(prompt),
        "intended_len": len(prompt),
        "intended_newlines": prompt.count("\n"),
        "argv": argv,
        "child_cwd": child_cwd,
        "trace_path": str(trace_path),
        "exit": proc.returncode,
        "stdout": proc.stdout,
        "stderr": (proc.stderr or "")[:2000],
        "duration_s": round(time.time() - started, 1),
    }


def captured_messages(trace: Path) -> list[dict]:
    """Extract outgoing user messages + serialized request messages from the trace."""
    events = []
    if not trace.is_file():
        return events
    for line in trace.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "message.final" and e.get("direction") == "outgoing":
            m = e.get("message", {})
            if m.get("role") == "user":
                texts = [c.get("text", "") for c in m.get("content", []) if c.get("type") == "text"]
                events.append({"source": "message.final", "text": "\n".join(texts)})
        elif e.get("type") == "llm.request":
            payload = e.get("payload") or e.get("request") or e
            msgs = None
            if isinstance(payload, dict):
                for key in ("messages", "input"):
                    if isinstance(payload.get(key), list):
                        msgs = payload[key]
                        break
            if msgs:
                for m in msgs:
                    role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
                    if role == "user":
                        content = m.get("content") if isinstance(m, dict) else m.content
                        if isinstance(content, list):
                            text = "\n".join(
                                (c.get("text", "") if isinstance(c, dict) else getattr(c, "text", ""))
                                for c in content
                            )
                        else:
                            text = str(content)
                        events.append({"source": "llm.request", "text": text})
    return events


def main() -> int:
    transport = sys.argv[1] if len(sys.argv) > 1 else "cmd-shim"
    case = next(c for c in CORPUS if c["id"] == "CASE-01")
    prompt = arm_b_prompt(case)

    print("=== intended multiline prompt (repr) ===")
    print(repr(prompt))
    print(f"sha256={sha256(prompt)} len={len(prompt)} newlines={prompt.count(chr(10))}")

    # Direct argv-boundary check: what does a child process actually see as argv?
    # Use python itself through the same cmd.exe path to isolate argv mangling.
    echo = subprocess.run(
        [sys.executable, "-c",
         "import sys,json; print(json.dumps(sys.argv[1:]))", prompt],
        capture_output=True, text=True, encoding="utf-8")
    direct_argv = json.loads(echo.stdout)
    print("=== direct python-subprocess argv check ===")
    print(f"argv[1] sha256={sha256(direct_argv[0])} intact={direct_argv[0] == prompt}")

    if TRACE.exists():
        TRACE.unlink()

    result = run_case(case, "arm-b-case01-multiline", prompt)
    print("=== little-coder delivery probe ===")
    print(f"exit={result['exit']} duration={result['duration_s']}s")
    print(f"stdout(repr)={result['stdout'][:500]!r}")

    time.sleep(1.0)
    trace_path = Path(result["trace_path"])
    captured = captured_messages(trace_path)
    result["captured"] = [
        {**c, "captured_sha256": sha256(c["text"]), "byte_identical": c["text"] == prompt,
         "text": c["text"]}
        for c in captured
    ]
    for c in result["captured"]:
        print(f"--- captured via {c['source']}: byte_identical={c['byte_identical']} "
              f"intended={c['intended_sha256'] if 'intended_sha256' in c else result['intended_sha256']} "
              f"captured={c['captured_sha256']}")
        if not c["byte_identical"]:
            print(f"captured(repr)={c['text'][:600]!r}")

    (OUT_DIR / f"arm-b-case01-multiline-{transport}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if trace_path.is_file():
        shutil.copy2(trace_path, OUT_DIR / f"arm-b-case01-multiline-{transport}-trace.ndjson")
    print(f"wrote {OUT_DIR / f'arm-b-case01-multiline-{transport}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
