# Command Line Interface for DeltaFuse Framework.

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

from deltafuse.core.installer import install, InstallationError
from deltafuse.core.fsm import validate_change_package, check_gate, find_repo_root
from deltafuse.core.archiver import archive_change, ArchivalError
from deltafuse.core.evidence import EvidenceRunError, run_evidence
from deltafuse.core.layout import validate_product_layout
from deltafuse.core.board import BoardError, build_board_snapshot
from deltafuse.core.analyze import CoverageError, claim_trace_warnings, write_coverage
from deltafuse.core.queue import (
    QueueError,
    build_work_queue,
    format_human_blocked_queue,
    format_human_guide,
    format_item,
    format_queue,
    intake_sources_pending,
    load_product_root,
    queue_snapshot,
    select_next,
)
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core import gate_password
from deltafuse.core.transitions import TransitionError, advance_change, gate_order_errors
from deltafuse.core.transitions import already_green_advice, set_artifact_status
from deltafuse.core.leash import LeashError, load_leash_mode
from deltafuse.core.leash_run import run_leash
from deltafuse.core.steps import step_names
from deltafuse.core.context import (
    token_count_receipt,
    tokenizer_config,
    validate_context_budget,
    validate_task_context_budget,
)
from deltafuse.core.frontmatter import parse_frontmatter


class _HintingParser(argparse.ArgumentParser):
    """argparse, plus a guess when a subcommand is not one.

    Workers call the host's tool name as a command (`deltafuse artifact_write`, 8 times in
    the runs of 2026-09-25/26) and got the list of every command back, which does not say
    which one they meant.
    """

    def error(self, message: str) -> NoReturn:
        import difflib

        # The "(choose from ...)" wording is argparse's own and has changed across Python
        # versions (3.10 through 3.14 are all in CI); the choice value itself ("invalid
        # choice: 'x'") has not. Read the valid choices from the subparsers action itself
        # instead of the formatted message, so a wording change cannot silently turn this
        # hint off again.
        wrong = re.search(r"invalid choice: '([^']+)'", message)
        if wrong:
            given = wrong.group(1)
            choices: list[str] = []
            for action in self._subparsers._group_actions if self._subparsers else []:
                if isinstance(action, argparse._SubParsersAction):
                    choices = list(action.choices)
                    break
            words = re.split(r"[_\s]+", given)
            guess = None
            if len(words) > 1 and words[0] in choices:
                guess = " ".join(words)  # artifact_write -> artifact write
            elif choices:
                near = difflib.get_close_matches(given, choices, n=1, cutoff=0.6)
                guess = near[0] if near else None
            if guess:
                message = f"Did you mean: deltafuse {guess} ...?  ({message})"
        super().error(message)


class _Capture:
    """Writes through to a stream and keeps a copy."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        self.parts.append(text)
        return self._stream.write(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def text(self) -> str:
        return "".join(self.parts)


def _journal(start: Path | str, **event: object) -> None:
    from deltafuse.bench.journal import record_event

    record_event(start, **event)


def _fail(start: Path, what: str, error: object, code: int, **event: object) -> int:
    """Journal a refused command, print `<what>: <error>` on stderr, return `code`."""
    event.setdefault("ok", False)  # a caller that places `ok` itself keeps its journal key order
    _journal(start, **event, errors=[str(error)])
    print(f"{what}: {error}", file=sys.stderr)
    return code


def _print_errors(header: str, errors: list[str]) -> None:
    print(header, file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)


def _report(cmd: str, target: Path, errors: list[str], failed: str, valid: str, **event: object) -> int:
    """Journal a validator's verdict; list the errors on stderr (exit 1) or print `valid` (exit 0)."""
    _journal(target, cmd=cmd, ok=not errors, errors=errors, n_errors=len(errors), **event)
    if errors:
        _print_errors(f"{failed} for {target} with {len(errors)} error(s):", errors)
        return 1
    print(valid)
    return 0


def _read_secret(prompt: str, hint: str = "") -> str:
    """Read a secret from the terminal; refuse when no human is at one."""
    import getpass

    if not sys.stdin.isatty():
        raise gate_password.GatePasswordError(
            "the Human Gate password is read only from an interactive terminal" + hint
        )
    return getpass.getpass(prompt)


def _gate_password_prompt(command: str = "") -> str:
    hint = f"; open one at the product root and run: {command}" if command else ""
    return _read_secret("Human Gate password: ", hint)


def _capability_command(args) -> int:
    """Propose a capability the catalog does not have yet, as a draft (q8).

    Routing refuses a name the catalog does not hold, and the catalog is
    writable only in Specify - after the `analyzed` gate. A Change that needs
    a new capability had no legal move in Analyze at all.
    """
    from deltafuse.core import capability

    try:
        root = load_product_root(Path(args.path).resolve())
    except QueueError as ex:
        print(f"capability: {ex}", file=sys.stderr)
        return 2
    try:
        written = capability.propose_capability(
            root,
            args.name,
            summary=args.summary,
            spec=args.spec,
            code_roots=args.code_root or [],
        )
    except capability.CapabilityError as ex:
        print(f"capability: {ex}", file=sys.stderr)
        return 1
    print(
        f"capability: {written['capability']} proposed as a draft in {written['path']}; "
        f"its spec is {written['spec']} (Specify writes it) and the human makes it "
        "active when accepting the specification"
    )
    return 0


def _gate_password_command(action: str, target: Path) -> int:
    try:
        root = load_product_root(target.resolve())
    except QueueError as ex:
        print(f"gate-password: {ex}", file=sys.stderr)
        return 2
    enabled = gate_password.is_enabled(root)
    if action == "status":
        print(f"gate-password: {'enabled' if enabled else 'disabled'}")
        return 0
    try:
        current = _read_secret("Current password: ") if enabled else None
        if action == "clear":
            gate_password.clear_password(root, current)
            print("gate-password: disabled")
            return 0
        new = _read_secret("New password: ")
        if new != _read_secret("Repeat new password: "):
            print("gate-password: the passwords differ; nothing changed", file=sys.stderr)
            return 1
        gate_password.set_password(root, new, current=current)
    except gate_password.GatePasswordError as ex:
        print(f"gate-password: {ex}", file=sys.stderr)
        return 1
    print(f"gate-password: enabled ({gate_password.PASSWORD_REL}; stores a salted hash only)")
    return 0

def _artifact_write_command(args: argparse.Namespace) -> int:
    """`deltafuse artifact write`: one command, the Core decides create or update."""
    from deltafuse.core.artifact_lock import ArtifactLockError
    from deltafuse.core.artifact_patch import ArtifactPatchError
    from deltafuse.core.artifact_policy import ArtifactPolicyError
    from deltafuse.core.artifact_reader import ArtifactReaderError, strict_parse_json
    from deltafuse.core.artifact_transactions import ArtifactTransactionError
    from deltafuse.core.artifact_write import split_envelope, write_artifact
    from deltafuse.core.artifacts import ArtifactServiceError

    max_bytes = 1024 * 1024

    def fail(code: str, message: str, ret: int) -> int:
        if args.json:
            print(json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False, indent=2))
        print(f"artifact write: {message}", file=sys.stderr)
        return ret

    try:
        if args.input == "-":
            raw_bytes = sys.stdin.buffer.read(max_bytes + 1) if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
        else:
            source = Path(args.input)
            if not source.is_file():
                return fail("file_not_found", f"input file not found: {args.input}", 2)
            raw_bytes = source.read_bytes()
        raw_json = strict_parse_json(raw_bytes, max_bytes=max_bytes)
        identity, target, fields, body = split_envelope(raw_json)
        receipt = write_artifact(
            Path(args.change),
            args.kind,
            identity=identity,
            target=target,
            fields=fields,
            body=body,
            request_id=raw_json.get("request_id") if isinstance(raw_json, dict) else None,
        )
    except ArtifactReaderError as ex:
        return fail(ex.code, f"input is not valid JSON: {ex.message}", 2)
    except (ArtifactPolicyError, ArtifactPatchError, ArtifactServiceError) as ex:
        code = getattr(ex, "code", "artifact_error")
        # A policy refusal is 3, a malformed request 2 - the split the retired `artifact create` made.
        denied = ("core_owned_field", "policy_denied", "missing_core_context", "missing_change_authority",
                  "unauthorized_stage", "stage_halted")
        ret = 3 if code in denied else 2
        message = str(ex) if str(ex).startswith("[") else f"[{code}] {ex}"
        return fail(code, message, ret)
    except (ArtifactLockError, ArtifactTransactionError) as ex:
        return fail(getattr(ex, "code", "lock_error"), str(ex), 5)
    if args.json:
        print(json.dumps({"ok": True, **receipt}, ensure_ascii=False, indent=2))
    else:
        print(f"artifact write: {receipt['operation']} {receipt.get('target')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Bound installation/registry failures at the public Artifact CLI boundary."""
    from deltafuse.core.artifact_registry import ArtifactRegistryError
    from deltafuse.core.assets import AssetError

    raw = list(sys.argv[1:] if argv is None else argv)
    writes = len(raw) > 1 and raw[0] == "artifact" and raw[1] == "write"
    out, err = sys.stdout, sys.stderr
    cap_out = cap_err = None
    if writes:
        cap_out, cap_err = _Capture(out), _Capture(err)
        sys.stdout, sys.stderr = cap_out, cap_err
    code: int | None = None
    try:
        try:
            code = _main(raw)
        except SystemExit as ex:
            code = ex.code if isinstance(ex.code, int) else 2
            raise
        except (ArtifactRegistryError, AssetError) as ex:
            if not raw or raw[0] != "artifact":
                raise
            message = str(ex)[:512]
            if "--json" in raw:
                print(json.dumps({"ok": False, "error": {
                    "code": "asset_resolution_failed", "stage": "schema",
                    "path": "/", "message": message,
                    "hint": "Reinstall a verified framework bundle; in a source checkout run scripts/sync_assets.py.",
                }}, ensure_ascii=False, indent=2))
            print(f"Artifact assets unavailable: {message}", file=sys.stderr)
            code = 5
        return code
    finally:
        if writes and cap_out is not None and cap_err is not None:
            sys.stdout, sys.stderr = out, err
            _journal_artifact_write(raw, 1 if code is None else code, cap_out.text(), cap_err.text())


def _flag(raw: list[str], *names: str) -> str | None:
    for i, item in enumerate(raw):
        if item in names and i + 1 < len(raw):
            return raw[i + 1]
        for name in names:
            if item.startswith(name + "="):
                return item.split("=", 1)[1]
    return None


def _journal_artifact_write(raw: list[str], code: int, out: str, err: str) -> None:
    """One journal line per Artifact Writer call: what, and why it was refused.

    `artifact write` left no trace in the command journal, so a Worker that fought the
    Writer for 20 calls and one that never touched it looked the same to every metric.
    """

    errors: list[str] = []
    if code != 0:
        text = err.strip() or out.strip()
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("usage:"):
                errors.append(line[:400])
        errors = errors[:5] or [f"exit {code}"]
        found = re.search(r"\[(\w+)\]", " ".join(errors))
    else:
        found = None
    change = _flag(raw, "--change", "-c") or "."
    _journal(
        Path(change),
        cmd="artifact",
        sub=raw[1],
        kind=_flag(raw, "--kind", "-k"),
        identity=_flag(raw, "--identity"),
        ok=code == 0,
        refusal=found.group(1) if found else None,
        errors=errors or None,
    )


def _main(argv: list[str] | None = None) -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = _HintingParser(prog="deltafuse", description="DeltaFuse Specification-Driven AI Engineering Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    raw = list(sys.argv[1:] if argv is None else argv)
    evidence_argv: list[str] = []
    if raw and raw[0] == "evidence" and "--" in raw:
        cut = raw.index("--")
        evidence_argv = raw[cut + 1 :]
        raw = raw[:cut]

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize DeltaFuse product layout")
    init_parser.add_argument("target", nargs="?", default=".", help="Target product directory (default: current dir)")
    init_parser.add_argument("--force", "-f", action="store_true", help="Force upgrade/overwrite existing lock")
    init_parser.add_argument("--agents-md", choices=["prompt", "bridge", "preserve", "replace"], default=None,
                             help="Host instruction integration: prompt (TTY), bridge, preserve, or replace")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate Change package structural invariants")
    val_parser.add_argument("change_path", nargs="?", default=".", help="Path to Change package directory")

    # check-gate command
    gate_parser = subparsers.add_parser("check-gate", help="Check lifecycle gate preconditions")
    gate_parser.add_argument("change_path", help="Path to Change package directory")
    gate_parser.add_argument("--gate", "-g", required=True, help="Target gate (intake, analyzed, specified, decomposed, declaring, implemented, converged)")

    # archive command
    arch_parser = subparsers.add_parser("archive", help="Archive a converged Change package")
    arch_parser.add_argument("change_path", help="Path to Change package directory")
    arch_parser.add_argument("--force", "-f", action="store_true", help="Accepted for compatibility; archive always requires status 'converged' (or a terminal status) and never skips the gate")

    # advance command (DF3-004): Core-owned gate validation + transition
    advance_parser = subparsers.add_parser(
        "advance", help="Apply a gate transition: Core validates, writes status, records a receipt"
    )
    advance_parser.add_argument("change_path", help="Path to Change package directory")
    advance_parser.add_argument(
        "--gate", "-g", required=True,
        help="Gate to apply (intake, analyzed, specified, decomposed, declaring, implemented, converged)",
    )
    advance_parser.add_argument("--json", action="store_true", help="Write JSON result to stdout")

    # V3-FIX-010: Core-owned artifact status writes
    state_parser = subparsers.add_parser(
        "state", help="Set a Core-owned task/slice/Change in-flight status (never hand-edit status)"
    )
    state_parser.add_argument("change_path", help="Path to Change package directory")
    group = state_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Task id like TASK-001")
    group.add_argument("--slice", dest="slice_id", help="Slice id like SLICE-01")
    group.add_argument("--change", action="store_true", help="Target the Change itself (in-flight status)")
    state_parser.add_argument("--status", required=True, help="New status")
    state_parser.add_argument("--json", action="store_true", help="Write JSON result to stdout")

    # new command (DF3-005 / C-03): deterministic Change scaffolding
    new_parser = subparsers.add_parser("new", help="Scaffold a minimal Change package (does not close Intake)")
    new_parser.add_argument("product_path", nargs="?", default=".", help="Product root (default: current dir)")
    new_parser.add_argument("change_id", help="Change id like CHG-101 or CHG-101-auth")
    new_parser.add_argument("--route", default="code", choices=["code", "docs", "ops"], help="Change route")
    new_parser.add_argument("--title", default="", help="Short Change title")
    new_parser.add_argument("--json", action="store_true", help="Write JSON to stdout")

    layout_parser = subparsers.add_parser("validate-layout", help="Validate product repository layout, locks, and adapters")
    layout_parser.add_argument("product_path", nargs="?", default=".", help="Path to product repository root (default: current dir)")

    # evidence command (WK-002)
    ev_parser = subparsers.add_parser(
        "evidence", help="Run a command after '--' and write evidence/red|green|regression YAML"
    )
    ev_parser.add_argument("change_path", help="Path to Change package directory")
    ev_parser.add_argument(
        "--phase", "-p", required=True, choices=["red", "green", "regression", "verification"],
        help="Evidence phase to record",
    )
    ev_parser.add_argument("--task", "-t", default=None, help="Task id (TASK-NNN); required for red/green/regression, forbidden for verification")
    ev_parser.add_argument("--changed-path", action="append", default=[], dest="changed_paths",
                           help="Relative path written by the Worker (repeatable)")
    ev_parser.add_argument("--timeout", type=int, default=90, help="Command timeout in seconds")

    cov_parser = subparsers.add_parser("coverage",
                                       help="Write coverage.yaml from routing and slices (no LLM)")
    cov_parser.add_argument("change_path", help="Path to Change package directory")

    # next / work queue (WK-003)
    next_parser = subparsers.add_parser("next", help="Select the next ready lifecycle step (no LLM)")
    next_parser.add_argument("path", nargs="?", default=".",
                             help="Product root or Change package directory (default: current dir)")
    next_parser.add_argument("--list", action="store_true", help="Print the full ready/blocked queue")
    next_parser.add_argument("--json", action="store_true", help="Write a JSON snapshot to stdout")
    next_parser.add_argument(
        "--human", action="store_true",
        help="Print a checklist from the step contract (same files, not a second process)",
    )
    next_parser.add_argument("--step", choices=list(step_names()), help="Only select this step")

    decide_parser = subparsers.add_parser(
        "decide", help="Apply a Human Gate choice after the human answers (no LLM, no auto-accept)"
    )
    decide_parser.add_argument("path", nargs="?", default=".",
                               help="Product root, or Change directory for --spec")
    decide_parser.add_argument("--decision", "-d", default=None, help="DEC id or docs/decisions/*.md path")
    decide_parser.add_argument("--spec", action="store_true",
                               help="Apply the specification Human Gate (spec-delta.md on the Change path)")
    decide_parser.add_argument(
        "--task", default=None,
        help="Answer this blocked task of the Change on the path (--status cancelled or reopened)",
    )
    decide_parser.add_argument(
        "--status", required=True, choices=["accepted", "rejected", "cancelled", "reopened"],
        help="Recorded human choice (cancelled, reopened: only with --task)",
    )
    decide_parser.add_argument(
        "--gap", default=None,
        help="With --status reopened: send the Change whose Verify recorded this gap back (spec-gap -> Analyze)",
    )
    decide_parser.add_argument(
        "--note", default=None, help="With --status reopened: what the human passes on to the next Declare"
    )
    decide_parser.add_argument("--json", action="store_true", help="Write JSON to stdout")

    # Human Gate password: interactive only, never a flag or an environment
    # variable - anything a Worker's shell can pass, a Worker can pass.
    gpw_parser = subparsers.add_parser(
        "gate-password", help="Set, clear or show the optional Human Gate password (interactive only)"
    )
    gpw_parser.add_argument("action", choices=["set", "clear", "status"])
    gpw_parser.add_argument("path", nargs="?", default=".", help="Product root")

    cap_parser = subparsers.add_parser(
        "capability", help="Propose a capability the catalog does not have yet (draft, Analyze)"
    )
    cap_sub = cap_parser.add_subparsers(dest="capability_command", required=True)
    cap_propose = cap_sub.add_parser("propose", help="Add <domain>.<capability> to the catalog as a draft")
    cap_propose.add_argument("name", help="<domain>.<capability>, e.g. monitoring.usage_stats")
    cap_propose.add_argument("--summary", required=True, help="One line: what it is responsible for")
    cap_propose.add_argument("--spec", required=True, help="Spec file Specify will write, under docs/spec/")
    cap_propose.add_argument("--code-root", action="append", default=[],
                             help="Code root it will own (repeatable)")
    cap_propose.add_argument("--path", default=".", help="Product root")

    # board snapshot (FM-001)
    board_parser = subparsers.add_parser("board",
                                         help="Emit a read-only fuse-map board snapshot (no product writes)")
    board_parser.add_argument("product_path", nargs="?", default=".",
                              help="Product repository root (default: current dir)")
    board_parser.add_argument(
        "--json", action="store_true", default=True,
        help="Write the snapshot JSON to stdout (default; the only stdout on success)",
    )
    board_parser.add_argument("--archive", action="store_true", help="Include archived Change cards")

    # validate-config (DF3-009 item 5): one validator for config contracts
    cfg_parser = subparsers.add_parser("validate-config",
                                       help="Validate .deltafuse/config.yaml as one contract")
    cfg_parser.add_argument("product_path", nargs="?", default=".")
    cfg_parser.add_argument("--json", action="store_true")

    ctx_parser = subparsers.add_parser("lint-context", help="Lint Change package context budget and contracts")
    ctx_parser.add_argument("change_path", nargs="?", default=".", help="Path to Change package directory")

    leash_parser = subparsers.add_parser("leash",
                                         help="Check git diff against the current write envelope (no LLM)")
    leash_parser.add_argument("path", nargs="?", default=".", help="Product root (default: current dir)")
    leash_parser.add_argument("--json", action="store_true", help="Write JSON to stdout")
    leash_parser.add_argument(
        "--base", default=None,
        help="Exact base SHA: diff the committed range base..head instead of the local worktree (DF3-003)",
    )
    leash_parser.add_argument("--head", default=None, help="Exact head SHA (default: HEAD); requires --base")
    leash_parser.add_argument("--file", action="append", default=[], dest="files",
                              help="Relative path to check instead of git diff (repeatable)")

    bench_parser = subparsers.add_parser(
        "bench", help="Agent-agnostic Worker bench: init a case, score the disk, compare runs (no LLM)"
    )
    bench_sub = bench_parser.add_subparsers(dest="bench_cmd", required=True)
    bench_init = bench_sub.add_parser("init", help="Install a product workspace for a bench case")
    bench_init.add_argument("case_id", help="Case id (M01-cooldown floor, M02-policy-stats frontier)")
    bench_init.add_argument("product_dir", help="New worker sandbox (must be empty unless --force)")
    bench_init.add_argument("--force", "-f", action="store_true",
                            help="Recreate the sandbox if the directory already exists")
    bench_init.add_argument(
        "--pack", default=None,
        help="Judge pack (framework root, process/bench, or cases/). Default: this checkout",
    )
    # `score` and `compare` live in deltafuse-bench since 3.3.0: the judge is
    # versioned apart from the framework it measures (roadmap: one harness in
    # deltafuse-bench). The framework keeps only what a product produces.
    bench_journal = bench_sub.add_parser("journal",
                                         help="Judge: collect Core attempts from a sandbox journal (no LLM)")
    bench_journal.add_argument("product_dir", help="Product root created by bench init")

    # artifact command (AW-11)
    art_parser = subparsers.add_parser("artifact", help="Typed Artifact Writer CLI operations (AW-11)")
    art_sub = art_parser.add_subparsers(dest="artifact_cmd", required=True)
    art_write = art_sub.add_parser(
        "write", help="Create or update a Change artifact: fields plus a prose body (the Worker's path)"
    )
    art_write.add_argument("--kind", "-k", required=True, help="task | slice | routing | spec-delta | change")
    art_write.add_argument("--change", "-c", required=True, help="Change directory")
    art_write.add_argument(
        "--input", "-i", required=True,
        help='JSON file (or - for stdin): {"identity" | "target", "fields": {...}, "body": "..."}',
    )
    art_write.add_argument("--json", action="store_true", help="Output the Writer receipt as JSON")

    args = parser.parse_args(raw)

    if args.command == "init":
        try:
            result = install(target_dir=args.target, force=args.force, agents_md=args.agents_md)
            print(f"DeltaFuse {result.version} successfully installed into {result.target_dir}")
            print(f"Content hash: sha256:{result.content_hash}")
            target = str(result.agents_md_target) if result.agents_md_target else "none"
            print(f"agents_md_mode: {result.agents_md_mode}; effective target: {target}")
            if result.agents_md_mode == "preserve":
                print("Host instruction files were preserved; activate DeltaFuse explicitly with /run or deltafuse next --json.")
            if result.adapter_mode == "link":
                print("Adapter skills are relative links into the nested framework checkout.")
            return 0
        except InstallationError as e:
            print(f"Installation Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error during installation: {e}", file=sys.stderr)
            return 2

    elif args.command == "validate":
        target = Path(args.change_path)
        errors = validate_change_package(target)
        return _report("validate", target, errors, "Validation failed", f"Change package {target} is valid.")

    elif args.command == "check-gate":
        target = Path(args.change_path)
        # A gate whose turn has not come must not read as "passed": advance
        # would refuse it a moment later.
        errors = gate_order_errors(target, args.gate) + check_gate(target, args.gate)
        # P12 (workflow.trace_claims: warn, default off): advisory only - never in
        # `errors`, never affects the exit code. `off` costs nothing here (empty list).
        warnings = claim_trace_warnings(target) if args.gate == "converged" else []
        # Q0-2: a gate verdict that rests on a token budget must say how that
        # budget was counted; the configuration is what the campaign pins.
        tokenizer = tokenizer_config()
        _journal(
            target,
            cmd="check-gate",
            gate=args.gate,
            ok=not errors,
            errors=errors,
            n_errors=len(errors),
            **({"warnings": warnings} if warnings else {}),
            token_endpoint=tokenizer["endpoint"],
            token_required=tokenizer["required"],
            token_heuristic=tokenizer["heuristic"],
        )
        if errors:
            _print_errors(f"Gate {args.gate} check failed for {target}:", errors)
            return 1
        for warning in warnings:
            print(f"Gate {args.gate} (advisory): {warning}", file=sys.stderr)
        print(f"Gate {args.gate} passed for {target}.")
        return 0

    elif args.command == "archive":
        target = Path(args.change_path)
        try:
            dest = archive_change(target, force=args.force)
            _journal(target, cmd="archive", ok=True)
            print(f"Change package {target.name} successfully archived to {dest}")
            return 0
        except ArchivalError as ae:
            return _fail(target, "Archival failed", ae, 1, cmd="archive")
        except Exception as ex:
            return _fail(target, "Unexpected error during archival", ex, 2, cmd="archive")

    elif args.command == "advance":
        target = Path(args.change_path)
        try:
            result = advance_change(target, args.gate)
        except TransitionError as te:
            return _fail(target, "advance failed", te, 1, cmd="advance", gate=args.gate)
        receipt = dict(result)
        receipt.pop("ok", None)
        # P12: `advance --gate converged` is the one call a Worker makes now, so the
        # advisory claim-to-test findings that `check-gate` printed are printed here.
        warnings = claim_trace_warnings(target) if args.gate == "converged" else []
        if warnings:
            receipt["warnings"] = warnings
        _journal(target, cmd="advance", ok=True, errors=[], n_errors=0, **receipt)
        for warning in warnings:
            print(f"Gate {args.gate} (advisory): {warning}", file=sys.stderr)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for finding in (result.get("leash") or {}).get("violations") or []:
                print(f"advance: leash ({result['leash']['mode']}): {finding}", file=sys.stderr)
            if (result.get("leash") or {}).get("checked") is False:
                print(f"advance: leash not checked: {result['leash']['reason']}", file=sys.stderr)
            print(f"advance: gate '{result['gate']}' applied: {result['from']} -> {result['to']} "
                  f"(receipt {result['receipt'][:12]})")
        return 0

    elif args.command == "state":
        target = Path(args.change_path)
        try:
            result = set_artifact_status(
                target, status=args.status, task_id=args.task, slice_id=args.slice_id,
                change_status=args.change,
            )
        except TransitionError as te:
            return _fail(target, "state failed", te, 1, cmd="state", status=args.status)
        _journal(target, cmd="state", status=args.status, ok=True, errors=[], n_errors=0)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result.get("unchanged"):
            print(f"state: {result['artifact']} status is already {result['to']} (nothing written)")
        else:
            print(f"state: {result['artifact']} status {result['from']} -> {result['to']} "
                  f"(receipt {result['receipt'][:12]})")
        return 0

    elif args.command == "new":
        from deltafuse.core.scaffold import ScaffoldError, scaffold_change

        try:
            change_dir = scaffold_change(
                Path(args.product_path), args.change_id, route=args.route, title=args.title
            )
        except ScaffoldError as se:
            print(f"new failed: {se}", file=sys.stderr)
            return 1
        payload = {"ok": True, "change": args.change_id, "path": str(change_dir), "route": args.route}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"new: scaffolded {args.change_id} at {change_dir} (Intake stays open)")
        return 0

    elif args.command == "validate-layout":
        target = Path(args.product_path)
        errors = validate_product_layout(target)
        valid = f"DeltaFuse product layout at {target} is valid."
        return _report("validate-layout", target, errors, "Product layout validation failed", valid)

    elif args.command == "evidence":
        target = Path(args.change_path)
        try:
            outcome = run_evidence(
                target, phase=args.phase, task=args.task, argv=evidence_argv,
                changed_paths=args.changed_paths, timeout=args.timeout,
            )
        except EvidenceRunError as ex:
            return _fail(target, "Evidence run failed", ex, 2, cmd="evidence", phase=args.phase,
                         task=args.task)
        errors = list(outcome.errors or [])
        _journal(target, cmd="evidence", phase=args.phase, task=args.task, ok=bool(outcome.authentic),
                 errors=errors, n_errors=len(errors))
        print(f"Wrote {outcome.dest}")
        if outcome.authentic:
            print("Evidence is authentic.")
            if (
                args.phase == "red"
                and outcome.payload.get("result") == "already-green"
            ):
                # The record is an honest observation, but it is a stop, not a
                # green light: there is no failure for Implement to remove, and
                # the implemented gate refuses an already-green Red. "Return it
                # upstream" named no command, and the Worker declared the task seven
                # times over (cls-g31g-m02b, 2026-10-04): say what closes it.
                print(already_green_advice(args.change_path, str(args.task)), file=sys.stderr)
            return 0
        _print_errors("Evidence is not authentic:", outcome.errors)
        return 1

    elif args.command == "coverage":
        target = Path(args.change_path)
        try:
            dest = write_coverage(target)
        except Exception as ex:
            code = 1 if isinstance(ex, CoverageError) else 2
            return _fail(target, "Coverage failed", ex, code, cmd="coverage")
        _journal(target, cmd="coverage", ok=True)
        print(f"Wrote {dest}")
        return 0

    elif args.command == "next":
        target = Path(args.path)
        mode = "list" if args.list else "json" if args.json else "human" if args.human else "select"
        try:
            only = target.resolve() if (target.resolve() / "change.yaml").is_file() else None
            queue = build_work_queue(target, only_change=only)
        except QueueError as ex:
            return _fail(target, "Next failed", ex, 2, cmd="next", ok=False, mode=mode)
        selected = select_next(queue, step=args.step)
        had_item = selected is not None
        if (
            args.step is None
            and selected is not None
            and selected.step == "intake"
            and not (
                selected.intake_pending
                if selected.intake_pending is not None
                else intake_sources_pending(load_product_root(target))
            )
        ):
            # ref-m03-347 (2026-10-07): after the archive, `next` named a ready intake step
            # (intake_pending false) next to a "done" halt; the verify skill says to execute a
            # ready step, and the reference opened CHG-002 from the request CHG-001 had just
            # delivered. With no intake waiting there is no ready step to name.
            selected = None
        scope = target if only is None else only
        _journal(
            scope,
            cmd="next",
            ok=True if mode in {"list", "json"} else selected is not None,
            mode=mode,
            skill=selected.skill if selected is not None else None,
            step=selected.step if selected is not None else None,
            change=selected.change_id if selected is not None else None,
            empty=selected is None,
        )
        guide = (
            format_human_guide(selected, load_product_root(scope))
            if selected is not None
            else format_human_blocked_queue(queue)
        )
        if args.json:
            payload = queue_snapshot(queue, selected=selected, product_root=load_product_root(scope))
            if args.human:
                payload["guide"] = guide
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.human:
            if selected is not None:
                print(guide)
            else:
                print(guide, file=sys.stderr)
        elif args.list:
            print(format_queue(queue))
        elif selected is not None:
            print(format_item(selected))
        else:
            print("No ready work.", file=sys.stderr)
            print(format_queue(queue), file=sys.stderr)
            print("To start a new Change: /intake", file=sys.stderr)
        return 0 if had_item else 1

    elif args.command == "decide":
        target = Path(args.path)
        which = (f"--decision {args.decision}" if args.decision else f"--task {args.task}" if args.task
                 else f"--gap {args.gap}" if args.gap else "--spec")
        try:
            result = apply_decision(
                target, status=args.status, decision=args.decision, spec=args.spec, task=args.task,
                gap=args.gap, note=args.note,
                password_prompt=lambda: _gate_password_prompt(
                    f"deltafuse decide {args.path} {which} --status {args.status}"
                ),
            )
        except (DecideError, QueueError) as ex:
            return _fail(target, "Decide failed", ex, 1 if isinstance(ex, DecideError) else 2, cmd="decide")
        _journal(
            target,
            cmd="decide",
            ok=bool(result.get("ok")),
            gate=result.get("gate"),
            status=result.get("status"),
            decision=result.get("decision"),
            errors=list(result.get("gate_errors") or []) if not result.get("ok") else [],
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"decide: {result.get('gate')} {result.get('status')}")
            if result.get("decision"):
                print(f"decision: {result['decision']}")
            if result.get("change_status"):
                print(f"change_status: {result['change_status']}")
            for rel in result.get("written") or []:
                print(f"wrote: {rel}")
            for err in result.get("gate_errors") or []:
                print(f"gate: {err}", file=sys.stderr)
        return 0 if result.get("ok") else 1

    elif args.command == "capability":
        return _capability_command(args)

    elif args.command == "gate-password":
        return _gate_password_command(args.action, Path(args.path))

    elif args.command == "leash":
        if args.head and not args.base:
            print("leash: --head requires --base", file=sys.stderr)
            return 1
        target = Path(args.path)
        try:
            payload = run_leash(target, base=args.base, head=args.head, files=args.files)
            root = load_product_root(target.resolve() if (target.resolve() / "change.yaml").is_file() else target)
            errors = payload["violations"]
            mode = payload["mode"]
            skipped = payload["skipped"]
            _journal(root, cmd="leash", ok=payload["ok"], errors=errors, n_errors=len(errors),
                     skipped=skipped)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            elif skipped:
                print("leash: no write envelope (no ready Worker step)")
            elif errors:
                _print_errors(f"leash: {len(errors)} path(s) outside the write envelope", errors)
            else:
                print("leash: diff is inside the write envelope")
            if errors and mode != "advisory":
                return 1
            return 0
        except (QueueError, LeashError) as ex:
            _journal(target, cmd="leash", ok=False, errors=[str(ex)])
            print(f"Leash failed: {ex}", file=sys.stderr)
            # Advisory never stands in the way: the pre-commit hook it installs runs on
            # the very first commit of a fresh product, where there is no HEAD to diff.
            try:
                advisory = load_leash_mode(load_product_root(target.resolve())) == "advisory"
            except Exception:
                advisory = False
            return 0 if advisory else 2

    elif args.command == "board":
        target = Path(args.product_path)
        try:
            snapshot = build_board_snapshot(target, include_archive=args.archive)
        except BoardError as ex:
            return _fail(target, "Board failed", ex, 2, cmd="board")
        _journal(target, cmd="board", ok=True)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    elif args.command == "validate-config":
        from deltafuse.core.config import validate_config

        errors = validate_config(Path(args.product_path))
        _journal(Path(args.product_path), cmd="validate-config", ok=not errors, errors=errors, n_errors=len(errors))
        if args.json:
            print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        elif errors:
            for e in errors:
                print(f"config: {e}", file=sys.stderr)
            return 1
        print("config: .deltafuse/config.yaml is a valid v3 contract")
        return 0

    elif args.command == "lint-context":
        target = Path(args.change_path)
        repo_root = find_repo_root(target)
        slices_dir = target / "slices"
        errors: list[str] = []
        # Q0-2: the counting mode travels with the verdict into the journal.
        token_receipt: dict[str, Any] = {}
        if slices_dir.is_dir():
            for sf in slices_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(sf.read_text(encoding="utf-8"))
                    budget = meta.get("context_budget")
                    if budget and isinstance(budget, dict):
                        ref_files = [repo_root / sref.split("#")[0] for sref in meta.get("spec_refs", [])]
                        b_errs = validate_context_budget(
                            budget, ref_files, repo_root=repo_root, receipt=token_receipt
                        )
                        errors.extend(f"{sf.name}: {e}" for e in b_errs)
                except Exception as ex:
                    errors.append(f"{sf.name}: {ex}")
        tasks_dir = target / "tasks"
        if tasks_dir.is_dir():
            for tf in tasks_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(tf.read_text(encoding="utf-8"))
                    budget = meta.get("context_budget")
                    if budget and isinstance(budget, dict):
                        b_errs = validate_task_context_budget(
                            budget, meta.get("spec_refs") or [], meta.get("allowed_paths") or [], repo_root,
                            receipt=token_receipt,
                        )
                        errors.extend(f"{tf.name}: {e}" for e in b_errs)
                    else:
                        errors.append(
                            f"{tf.name}: context_budget is required "
                            "(max_tokens/max_files) for Declare and Implement"
                        )
                except Exception as ex:
                    errors.append(f"{tf.name}: {ex}")
        if not token_receipt:
            token_receipt = token_count_receipt()
        return _report(
            "lint-context",
            target,
            errors,
            "Context budget validation failed",
            f"Context budget for {target} is within limits (tokens counted by {token_receipt.get('mode')}).",
            token_mode=token_receipt.get("mode"),
            token_measured=token_receipt.get("measured"),
            token_heuristic=token_receipt.get("heuristic"),
        )

    elif args.command == "bench":
        from deltafuse.bench.init_product import format_worker_start_prompt, init_bench_product

        try:
            if args.bench_cmd == "init":
                meta = init_bench_product(
                    args.case_id, args.product_dir, pack_root=args.pack, force=args.force
                )
                product = Path(args.product_dir).resolve()
                print(f"Bench {meta['case']} ready in {product}")
                print("Open that directory as the Worker workspace, then paste:")
                print()
                print("----- paste into the Worker -----")
                print(format_worker_start_prompt(meta))
                print("----- end -----")
                return 0
            if args.bench_cmd == "journal":
                from deltafuse.bench.journal import collect_attempts, load_events

                payload = collect_attempts(load_events(Path(args.product_dir).resolve()))
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            print(
                "Scoring moved to the judge: `deltafuse-bench score <product-dir> --pack <pack>`",
                file=sys.stderr,
            )
            return 2
        except Exception as ex:  # BenchError included: same text, same code
            print(f"Bench failed: {ex}", file=sys.stderr)
            return 2

    elif args.command == "artifact":
        return _artifact_write_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
