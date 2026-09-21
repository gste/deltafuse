"""Local measured tokenizer for qualification campaigns (roadmap item 0.2).

Serves the reference model's own tokenizer over the llama-server-compatible
endpoint that `deltafuse.core.context.try_endpoint_token_count` already
speaks, so a campaign can set `DELTAFUSE_TOKENIZER_REQUIRED` and count the
framework-controlled input with a measured tokenizer instead of the heuristic.

    python scripts/tokenize_server.py --tokenizer <dir-or-tokenizer.json> [--port 8765]
    DELTAFUSE_TOKENIZE_URL=http://127.0.0.1:8765/tokenize

Endpoints:
    POST /tokenize  {"content": "..."}  ->  {"count": N}
    GET  /health                       ->  tokenizer identity (sha256, source, revision)

Judge-side tooling: it needs the `tokenizers` package, which is deliberately not
a framework dependency. It never runs a model and never calls chat completions
(Q-004) — it only splits text into ids and counts them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_BODY_BYTES = 64 * 1024 * 1024


def resolve_tokenizer_file(path: Path) -> Path:
    candidate = path / "tokenizer.json" if path.is_dir() else path
    if not candidate.is_file():
        raise SystemExit(f"tokenizer.json not found: {candidate}")
    return candidate


def tokenizer_identity(tokenizer_file: Path) -> dict[str, Any]:
    """What the campaign manifest records: which tokenizer produced the counts."""
    revision_file = tokenizer_file.parent / "REVISION"
    source_file = tokenizer_file.parent / "SOURCE"
    return {
        "tokenizer_sha256": hashlib.sha256(tokenizer_file.read_bytes()).hexdigest(),
        "source": source_file.read_text(encoding="utf-8").strip() if source_file.is_file() else None,
        "revision": revision_file.read_text(encoding="utf-8").strip() if revision_file.is_file() else None,
    }


def make_handler(tokenizer: Any, identity: dict[str, Any]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if self.path.rstrip("/") == "/health":
                self._send(200, {"ok": True, **identity})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/tokenize":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send(400, {"error": "missing or oversized body"})
                return
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                content = data["content"]
                if not isinstance(content, str):
                    raise TypeError("content must be a string")
            except (ValueError, KeyError, TypeError) as ex:
                self._send(400, {"error": f"bad request: {ex}"})
                return
            # Same default as llama-server /tokenize: no special tokens added.
            count = len(tokenizer.encode(content, add_special_tokens=False).ids)
            self._send(200, {"count": count})

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tokenizer", required=True, help="tokenizer.json or a directory holding it")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    try:
        from tokenizers import Tokenizer
    except ModuleNotFoundError:
        print("tokenize_server: install the `tokenizers` package (judge-side only)", file=sys.stderr)
        return 2

    tokenizer_file = resolve_tokenizer_file(Path(args.tokenizer))
    tokenizer = Tokenizer.from_file(str(tokenizer_file))
    identity = tokenizer_identity(tokenizer_file)
    identity["vocab_size"] = tokenizer.get_vocab_size()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(tokenizer, identity))
    print(
        f"tokenize_server: http://{args.host}:{args.port}/tokenize "
        f"source={identity['source']} sha256={identity['tokenizer_sha256'][:12]}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
