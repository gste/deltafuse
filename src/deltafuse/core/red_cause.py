"""A Red test that fails on an error in its own code is not Red.

Reference run ref-m02-339 (qwen3.8-27b, M02, 2026-10-05): Declare wrote

    new = set(sys.modules) - before
    assert not (new & NETWORKY_MODULES), ...

with `NETWORKY_MODULES` a tuple. `set & tuple` raises TypeError whatever the product does,
so the test failed, Red was recorded, the oracle was frozen - and Implement could only prove
that no code passes it and halt for the human. Five sibling tests failed on the missing
`get_stats`; nothing in the record told the two causes apart.

The Core cannot know in general why a test fails. It refuses only what is unambiguous, from
the runner's own report (pytest): the failure was raised in the test file itself and is

* a NameError or UnboundLocalError - a name the test's own code never bound; or
* a TypeError between built-in types (`unsupported operand type(s)`, `bad operand type`) on
  a line that names nothing coming from the product: no product import, nothing assigned
  from one, no fixture argument, no helper defined in the test module.

Anything that touches the product - a stub returning the wrong type, a call with the wrong
arity - stays Red: the product can still change the outcome.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from deltafuse.core.test_reports import FAILED, TestReport

_FRAME = re.compile(r"([^\s\"'<>]+?\.py):(\d+):")
_OPERANDS = re.compile(r"(?:unsupported operand type\(s\) for [^:]+|bad operand type for [^:]+): (.+)$")
_TYPE_NAME = re.compile(r"'([A-Za-z_][\w.]*)'")
BUILTIN_TYPES = frozenset({
    "int", "float", "complex", "bool", "str", "bytes", "bytearray", "list", "tuple", "set",
    "frozenset", "dict", "range", "dict_keys", "dict_values", "dict_items",
})
_UNBOUND = ("NameError", "UnboundLocalError")


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def _last_frame(text: str, repo_root: Path) -> tuple[Path, int] | None:
    frames = _FRAME.findall(text or "")
    if not frames:
        return None
    raw, line = frames[-1]
    path = Path(raw.replace("\\", "/"))
    if not path.is_absolute():
        path = repo_root / path
    return path, int(line)


def _product_module(name: str, repo_root: Path) -> bool:
    if name in {"tests", "test"}:
        return False
    for base in (repo_root / "src", repo_root):
        pkg = base / name
        if pkg.is_dir() and any(pkg.glob("*.py")):
            return True
        if (base / f"{name}.py").is_file() and not _is_test_file(base / f"{name}.py"):
            return True
    return False


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _bound(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _taint(nodes: list[ast.AST], tainted: set[str], repo_root: Path) -> None:
    """Names that carry something from the product, propagated through assignments."""
    for _ in range(3):  # loops and later rebinding: a few passes reach the fixpoint
        for root in nodes:
            for node in ast.walk(root):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _product_module(alias.name.split(".")[0], repo_root):
                            tainted.add((alias.asname or alias.name).split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    module = (node.module or "").split(".")[0]
                    if node.level or (module and _product_module(module, repo_root)):
                        tainted.update(alias.asname or alias.name for alias in node.names)
                elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
                    value = node.value
                    if value is not None and _names(value) & tainted:
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        for target in targets:
                            tainted |= _bound(target)
                elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                    if _names(node.iter) & tainted:
                        tainted |= _bound(node.target)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        if item.optional_vars is not None and _names(item.context_expr) & tainted:
                            tainted |= _bound(item.optional_vars)


def _innermost(tree: ast.AST, line: int, kinds: tuple[type, ...]) -> ast.AST | None:
    best = None
    for node in ast.walk(tree):
        if isinstance(node, kinds) and node.lineno <= line <= (node.end_lineno or node.lineno):
            if best is None or node.lineno >= best.lineno:
                best = node
    return best


def _line_touches_product(path: Path, line: int, repo_root: Path) -> bool:
    """True unless the failing line provably names nothing from the product."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return True
    tainted: set[str] = set()
    module_level = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    _taint(module_level, tainted, repo_root)
    # A helper or class the test module defines may reach the product: count it as product.
    tainted |= {
        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    func = _innermost(tree, line, (ast.FunctionDef, ast.AsyncFunctionDef))
    if func is None:
        return True
    args = func.args
    # A fixture can be anything, the product included; so can `self` in a test class.
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
        if arg is not None:
            tainted.add(arg.arg)
    _taint(list(func.body), tainted, repo_root)
    stmt = _innermost(func, line, (ast.stmt,))
    if stmt is None:
        return True
    return bool(_names(stmt) & tainted)


def _own_code_cause(message: str, text: str, repo_root: Path) -> str | None:
    frame = _last_frame(text, repo_root)
    if frame is None:
        return None
    path, line = frame
    if not _is_test_file(path):
        return None  # raised in product code: the product decides this outcome
    exc = message.split(":", 1)[0].strip().rsplit(".", 1)[-1]
    where = f"{path.relative_to(repo_root).as_posix() if path.is_relative_to(repo_root) else path.as_posix()}:{line}"
    if exc in _UNBOUND:
        return f"{message} at {where}"
    if exc != "TypeError":
        return None
    operands = _OPERANDS.search(message)
    if operands is None:
        return None
    types = set(_TYPE_NAME.findall(operands.group(1)))
    if not types or not types <= BUILTIN_TYPES:
        return None
    if _line_touches_product(path, line, repo_root):
        return None
    return f"{message} at {where}"


def own_code_failures(report: TestReport, repo_root: Path) -> list[tuple[str, str]]:
    """Failed Red tests whose failure no product code can change, with the cause."""
    out: list[tuple[str, str]] = []
    for name in report.ids(FAILED):
        detail = report.failures.get(name)
        if detail is None:
            continue
        cause = _own_code_cause(detail[0], detail[1], repo_root)
        if cause:
            out.append((name, cause))
    return out


def own_code_error(report: TestReport, repo_root: Path) -> str | None:
    """The refusal for a Red with such tests, or None."""
    found = own_code_failures(report, repo_root)
    if not found:
        return None
    listed = "; ".join(f"{name}: {cause}" for name, cause in found[:5])
    return (
        "Red is not authentic: these tests fail on an error in their own code, which no "
        f"product code can change, so they would never pass - {listed}. Fix the test so it "
        "fails only because the behaviour is missing, then take Red again"
    )
