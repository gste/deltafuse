"""The Red oracle, frozen per failed test (evidence field `red_oracle_tests`).

3.3.5 froze the bytes of every test file Red declared (`red_oracle`). That caught
a weakened assertion, but it also refused every honest edit of the same file: the
regression test Implement is allowed to add, the second task's Red written into
the file after the first one was taken, a reformat. The unit that has to stay
fixed is not the file but the test Red saw fail, so that is what is frozen now.

For a Python test file the Core takes the tests named in the Red record's
`tests.failed` and records, for each, two digests over a normalised AST (no
positions, no comments, no docstrings, so whitespace and comments do not count):

- `body`: every statement of its scope that binds the test's name - the
  function with its decorators (`skip`, `xfail`, `parametrize` included), and a
  later redefinition of the same name too, since the last one is what runs.
- `context`: what the test reaches inside the declared test files - the class
  around a method (decorators, bases, setup, attributes; not its other tests),
  every top-level definition, assignment or imported name its body refers to,
  followed transitively (fixtures are reached through the test's parameters),
  and in every declared test module the statements that act without being
  named: `pytestmark`, `pytest_plugins`, `pytest_*` hooks, autouse fixtures,
  and module-level code that binds no name.

Everything else in the file is free: new tests, unrelated helpers, new imports.

What cannot be split into tests is frozen whole, as before: a non-Python file
(Java under `src/test/**`, test data) or a Python file that did not parse as
raw bytes; a declared Python module with no tests of its own (`conftest.py`, a
helper module) as its normalised AST, since any fixture in it may be one the
oracle uses. A declared test module in which Red named no failed test has all
of its tests frozen one by one: the Core cannot tell which of them is the oracle.
"""

from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deltafuse.core.hasher import compute_file_sha256, oracle_paths

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


def _all_tests(units: list[_Unit]) -> list[list[str]]:
    out: list[list[str]] = []
    for unit in units:
        node = unit.node
        if _is_test_def(node):
            out.append([node.name])
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            out.extend([node.name, s.name] for s in node.body if _is_test_def(s))
    return out


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


def _resolve(test_id: str, modules: list[str]) -> list[tuple[str, list[str], bool]]:
    """Which declared module a runner's test id names, and the path inside it.

    pytest's JUnit id is `dotted.module.Class::name[params]`, the dotted part
    relative to pytest's rootdir, which need not be the product root - so the
    longest trailing match of a module's path wins. The flag says whether the
    match was unique.
    """
    classname, _, name = test_id.rpartition("::")
    name = name.split("[", 1)[0]
    cparts = classname.split(".") if classname else []
    best: list[tuple[str, list[str]]] = []
    best_len = 0
    for rel in modules:
        mparts = rel[:-3].split("/")
        for k in range(len(mparts), 0, -1):
            if cparts[:k] == mparts[-k:]:
                if k > best_len:
                    best, best_len = [(rel, cparts[k:] + [name])], k
                elif k == best_len:
                    best.append((rel, cparts[k:] + [name]))
                break
    return [(rel, path, len(best) == 1) for rel, path in best]


def _locate_all(
    units: list[_Unit], wanted: list[tuple[list[str], bool]]
) -> tuple[list[tuple[str, list[str], list[str], set[str]]], bool]:
    """The wanted tests found in a module, and whether it must be frozen whole."""
    found: list[tuple[str, list[str], list[str], set[str]]] = []
    seen: set[str] = set()
    for path, unique in wanted:
        key = "::".join(path)
        if key in seen:
            continue  # parametrized cases of one test
        seen.add(key)
        body, context, refs = _locate(units, path)
        if body:
            found.append((key, body, context, refs))
        elif unique:
            # Red says this test failed and it is not a plain definition here
            # (generated, or bound in a way the Core does not follow): the
            # module cannot be split, so it is frozen whole.
            return found, True
    return found, False


def freeze_red_oracle(
    repo_root: Path | str, changed_paths: Iterable[str], failed: Iterable[str]
) -> dict[str, Any] | None:
    """The `red_oracle_tests` a Red record carries. None when Red declared no test file."""
    root = Path(repo_root)
    paths = oracle_paths(changed_paths)
    if not paths:
        return None
    trees = {rel: _parse(root / rel) for rel in paths if rel.endswith(".py")}
    parsed = [rel for rel, tree in trees.items() if isinstance(tree, ast.Module)]
    named: dict[str, list[tuple[list[str], bool]]] = {}
    for test_id in failed:
        for rel, path, unique in _resolve(str(test_id), parsed):
            named.setdefault(rel, []).append((path, unique))

    files: list[dict[str, Any]] = []
    located: dict[str, list[tuple[str, list[str], list[str], set[str]]]] = {}
    modules: dict[str, list[_Unit]] = {}
    for rel in paths:
        tree = trees.get(rel)
        if not isinstance(tree, ast.Module):
            files.append({"path": rel, "form": "bytes", "sha256": _file_digest(root, rel, "bytes")})
            continue
        units = _units(tree.body)
        found, whole = _locate_all(units, named.get(rel) or [])
        if not found and not whole:
            # Red named no failed test here that the Core could find: it cannot
            # tell which of this module's tests is the oracle, so all are.
            found, whole = _locate_all(units, [(p, True) for p in _all_tests(units)])
        if whole or not found:
            files.append({"path": rel, "form": "ast", "sha256": _file_digest(root, rel, "ast")})
            continue
        modules[rel] = units
        located[rel] = found

    tests = [
        {
            "path": rel,
            "test": key,
            "body": _sha("\n".join(body)),
            "context": _context_digest(modules, context, refs),
        }
        for rel, found in located.items()
        for key, body, context, refs in found
    ]
    return {"tests": tests, "files": files}


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
