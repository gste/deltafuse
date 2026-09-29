"""The Red oracle, frozen per failed test (evidence field `red_oracle_tests`).

3.3.5 froze the bytes of every test file Red declared (`red_oracle`). That caught
a weakened assertion, but it also refused every honest edit of the same file: the
regression test Implement is allowed to add, the second task's Red written into
the file after the first one was taken, a reformat. The unit that has to stay
fixed is not the file but the test Red saw fail, so that is what is frozen now.

For a Python test the Core takes the tests named in the Red record's
`tests.failed` and records, for each, digests over a normalised AST (no
positions, no comments, no docstrings, so whitespace and comments do not count):

- `body`: every statement of its scope that binds the test's name - the
  function with its decorators (`skip`, `xfail`, `parametrize` included), and a
  later redefinition of the same name too, since the last one is what runs.
- `context` (and `context_by_file`, the same split by file, so a refusal can
  say where): what the test reaches -
  - the class around a method (decorators, bases, setup, attributes; not its
    other tests);
  - by name, in the fixture scope - the declared Python test files, every
    `conftest.py` from the test's directory up to the product root (declared or
    not, present or not: one appearing later counts), and local modules named
    in `pytest_plugins` - every top-level definition, assignment or imported
    name the test refers to, followed transitively; fixtures are reached
    through parameters, `name=` aliases and `usefixtures("x")` strings;
  - through imports, in local helper modules under the test roots, declared or
    not: `from tests.helpers import make` and `helpers.make()` reach `make`
    inside that module, and what it refers to there;
  - in every module reached, what acts without being named: `pytestmark`,
    `pytest_plugins`, `pytest_*` hooks, autouse fixtures, module-level code
    that binds no name.
- `config` (one per record): the pytest sections of `pytest.ini`,
  `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `pyproject.toml`
  (`[tool.pytest]`), `tox.ini` (`[pytest]`) and `setup.cfg` (`[tool:pytest]`)
  in the product root and every directory between it and a frozen test.

Everything else is free: new tests, new fixtures and helpers nothing frozen
reaches, new imports, formatting.

Java tests (`src/test/**`) are frozen per method too, by tokens
(core/oracle_java.py). What cannot be split into tests is frozen whole: a
non-Python, non-Java file (test data) or a file that did not parse by its
bytes; a named test the Core cannot find (generated, bound dynamically) by its
module's AST or tokens; a declared Java file with no tests of its own by its
tokens. A declared test module in which Red named no failed test has all of its
tests frozen one by one: the Core cannot tell which of them is the oracle.

What the freeze cannot see at rest - state one test leaves for another at run
time - is what the isolated run is for (`isolation_plan`): Green also runs the
frozen tests on their own, by node id, and they have to pass there too.
"""

from __future__ import annotations

import ast
import configparser
import copy
import fnmatch
import hashlib
import json
import sys
import tomllib
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from deltafuse.core import oracle_java as java
from deltafuse.core.hasher import ORACLE_GLOBS, compute_file_sha256, oracle_paths

_DOC_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_OWN_SCOPE = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
# Names pytest acts on without the test naming them.
_IMPLICIT_NAMES = frozenset({"pytestmark", "pytest_plugins"})
# Where pytest reads its configuration, and the section it reads there.
_CONFIG_FILES = {
    "pytest.ini": "pytest",
    ".pytest.ini": "pytest",
    "pytest.toml": "pytest",
    ".pytest.toml": "pytest",
    "pyproject.toml": "tool.pytest",
    "tox.ini": "pytest",
    "setup.cfg": "tool:pytest",
}
# 1: 7149cad - declared test files only, support modules frozen whole, no
# Java, no conftest chain or config. Checked by oracle_v1 as it was taken.
FORMAT_VERSION = 2
ABSENT = "absent"
UNPARSEABLE = "unparseable"
_FIXTURES = ""  # the work-list scope that means "the fixture scope", not one module
_FIXTURE_REF = "@"  # marks a reference pytest may resolve as a fixture


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest().lower()


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _in_test_root(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in ORACLE_GLOBS)


def _posix(path: PurePosixPath) -> str:
    text = path.as_posix()
    return "" if text == "." else text


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
    skipped here either way, so 3.12 and 3.14 render the same tree the same.
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
    """Names a statement may reach.

    Identifiers and dotted chains rooted at one (`helpers.make`, followed into
    an imported helper module) resolve the way Python resolves them, in the
    module the statement is in. Parameters and identifier-shaped strings
    (`usefixtures("db")`, `getfixturevalue("db")`) may be fixture requests,
    which pytest resolves by name across the fixture scope; they carry the
    `@` prefix (not an identifier character) to say so.
    """
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            chain: list[str] = []
            cur: ast.AST = sub
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                out.add(".".join([cur.id, *reversed(chain)]))
        elif isinstance(sub, ast.arg):
            out.add(_FIXTURE_REF + sub.arg)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value.isidentifier():
            out.add(_FIXTURE_REF + sub.value)
    return out


@dataclass(frozen=True)
class _Import:
    kind: str  # "import" or "from"
    module: str
    level: int
    name: str
    asname: str | None


@dataclass(frozen=True)
class _Unit:
    names: frozenset[str]
    canon: str
    refs: frozenset[str]
    implicit: bool
    node: ast.AST | None
    imp: _Import | None = None


def _units(stmts: list[ast.stmt]) -> list[_Unit]:
    """One scope as units, each binding the names it binds.

    An import is split per name, so adding a name to an existing import line
    does not read as a change of the names already imported by it.
    """
    out: list[_Unit] = []
    for stmt in _strip_doc(stmts):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            kind = "import" if isinstance(stmt, ast.Import) else "from"
            module = getattr(stmt, "module", None) or ""
            level = getattr(stmt, "level", 0) or 0
            for alias in stmt.names:
                imp = _Import(kind, module, level, alias.name, alias.asname)
                text = f"{kind}({module!r},{level},{alias.name!r},{alias.asname!r})"
                if alias.name == "*":
                    out.append(_Unit(frozenset(), text, frozenset(), True, stmt, imp))
                    continue
                bound = alias.asname or alias.name.split(".")[0]
                out.append(_Unit(frozenset({bound}), text, frozenset(), False, stmt, imp))
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


class _Tree:
    """The product's files as the freeze reads them, parsed once per check."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._py: dict[str, list[_Unit] | str] = {}
        self._java: dict[str, tuple[list[str], list[java.Member]] | str] = {}

    def units(self, rel: str) -> list[_Unit] | str:
        if rel not in self._py:
            path = self.root / rel
            if not rel or not path.is_file():
                self._py[rel] = ABSENT
            else:
                try:
                    self._py[rel] = _units(ast.parse(path.read_text(encoding="utf-8")).body)
                except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
                    self._py[rel] = UNPARSEABLE
        return self._py[rel]

    def java(self, rel: str) -> tuple[list[str], list[java.Member]] | str:
        if rel not in self._java:
            path = self.root / rel
            if not path.is_file():
                self._java[rel] = ABSENT
            else:
                try:
                    toks = java.tokens(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    toks = None
                self._java[rel] = UNPARSEABLE if toks is None else (toks, java.members(toks))
        return self._java[rel]

    def find_module(self, dotted: str, importer: str, level: int = 0, *, anywhere: bool = False) -> str | None:
        """The local file an import names, if it is one the freeze follows.

        Relative imports resolve from the importer's package; absolute ones
        from the importer's directory up to the product root - where pytest's
        rootdir-based import modes put test directories on `sys.path`. Only
        modules under the test roots are followed: product code is what
        Implement is there to change. `anywhere` lifts that for plugins.
        """
        parts = [p for p in dotted.split(".") if p]
        here = PurePosixPath(importer).parent
        if level:
            base = here
            for _ in range(level - 1):
                base = base.parent
            bases = [base]
        else:
            bases = [here, *here.parents]
        for base in bases:
            for cand in (
                base.joinpath(*parts[:-1], f"{parts[-1]}.py") if parts else None,
                base.joinpath(*parts, "__init__.py"),
            ):
                if cand is None:
                    continue
                rel = _posix(cand)
                if (self.root / rel).is_file():
                    return rel if (anywhere or _in_test_root(rel)) else None
        return None


def _follow(tree: _Tree, importer: str, imp: _Import, attrs: list[str]) -> list[tuple[str, str]]:
    """Where an imported name leads: (module, name) pairs in local helpers."""
    if imp.kind == "from":
        if imp.name == "*":
            target = tree.find_module(imp.module, importer, imp.level)
            return [(target, "*")] if target else []
        sub = f"{imp.module}.{imp.name}" if imp.module else imp.name
        if tree.find_module(sub, importer, imp.level):
            cur, level = sub, imp.level
        else:
            target = tree.find_module(imp.module, importer, imp.level)
            return [(target, imp.name)] if target else []
    else:
        level = 0
        if imp.asname:
            cur = imp.name
        else:
            # `import a.b` binds `a`; the ref `a.b.make` walks the same chain.
            cur = imp.name.split(".")[0]
    for attr in attrs:
        nxt = f"{cur}.{attr}"
        if tree.find_module(nxt, importer, level):
            cur = nxt
            continue
        target = tree.find_module(cur, importer, level)
        return [(target, attr)] if target else []
    return []


def _fixture_scope(tree: _Tree, declared_py: list[str], test_files: list[str]) -> list[str]:
    """The modules whose fixtures a frozen test can receive by name.

    Every `conftest.py` from a test's directory up to the product root is in
    it whether or not it exists yet: pytest loads the one that appears later
    just the same, so its absence is part of what was frozen.
    """
    mods = set(declared_py)
    for rel in test_files:
        here = PurePosixPath(rel).parent
        for directory in (here, *here.parents):
            mods.add(_posix(directory / "conftest.py"))
    todo = sorted(mods)
    while todo:
        rel = todo.pop()
        units = tree.units(rel)
        if isinstance(units, str):
            continue
        for unit in units:
            if "pytest_plugins" not in unit.names or unit.node is None:
                continue
            for sub in ast.walk(unit.node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    plugin = tree.find_module(sub.value, rel, anywhere=True)
                    if plugin and plugin not in mods:
                        mods.add(plugin)
                        todo.append(plugin)
    return sorted(mods)


def _context(
    tree: _Tree, scope: list[str], origin: str, class_context: list[str], seeds: set[str]
) -> dict[str, str]:
    """What a Python test reaches, as normalised lines grouped by file."""
    lines: dict[str, set[str]] = defaultdict(set)
    for text in class_context:
        lines[origin].add(f"<class>\t{text}")
    in_scope = set(scope)
    todo: deque[tuple[str, str]] = deque()
    seen: set[tuple[str, str]] = set()
    started: set[str] = set()

    def refer(rel: str, ref: str) -> None:
        # A fixture request from a module pytest collects fixtures for goes to
        # the fixture scope; anything else - and a parameter of a plain helper -
        # resolves in the module itself.
        if ref.startswith(_FIXTURE_REF):
            name = ref[len(_FIXTURE_REF):]
            todo.append((_FIXTURES, name) if rel in in_scope else (rel, name))
        else:
            todo.append((rel, ref))

    def take(rel: str, unit: _Unit, attrs: list[str]) -> None:
        lines[rel].add(unit.canon)
        for ref in unit.refs:
            refer(rel, ref)
        if unit.imp is not None and unit.imp.name != "*":
            todo.extend(_follow(tree, rel, unit.imp, attrs))

    def start(rel: str) -> None:
        # A module reached at all runs its module-level code on import.
        if rel in started:
            return
        started.add(rel)
        units = tree.units(rel)
        if units == UNPARSEABLE:
            lines[rel].add("<unparseable>")
        if isinstance(units, str):
            return
        for unit in units:
            if unit.implicit:
                take(rel, unit, [])

    for rel in scope:
        start(rel)
    start(origin)
    for ref in seeds:
        refer(origin, ref)
    while todo:
        where, ref = todo.popleft()
        if (where, ref) in seen:
            continue
        seen.add((where, ref))
        root, *attrs = ref.split(".")
        if where == _FIXTURES:
            for rel in scope:
                units = tree.units(rel)
                for unit in units if not isinstance(units, str) else []:
                    if root in unit.names:
                        take(rel, unit, [])
            continue
        start(where)
        units = tree.units(where)
        if isinstance(units, str):
            continue
        bound = [u for u in units if root in u.names]
        for unit in bound:
            take(where, unit, attrs)
        if not bound:
            # Not bound here: it may come in through `from x import *`.
            for unit in units:
                if unit.imp is not None and unit.imp.name == "*":
                    todo.extend((target, ref) for target, _ in _follow(tree, where, unit.imp, []))
    return {rel: _sha("\n".join(sorted(found)) + "\n") for rel, found in lines.items() if found}


def _overall(by_file: dict[str, str]) -> str:
    return _sha("".join(f"{rel}\t{digest}\n" for rel, digest in sorted(by_file.items())))


def _pytest_section(path: Path, name: str) -> str | None:
    """The part of a config file pytest reads, normalised; None if it reads none."""
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "<unreadable>"
    if name.endswith(".toml"):
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            return "<unparseable>"
        section: Any = data
        for key in _CONFIG_FILES[name].split("."):
            section = section.get(key) if isinstance(section, dict) else None
        if section is None:
            # pytest.toml is pytest's file whatever it holds; pyproject is not.
            return None if name == "pyproject.toml" else "{}"
        return json.dumps(section, sort_keys=True, default=str)
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(raw)
    except configparser.Error:
        return "<unparseable>"
    wanted = _CONFIG_FILES[name]
    if not parser.has_section(wanted):
        # An empty pytest.ini still makes its directory the rootdir.
        return "{}" if name in {"pytest.ini", ".pytest.ini"} else None
    return json.dumps({k: parser.get(wanted, k, raw=True) for k in sorted(parser.options(wanted))})


def _config_digest(root: Path, test_files: list[str]) -> str:
    dirs: set[PurePosixPath] = set()
    for rel in test_files:
        here = PurePosixPath(rel).parent
        dirs.update((here, *here.parents))
    lines = []
    for directory in sorted(dirs, key=_posix):
        for name in _CONFIG_FILES:
            rel = _posix(directory / name)
            section = _pytest_section(root / rel, name)
            if section is not None:
                lines.append(f"{rel}\t{section}")
    return _sha("\n".join(lines) + "\n")


def _file_digest(tree: _Tree, rel: str, form: str) -> str | None:
    if form == "ast":
        units = tree.units(rel)
        if units == ABSENT:
            return None
        if units == UNPARSEABLE:
            return UNPARSEABLE
        return _sha("\n".join(u.canon for u in units))
    if form == "tokens":
        parsed = tree.java(rel)
        if parsed == ABSENT:
            return None
        if parsed == UNPARSEABLE:
            return UNPARSEABLE
        return _sha(" ".join(parsed[0]))
    path = tree.root / rel
    if not path.is_file():
        return None
    try:
        return "sha256:" + compute_file_sha256(path)
    except OSError:
        return None


def _resolve(test_id: str, modules: list[str]) -> list[tuple[str, list[str], bool]]:
    """Which declared Python module a runner's test id names, and the path inside it.

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


def _resolve_any(test_id: str, py: list[str], jv: list[str]) -> list[tuple[str, list[str], bool]]:
    return _resolve(test_id, py) + java.resolve(test_id, jv)


def _locate_all(
    find, wanted: list[tuple[list[str], bool]]
) -> tuple[list[tuple[str, Any]], bool]:
    """The wanted tests found in a module, and whether it must be frozen whole."""
    found: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for path, unique in wanted:
        key = "::".join(path)
        if key in seen:
            continue  # parametrized cases of one test
        seen.add(key)
        hit = find(path)
        if hit:
            found.append((key, hit))
        elif unique:
            # Red says this test failed and it is not a plain definition here
            # (generated, or bound in a way the Core does not follow): the
            # module cannot be split, so it is frozen whole.
            return found, True
    return found, False


def _python_scope(tree: _Tree, changed: list[str], files: list[dict[str, Any]], tests: Iterable[str]) -> list[str]:
    whole = {f.get("path") for f in files}
    declared = [rel for rel in changed if rel.endswith(".py") and rel not in whole]
    return _fixture_scope(tree, declared, sorted({t for t in tests if t.endswith(".py")}))


def freeze_red_oracle(
    repo_root: Path | str, changed_paths: Iterable[str], failed: Iterable[str]
) -> dict[str, Any] | None:
    """The `red_oracle_tests` a Red record carries. None when Red declared no test file."""
    root = Path(repo_root)
    paths = oracle_paths(changed_paths)
    if not paths:
        return None
    tree = _Tree(root)
    py = [rel for rel in paths if rel.endswith(".py") and not isinstance(tree.units(rel), str)]
    jv = [rel for rel in paths if rel.endswith(".java") and not isinstance(tree.java(rel), str)]
    named: dict[str, list[tuple[list[str], bool]]] = defaultdict(list)
    for test_id in failed:
        for rel, path, unique in _resolve_any(str(test_id), py, jv):
            named[rel].append((path, unique))

    files: list[dict[str, Any]] = []
    located: dict[str, list[tuple[str, Any]]] = {}
    for rel in paths:
        if rel in py:
            units = tree.units(rel)
            assert not isinstance(units, str)

            def find(path, units=units):
                body, context, refs = _locate(units, path)
                return (body, context, refs) if body else None

            candidates = _all_tests(units)
            form = "ast"
        elif rel in jv:
            toks, ms = tree.java(rel)  # type: ignore[misc]

            def find(path, ms=ms):
                return java.locate(ms, path) or None

            candidates = java.all_tests(ms)
            form = "tokens"
        else:
            files.append({"path": rel, "form": "bytes", "sha256": _file_digest(tree, rel, "bytes")})
            continue
        found, whole = _locate_all(find, named.get(rel, []))
        if not found and not whole:
            # Red named no failed test here that the Core could find: it cannot
            # tell which of this module's tests is the oracle, so all are.
            found, whole = _locate_all(find, [(p, True) for p in candidates])
        if whole or (not found and form == "tokens"):
            # A Java file with no tests is a helper the Core does not follow
            # into by name, so it is kept whole (formatting aside).
            files.append({"path": rel, "form": form, "sha256": _file_digest(tree, rel, form)})
        elif found:
            located[rel] = found
        # A Python module with no tests (conftest.py, a helper) is not frozen
        # whole: it is part of the fixture scope, and what the frozen tests
        # reach in it is in their context.

    scope = _python_scope(tree, paths, files, located)
    tests: list[dict[str, Any]] = []
    for rel, found in located.items():
        for key, hit in found:
            if rel.endswith(".py"):
                body, context, refs = hit
                by_file = _context(tree, scope, rel, context, refs)
                tests.append({
                    "path": rel,
                    "test": key,
                    "body": _sha("\n".join(body)),
                    "context": _overall(by_file),
                    "context_by_file": by_file,
                })
            else:
                toks, ms = tree.java(rel)  # type: ignore[misc]
                tests.append({
                    "path": rel,
                    "test": key,
                    "body": _sha(java.body_text(toks, hit)),
                    "context": _sha(java.context_text(toks, ms, hit)),
                })
    record: dict[str, Any] = {"version": FORMAT_VERSION, "tests": tests, "files": files}
    py_tests = sorted({t["path"] for t in tests if t["path"].endswith(".py")})
    if py_tests:
        record["config"] = _config_digest(root, py_tests)
        record["python"] = _python_version()
    return record


def red_oracle_changes(
    repo_root: Path | str, recorded: dict[str, Any], changed_paths: Iterable[str] = ()
) -> list[str]:
    """What moved in a frozen oracle since Red, one phrase each; empty when intact."""
    if recorded.get("version") is None:
        from deltafuse.core import oracle_v1

        return oracle_v1.red_oracle_changes(repo_root, recorded)
    root = Path(repo_root)
    tree = _Tree(root)
    changes: list[str] = []
    files = [f for f in recorded.get("files") or [] if isinstance(f, dict)]
    if len(files) != len(recorded.get("files") or []):
        changes.append("the frozen oracle record is malformed")
    for entry in files:
        if not isinstance(entry.get("path"), str):
            changes.append("the frozen oracle record is malformed")
            continue
        rel, form = entry["path"], entry.get("form") or "bytes"
        now = _file_digest(tree, rel, form)
        if now == entry.get("sha256"):
            continue
        if now is None:
            changes.append(f"{rel} was deleted")
        elif now == UNPARSEABLE:
            changes.append(f"{rel} no longer parses")
        elif entry.get("sha256") is None:
            changes.append(f"{rel} was absent at Red and exists now")
        elif form == "bytes":
            changes.append(f"{rel} changed (a file the Core cannot split into tests is frozen whole)")
        else:
            changes.append(f"{rel} changed (frozen whole: a test Red named could not be found in it, or it is a Java file with no tests)")

    entries = [e for e in recorded.get("tests") or [] if isinstance(e, dict)]
    recorded_py = recorded.get("python")
    version_note = (
        f" - Red was recorded under Python {recorded_py} and this check runs under "
        f"{_python_version()}; if nothing was edited, record Red again under this Python"
        if isinstance(recorded_py, str) and recorded_py != _python_version()
        else ""
    )
    scope: list[str] | None = None
    reported: set[str] = set()
    for entry in entries:
        rel, test = str(entry.get("path")), str(entry.get("test"))
        path = test.split("::")
        if rel.endswith(".java"):
            parsed = tree.java(rel)
            if isinstance(parsed, str):
                if rel not in reported:
                    reported.add(rel)
                    changes.append(f"{rel} was deleted" if parsed == ABSENT else f"{rel} no longer parses")
                continue
            toks, ms = parsed
            found = java.locate(ms, path)
            if not found:
                changes.append(f"{rel}::{test} was removed or renamed")
            elif _sha(java.body_text(toks, found)) != entry.get("body"):
                changes.append(f"{rel}::{test} changed (its body, signature or annotations)")
            elif _sha(java.context_text(toks, ms, found)) != entry.get("context"):
                changes.append(
                    f"what {rel}::{test} relies on changed (its class, a field, setup or helper "
                    "method, or an import it uses)"
                )
            continue
        units = tree.units(rel)
        if isinstance(units, str):
            if rel not in reported:
                reported.add(rel)
                changes.append(f"{rel} was deleted" if units == ABSENT else f"{rel} no longer parses")
            continue
        body, context, refs = _locate(units, path)
        if not body:
            changes.append(f"{rel}::{test} was removed or renamed")
            continue
        if _sha("\n".join(body)) != entry.get("body"):
            changes.append(f"{rel}::{test} changed (its body or decorators){version_note}")
            continue
        if scope is None:
            scope = _python_scope(tree, oracle_paths(changed_paths), files, [str(e.get("path")) for e in entries])
        by_file = _context(tree, scope, rel, context, refs)
        if _overall(by_file) == entry.get("context"):
            continue
        before = entry.get("context_by_file")
        where = ""
        if isinstance(before, dict):
            moved = sorted(f for f in set(before) | set(by_file) if before.get(f) != by_file.get(f))
            if moved:
                where = f" in {', '.join(moved)}"
        changes.append(
            f"what {rel}::{test} relies on changed{where} (a fixture, helper, import, its class, "
            f"or module-level code){version_note}"
        )

    config = recorded.get("config")
    if isinstance(config, str):
        py_tests = sorted({str(e.get("path")) for e in entries if str(e.get("path")).endswith(".py")})
        if _config_digest(root, py_tests) != config:
            changes.append(
                "the pytest configuration that applies to the frozen tests changed (pytest.ini, "
                "pytest.toml, pyproject.toml [tool.pytest], tox.ini [pytest] or setup.cfg "
                "[tool:pytest] between the product root and the test)"
            )
    return changes


def frozen_test_ids(recorded: dict[str, Any], red_failed: Iterable[str]) -> list[str]:
    """The runner ids from Red's `tests.failed` that name a frozen test."""
    entries = {
        (str(e.get("path")), str(e.get("test")))
        for e in recorded.get("tests") or []
        if isinstance(e, dict)
    }
    py = sorted({p for p, _ in entries if p.endswith(".py")})
    jv = sorted({p for p, _ in entries if p.endswith(".java")})
    out: list[str] = []
    for test_id in red_failed:
        for rel, path, _unique in _resolve_any(str(test_id), py, jv):
            if (rel, "::".join(path)) in entries and test_id not in out:
                out.append(str(test_id))
    return out


def _strip_suffix(name: str) -> str:
    for suffix in (".exe", ".cmd", ".bat"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def isolation_plan(
    argv: list[str], recorded: dict[str, Any], red_failed: Iterable[str]
) -> tuple[list[str], list[str]] | None:
    """The command that runs only the frozen tests, and the ids it must pass.

    Everything the Worker put on the Green command line besides the runner
    itself is dropped: an option (`-p plugin`, `-c other.ini`, `-o ...`) is as
    able to make the oracle pass as a test patching the product. None when the
    runner is not one the Core can select tests for, or nothing is frozen.
    """
    from deltafuse.core.test_reports import PYTEST_RUNNERS, runner_family

    expected = frozen_test_ids(recorded, red_failed)
    if not expected or not argv:
        return None
    family = runner_family(argv)
    head = _strip_suffix(Path(str(argv[0]).replace("\\", "/")).name).lower()
    if family == "pytest":
        prefix = list(argv[:1]) if head in PYTEST_RUNNERS else list(argv[: argv.index("pytest") + 1])
        py = sorted({
            str(e.get("path")) for e in recorded.get("tests") or []
            if isinstance(e, dict) and str(e.get("path")).endswith(".py")
        })
        nodes: list[str] = []
        for test_id in expected:
            for rel, path, _unique in _resolve(test_id, py):
                node = "::".join([rel, *path])
                if node not in nodes:
                    nodes.append(node)
        if not nodes:
            return None
        return [*prefix, *nodes, "-p", "no:cacheprovider"], expected
    if family == "jvm":
        by_class: dict[str, list[str]] = defaultdict(list)
        for test_id in expected:
            classname, _, name = test_id.rpartition("::")
            method = name.split("(", 1)[0].split("[", 1)[0].strip()
            if classname and method and method not in by_class[classname]:
                by_class[classname].append(method)
        if not by_class:
            return None
        if head in {"mvn", "mvnw"}:
            kept = [a for a in argv if not str(a).startswith(("-Dtest=", "-Dit.test="))]
            spec = ",".join(f"{cls}#{'+'.join(ms)}" for cls, ms in sorted(by_class.items()))
            return [*kept, f"-Dtest={spec}", "-Dsurefire.failIfNoSpecifiedTests=false"], expected
        kept = []
        skip = False
        for arg in argv:
            if skip:
                skip = False
                continue
            if arg == "--tests":
                skip = True
                continue
            if str(arg).startswith("--tests="):
                continue
            kept.append(arg)
        filters = [x for cls, ms in sorted(by_class.items()) for m in ms for x in ("--tests", f"{cls}.{m}")]
        return [*kept, *filters], expected
    return None
