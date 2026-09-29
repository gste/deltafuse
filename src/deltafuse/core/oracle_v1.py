"""Check of `red_oracle_tests` records of format 1 (no `version` field).

Format 1 was written by 7149cad: per-test digests over the declared test
files only, declared support modules frozen whole, Java by bytes, no conftest
chain and no pytest configuration. A record is checked the way it was taken,
so this is that code, kept for the check alone; core/oracle.py writes and
checks format 2.
"""

from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deltafuse.core.hasher import compute_file_sha256

_DOC_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_OWN_SCOPE = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
# Names pytest acts on without the test naming them.
_IMPLICIT_NAMES = frozenset({"pytestmark", "pytest_plugins"})
ABSENT = "absent"
UNPARSEABLE = "unparseable"


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest().lower()


def _strip_doc(body: list[Any]) -> list[Any]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def canon(node: Any) -> str:
    """A position-free, docstring-free rendering of an AST.

    Written out rather than `ast.dump`, whose output changes shape between
    Python versions (3.13 stopped printing empty fields): empty fields are
    skipped here either way.
    """
    if isinstance(node, ast.AST):
        parts: list[str] = []
        for name in node._fields:
            value = getattr(node, name, None)
            if name == "body" and isinstance(node, _DOC_OWNERS):
                value = _strip_doc(value or [])
            if value is None or value == []:
                continue
            parts.append(f"{name}={canon(value)}")
        return f"{type(node).__name__}({','.join(parts)})"
    if isinstance(node, list):
        return "[" + ",".join(canon(v) for v in node) + "]"
    return repr(node)


def _decorator_name(dec: ast.expr) -> str:
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _fixture_calls(defn: ast.AST) -> Iterable[ast.Call]:
    for dec in getattr(defn, "decorator_list", []):
        if isinstance(dec, ast.Call) and _decorator_name(dec).endswith("fixture"):
            yield dec


def _fixture_aliases(defn: ast.AST) -> set[str]:
    """`@pytest.fixture(name="limiter")` is requested as `limiter`."""
    return {
        kw.value.value
        for call in _fixture_calls(defn)
        for kw in call.keywords
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
    }


def _is_autouse(defn: ast.AST) -> bool:
    for call in _fixture_calls(defn):
        for kw in call.keywords:
            if kw.arg == "autouse" and not (isinstance(kw.value, ast.Constant) and not kw.value.value):
                return True
    return False


def _binds(stmt: ast.AST) -> set[str]:
    """Names a statement binds in the scope it sits in."""
    out: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, _SCOPES):
            out.add(node.name)
            out.update(_fixture_aliases(node))
            return
        if isinstance(node, _OWN_SCOPE):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != "*":
                    out.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            out.add(node.rest)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(stmt)
    return out


def _refs(node: ast.AST) -> set[str]:
    """Names a statement may reach: identifiers, parameters (fixtures are
    requested by parameter name) and identifier-shaped strings
    (`usefixtures("db")`, `getfixturevalue("db")`)."""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.arg):
            out.add(sub.arg)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value.isidentifier():
            out.add(sub.value)
    return out


@dataclass(frozen=True)
class _Unit:
    names: frozenset[str]
    canon: str
    refs: frozenset[str]
    implicit: bool
    node: ast.AST | None


def _units(stmts: list[ast.stmt]) -> list[_Unit]:
    """One scope as units, each binding the names it binds.

    An import is split per name, so adding a name to an existing import line
    does not read as a change of the names already imported by it.
    """
    out: list[_Unit] = []
    for stmt in _strip_doc(stmts):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            module = getattr(stmt, "module", None) or ""
            level = getattr(stmt, "level", 0) or 0
            for alias in stmt.names:
                if alias.name == "*":
                    out.append(_Unit(frozenset(), canon(stmt), frozenset(), True, stmt))
                    continue
                bound = alias.asname or alias.name.split(".")[0]
                text = f"{type(stmt).__name__}({module!r},{level},{alias.name!r},{alias.asname!r})"
                out.append(_Unit(frozenset({bound}), text, frozenset(), False, stmt))
            continue
        names = frozenset(_binds(stmt))
        implicit = (
            not names
            or bool(names & _IMPLICIT_NAMES)
            or (isinstance(stmt, _DEFS) and (stmt.name.startswith("pytest_") or _is_autouse(stmt)))
        )
        out.append(_Unit(names, canon(stmt), frozenset(_refs(stmt)), implicit, stmt))
    return out


def _is_test_def(stmt: ast.AST) -> bool:
    return isinstance(stmt, _DEFS) and stmt.name.startswith("test")


def _locate(units: list[_Unit], path: list[str]) -> tuple[list[str], list[str], set[str]]:
    """(body, class context, names reached) of the test at `path` in a scope."""
    matches = [u for u in units if path[0] in u.names]
    body: list[str] = []
    context: list[str] = []
    refs: set[str] = set()
    if len(path) == 1:
        for unit in matches:
            body.append(unit.canon)
            refs |= unit.refs
        return body, context, refs
    for unit in matches:
        node = unit.node
        if isinstance(node, ast.ClassDef):
            b, c, r = _locate(_units(node.body), path[1:])
            body += b
            context += c
            refs |= r
            # The class around the test is context: its decorators, bases,
            # setup and attributes - not its other tests.
            shell = copy.copy(node)
            shell.body = [s for s in node.body if not _is_test_def(s)]
            context.append(canon(shell))
            refs |= _refs(shell)
        else:
            context.append(unit.canon)
            refs |= unit.refs
    return body, context, refs


def _parse(path: Path) -> ast.Module | str:
    if not path.is_file():
        return ABSENT
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return UNPARSEABLE


def _context_digest(modules: dict[str, list[_Unit]], class_context: list[str], seeds: set[str]) -> str:
    lines = {f"<class>\t{c}" for c in class_context}
    todo = set(seeds)
    for rel, units in modules.items():
        for unit in units:
            if unit.implicit:
                lines.add(f"{rel}\t{unit.canon}")
                todo |= unit.refs
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for rel, units in modules.items():
            for unit in units:
                if name in unit.names:
                    lines.add(f"{rel}\t{unit.canon}")
                    todo |= unit.refs - seen
    return _sha("\n".join(sorted(lines)) + "\n")


def _file_digest(root: Path, rel: str, form: str) -> str | None:
    path = root / rel
    if form == "ast":
        tree = _parse(path)
        if tree == ABSENT:
            return None
        if tree == UNPARSEABLE:
            return UNPARSEABLE
        return _sha(canon(tree))
    if not path.is_file():
        return None
    try:
        return "sha256:" + compute_file_sha256(path)
    except OSError:
        return None


def red_oracle_changes(repo_root: Path | str, recorded: dict[str, Any]) -> list[str]:
    """What moved in a frozen oracle since Red, one phrase each; empty when intact."""
    root = Path(repo_root)
    changes: list[str] = []
    for entry in recorded.get("files") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            changes.append("the frozen oracle record is malformed")
            continue
        rel, form = entry["path"], entry.get("form") or "bytes"
        now = _file_digest(root, rel, form)
        if now == entry.get("sha256"):
            continue
        if now is None:
            changes.append(f"{rel} was deleted")
        elif now == UNPARSEABLE:
            changes.append(f"{rel} no longer parses")
        elif entry.get("sha256") is None:
            changes.append(f"{rel} was absent at Red and exists now")
        elif form == "ast":
            changes.append(f"{rel} changed (a module with no tests of its own is frozen whole)")
        else:
            changes.append(f"{rel} changed (a file the Core cannot split into tests is frozen whole)")

    entries = [e for e in recorded.get("tests") or [] if isinstance(e, dict)]
    trees = {e.get("path"): _parse(root / str(e.get("path"))) for e in entries}
    modules = {rel: _units(t.body) for rel, t in trees.items() if isinstance(t, ast.Module)}
    reported: set[str] = set()
    for entry in entries:
        rel, test = str(entry.get("path")), str(entry.get("test"))
        tree = trees.get(rel)
        if not isinstance(tree, ast.Module):
            if rel not in reported:
                reported.add(rel)
                changes.append(f"{rel} was deleted" if tree == ABSENT else f"{rel} no longer parses")
            continue
        body, context, refs = _locate(modules[rel], test.split("::"))
        if not body:
            changes.append(f"{rel}::{test} was removed or renamed")
        elif _sha("\n".join(body)) != entry.get("body"):
            changes.append(f"{rel}::{test} changed (its body or decorators)")
        elif _context_digest(modules, context, refs) != entry.get("context"):
            changes.append(
                f"what {rel}::{test} relies on changed (a fixture, helper, import, its class, "
                "or module-level code in the declared test files)"
            )
    return changes
