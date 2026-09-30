"""The Red oracle, frozen per failed test (evidence field `red_oracle_tests`).

Freezing whole test files (`red_oracle`) refused honest edits of them: a
regression test Implement may add, a second task's Red, a reformat. For each id
in Red's `tests.failed` the record keeps, over a normalised AST (no positions,
comments or docstrings): `body` - the definition with its decorators, and any
redefinition; `context` - within the test's own module, its class, what it
refers to by name, transitively, and what pytest applies unnamed (`pytestmark`,
hooks, autouse fixtures, module-level code). `files` freezes whole every
conftest.py on the path to the product root (absent ones too) and every other
declared Python module without tests (by AST), Java, data and unparseable files
(by bytes); `config` the pytest config files on that path (by bytes). Names are
not followed into other modules. Run-time effects are the isolated run's job.
"""

from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from deltafuse.core.hasher import compute_file_sha256, oracle_paths

FORMAT_VERSION = 2
CONFIG_FILES = ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml", "pyproject.toml", "tox.ini", "setup.cfg")
_DOC_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_OWN_SCOPE = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_IMPLICIT_NAMES = frozenset({"pytestmark", "pytest_plugins"})


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_doc(body: list[Any]) -> list[Any]:
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def canon(node: Any) -> str:
    """A position-free, docstring-free rendering of an AST. Hand-written rather
    than `ast.dump`, whose shape changed in 3.13: empty fields are skipped either
    way, so 3.12 and 3.14 render a tree the same."""
    if isinstance(node, ast.AST):
        parts = []
        for name in node._fields:
            value = getattr(node, name, None)
            if name == "body" and isinstance(node, _DOC_OWNERS):
                value = _strip_doc(value or [])
            if value is not None and value != []:
                parts.append(f"{name}={canon(value)}")
        return f"{type(node).__name__}({','.join(parts)})"
    if isinstance(node, list):
        return "[" + ",".join(canon(v) for v in node) + "]"
    return repr(node)


def _fixture_calls(defn: ast.AST) -> list[ast.Call]:
    out = []
    for dec in getattr(defn, "decorator_list", []):
        func = dec.func if isinstance(dec, ast.Call) else None
        name = getattr(func, "attr", None) or getattr(func, "id", None) or ""
        if name.endswith("fixture"):
            out.append(dec)
    return out


def _binds(stmt: ast.AST) -> set[str]:
    """Names a statement binds in its scope; `@fixture(name="x")` binds `x`."""
    out: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, (*_DEFS, ast.ClassDef)):
            out.add(node.name)
            for call in _fixture_calls(node):
                out.update(kw.value.value for kw in call.keywords
                           if kw.arg == "name" and isinstance(kw.value, ast.Constant))
            return
        if isinstance(node, _OWN_SCOPE):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out.update(a.asname or a.name.split(".")[0] for a in node.names if a.name != "*")
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(stmt)
    return out


def _refs(node: ast.AST) -> set[str]:
    """Identifiers, parameters (fixtures are requested by parameter name) and
    identifier-shaped strings (`usefixtures("db")`) a statement may reach."""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.arg):
            out.add(sub.arg)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value.isidentifier():
            out.add(sub.value)
    return out


def _units(stmts: list[ast.stmt]) -> list[tuple[frozenset[str], str, frozenset[str], bool, ast.AST]]:
    """A scope as (names bound, canon, refs, implicit, node). An import is split
    per name, so adding a name to an import line leaves the others unchanged."""
    out = []
    for stmt in _strip_doc(stmts):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for a in stmt.names:
                text = f"{type(stmt).__name__}({getattr(stmt, 'module', None)!r},{getattr(stmt, 'level', 0)},{a.name!r},{a.asname!r})"
                bound = frozenset() if a.name == "*" else frozenset({a.asname or a.name.split(".")[0]})
                out.append((bound, text, frozenset(), not bound, stmt))
            continue
        names = frozenset(_binds(stmt))
        implicit = not names or bool(names & _IMPLICIT_NAMES) or (
            isinstance(stmt, _DEFS) and (stmt.name.startswith("pytest_") or any(
                kw.arg == "autouse" and not (isinstance(kw.value, ast.Constant) and not kw.value.value)
                for call in _fixture_calls(stmt) for kw in call.keywords
            ))
        )
        out.append((names, canon(stmt), frozenset(_refs(stmt)), implicit, stmt))
    return out


def _is_test_def(stmt: ast.AST) -> bool:
    return isinstance(stmt, _DEFS) and stmt.name.startswith("test")


def _locate(units, path: list[str]) -> tuple[list[str], list[str], set[str]]:
    """(body, class context, names reached) of the test at `path` in a scope."""
    body: list[str] = []
    context: list[str] = []
    refs: set[str] = set()
    for names, text, unit_refs, _implicit, node in units:
        if path[0] not in names:
            continue
        if len(path) == 1:
            body.append(text)
            refs |= unit_refs
        elif isinstance(node, ast.ClassDef):
            b, c, r = _locate(_units(node.body), path[1:])
            shell = copy.copy(node)
            shell.body = [s for s in node.body if not _is_test_def(s)]
            body, context, refs = body + b, context + c + [canon(shell)], refs | r | _refs(shell)
        else:
            context.append(text)
            refs |= unit_refs
    return body, context, refs


def _all_tests(units) -> list[list[str]]:
    out = []
    for *_rest, node in units:
        if _is_test_def(node):
            out.append([node.name])
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            out.extend([node.name, s.name] for s in node.body if _is_test_def(s))
    return out


def _module_units(root: Path, rel: str):
    """The module's units, or None when it is absent or does not parse."""
    try:
        return _units(ast.parse((root / rel).read_text(encoding="utf-8")).body)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def _context(units, class_context: list[str], seeds: set[str]) -> str:
    """The test's class, what it reaches by name in its module, and the
    module's implicit statements."""
    lines = {f"<class>\t{c}" for c in class_context}
    todo = set(seeds)
    for _names, text, refs, implicit, _node in units:
        if implicit:
            lines.add(text)
            todo |= refs
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for names, text, refs, _implicit, _node in units:
            if name in names:
                lines.add(text)
                todo |= refs - seen
    return _sha("\n".join(sorted(lines)) + "\n")


def _file_digest(root: Path, rel: str, form: str) -> str | None:
    """None when the file is absent; `unparseable` when an `ast` file does not parse."""
    path = root / rel
    if not path.is_file():
        return None
    if form == "ast":
        units = _module_units(root, rel)
        return "unparseable" if units is None else _sha("\n".join(u[1] for u in units))
    try:
        return "sha256:" + compute_file_sha256(path)
    except OSError:
        return None


def _resolve(test_id: str, modules: list[str]) -> list[tuple[str, list[str], bool]]:
    """The declared module a pytest JUnit id (`dotted.module.Class::name[params]`)
    names, and the path in it. The dotted part is relative to pytest's rootdir,
    so the longest trailing match wins; the flag says whether it was unique."""
    classname, _, name = test_id.rpartition("::")
    cparts = classname.split(".") if classname else []
    best: list[tuple[str, list[str]]] = []
    best_len = 0
    for rel in modules:
        mparts = rel[:-3].split("/")
        k = next((k for k in range(len(mparts), 0, -1) if cparts[:k] == mparts[-k:]), 0)
        if k and k >= best_len:
            best = ([] if k > best_len else best) + [(rel, cparts[k:] + [name.split("[", 1)[0]])]
            best_len = k
    return [(rel, path, len(best) == 1) for rel, path in best]


def _on_path(test_files: Iterable[str], name: str) -> list[str]:
    """`name` in every directory from each test's directory up to the root."""
    out: set[str] = set()
    for rel in test_files:
        here = PurePosixPath(rel).parent
        out.update((d / name).as_posix().removeprefix("./") for d in (here, *here.parents))
    return sorted(out)


def _config_digest(root: Path, test_files: list[str]) -> str:
    lines = [
        f"{rel}\t{_file_digest(root, rel, 'bytes')}"
        for name in CONFIG_FILES for rel in _on_path(test_files, name)
        if (root / rel).is_file()
    ]
    return _sha("\n".join(sorted(lines)) + "\n")


def freeze_red_oracle(repo_root: Path | str, changed_paths: Iterable[str], failed: Iterable[str]) -> dict[str, Any] | None:
    """The `red_oracle_tests` a Red record carries. None when Red declared no test file."""
    root = Path(repo_root)
    paths = oracle_paths(changed_paths)
    if not paths:
        return None
    parsed = {rel: u for rel in paths if rel.endswith(".py") and (u := _module_units(root, rel)) is not None}
    named: dict[str, list[tuple[list[str], bool]]] = {}
    for test_id in failed:
        for rel, path, unique in _resolve(str(test_id), sorted(parsed)):
            named.setdefault(rel, []).append((path, unique))

    tests: list[dict[str, Any]] = []
    whole: dict[str, str] = {}
    for rel in paths:
        units = parsed.get(rel)
        if units is None:
            whole[rel] = "bytes"
            continue
        wanted = named.get(rel) or [(p, True) for p in _all_tests(units)]
        found = []
        for path, unique in wanted:
            key = "::".join(path)
            body, context, refs = _locate(units, path)
            if body and key not in [f[0] for f in found]:
                found.append((key, body, context, refs))
            elif not body and unique:
                found = []  # a named test that is not a plain definition: freeze the module whole
                break
        if not found:
            whole[rel] = "ast"
            continue
        tests += [{"path": rel, "test": key, "body": _sha("\n".join(body)), "context": _context(units, context, refs)}
                  for key, body, context, refs in found]
    test_files = sorted({t["path"] for t in tests})
    for rel in _on_path(test_files, "conftest.py"):
        whole.setdefault(rel, "ast")
    files = [{"path": rel, "form": form, "sha256": _file_digest(root, rel, form)} for rel, form in sorted(whole.items())]
    record: dict[str, Any] = {"version": FORMAT_VERSION, "tests": tests, "files": files}
    if test_files:
        record["config"] = _config_digest(root, test_files)
    return record


def red_oracle_changes(repo_root: Path | str, recorded: dict[str, Any]) -> list[str]:
    """What moved in a frozen oracle since Red, one phrase each; empty when intact."""
    root = Path(repo_root)
    if recorded.get("version") != FORMAT_VERSION:
        return ["the record was written by a pre-release build of the per-test freeze and cannot be checked"]
    changes = []
    for entry in recorded.get("files") or []:
        rel, form, then = str(entry.get("path")), entry.get("form") or "bytes", entry.get("sha256")
        now = _file_digest(root, rel, form)
        if now == then:
            continue
        what = "a conftest.py on the frozen test's path" if rel.rsplit("/", 1)[-1] == "conftest.py" else (
            "a declared module with no tests of its own" if form == "ast" else "a file the Core does not split into tests")
        state = "was deleted" if now is None else "was added" if then is None else (
            "no longer parses" if now == "unparseable" else "changed")
        changes.append(f"{rel} {state} ({what}, frozen whole)")
    modules: dict[str, Any] = {}
    for entry in recorded.get("tests") or []:
        rel, test = str(entry.get("path")), str(entry.get("test"))
        if rel not in modules:
            modules[rel] = _module_units(root, rel)
            if modules[rel] is None:
                changes.append(f"{rel} was deleted" if not (root / rel).is_file() else f"{rel} no longer parses")
        units = modules[rel]
        if units is None:
            continue
        body, context, refs = _locate(units, test.split("::"))
        if not body:
            changes.append(f"{rel}::{test} was removed or renamed")
        elif _sha("\n".join(body)) != entry.get("body"):
            changes.append(f"{rel}::{test} changed (its body or decorators)")
        elif _context(units, context, refs) != entry.get("context"):
            changes.append(f"what {rel}::{test} relies on changed (in {rel}: a fixture, helper, import, "
                           "its class, or module-level code)")
    test_files = sorted({str(e.get("path")) for e in recorded.get("tests") or []})
    if "config" in recorded and _config_digest(root, test_files) != recorded["config"]:
        changes.append("the pytest configuration on the frozen tests' path changed ("
                       + ", ".join(CONFIG_FILES) + " between the product root and the test)")
    return changes


def frozen_test_ids(recorded: dict[str, Any], red_failed: Iterable[str]) -> list[str]:
    """The ids from Red's `tests.failed` that name a frozen test."""
    entries = {(str(e.get("path")), str(e.get("test"))) for e in recorded.get("tests") or []}
    modules = sorted({p for p, _ in entries})
    return [t for t in dict.fromkeys(map(str, red_failed))
            if any((rel, "::".join(path)) in entries for rel, path, _ in _resolve(t, modules))]


# Test selection and plugin loading, which the isolated run must not inherit;
# and options whose value (often a path) must not be read as a selection.
_DROP = frozenset({"-p", "-k", "-m", "--deselect", "--ignore", "--ignore-glob", "--junitxml", "--junit-xml"})
_DROP_FLAGS = frozenset({"--lf", "--last-failed", "--ff", "--failed-first", "--sw", "--stepwise", "--pyargs"})
_KEEP = frozenset({"-c", "--config-file", "-o", "--override-ini", "--rootdir", "--import-mode", "--confcutdir",
                   "--basetemp", "-W", "--pythonwarnings"})


def isolation_plan(argv: list[str], recorded: dict[str, Any], red_failed: Iterable[str],
                   repo_root: Path | str = ".") -> tuple[list[str], list[str]] | None:
    """The pytest command running only the frozen tests, and the ids it must pass.

    The Worker's options stay (`-c`, `-o`, `--import-mode`, a plugin's own
    options may be what the suite needs); its test selection and `-p` go. A
    bare argument that is not an existing path is an option's value and stays.
    None when the runner is not pytest or nothing is frozen.
    """
    from deltafuse.core.test_reports import PYTEST_RUNNERS, runner_family

    expected = frozen_test_ids(recorded, red_failed)
    if not expected or runner_family(argv) != "pytest":
        return None
    head = Path(str(argv[0]).replace("\\", "/")).name.lower().removesuffix(".exe")
    split = 1 if head in PYTEST_RUNNERS else argv.index("pytest") + 1
    kept: list[str] = []
    rest = iter(argv[split:])
    for arg in rest:
        if arg in _DROP:
            next(rest, None)
        elif arg in _KEEP:
            kept += [arg, next(rest, "")]
        elif arg in _DROP_FLAGS or (arg.split("=", 1)[0] if arg.startswith("--") else arg[:2]) in _DROP:
            continue  # `--deselect=x`, `-pplugin`, `-kexpr`
        elif arg.startswith("-") or not (Path(repo_root) / arg.split("::", 1)[0]).exists():
            kept.append(arg)
    modules = sorted({str(e.get("path")) for e in recorded.get("tests") or []})
    nodes = list(dict.fromkeys("::".join([rel, *path]) for t in expected for rel, path, _ in _resolve(t, modules)))
    return [*argv[:split], *kept, *nodes, "-p", "no:cacheprovider"], expected
