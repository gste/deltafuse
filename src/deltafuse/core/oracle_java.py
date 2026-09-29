"""Java test methods for the frozen Red oracle (core/oracle.py).

There is no Java parser in the Core, and freezing a method does not need one:
a tokenizer that drops comments and whitespace, plus brace matching over the
tokens, finds the members of each class. That is enough to hold one test
method fixed while the rest of the file moves.

For each JVM test Red saw fail the record keeps:

- `body`: the tokens of every method of that name in its class - annotations
  (`@Test`, `@Disabled`, `@ParameterizedTest` and its sources), signature and
  body. Overloads are included together, as a later redefinition is in Python.
- `context`: the tokens of the file with every test method and every import
  taken out, plus the imports whose simple name the test or that remainder
  uses (and wildcard imports). So the class, its fields, setup and helpers are
  frozen - the Core does not follow Java names, so it keeps all of them - while
  new test methods and new imports are free.

Formatting, comments and Javadoc do not count. A file the tokenizer cannot
read, or a named test it cannot find, is frozen whole by its tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TEST_ANNOTATIONS = frozenset(
    {"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"}
)
_TYPE_KEYWORDS = frozenset({"class", "interface", "enum", "record"})


def tokens(text: str) -> list[str] | None:
    """Java source as tokens without comments or whitespace; None if unreadable."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                return None
            i = j + 2
        elif text.startswith('"""', i):
            j = i + 3
            while True:
                k = text.find('"""', j)
                if k < 0:
                    return None
                slashes = 0
                while text[k - 1 - slashes] == "\\":
                    slashes += 1
                if slashes % 2 == 0:
                    break
                j = k + 1
            out.append(text[i : k + 3])
            i = k + 3
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\n":
                    return None
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                return None
            out.append(text[i : j + 1])
            i = j + 1
        elif c.isalnum() or c in "_$":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            out.append(text[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return out


def _is_ident(tok: str) -> bool:
    return bool(tok) and (tok[0].isalpha() or tok[0] in "_$")


def _match(toks: list[str], i: int, open_: str, close: str) -> int:
    """Index of the bracket closing the one at `i`, or len(toks) if unbalanced."""
    depth = 0
    for j in range(i, len(toks)):
        if toks[j] == open_:
            depth += 1
        elif toks[j] == close:
            depth -= 1
            if depth == 0:
                return j
    return len(toks)


@dataclass
class Member:
    start: int
    end: int  # exclusive
    kind: str  # "method", "type", "import", "other"
    name: str | None = None
    annotations: list[str] = field(default_factory=list)
    members: list["Member"] = field(default_factory=list)

    @property
    def is_test(self) -> bool:
        return self.kind == "method" and bool(TEST_ANNOTATIONS & set(self.annotations))


def members(toks: list[str], start: int = 0, end: int | None = None) -> list[Member]:
    """The members of a class body (or of a file) between `start` and `end`."""
    end = len(toks) if end is None else end
    out: list[Member] = []
    p = start
    while p < end:
        m = Member(p, p, "other")
        if toks[p] == "import":
            m.kind = "import"
        after_eq = False
        while p < end:
            t = toks[p]
            if t == "@" and p + 1 < end and toks[p + 1] != "interface":
                p += 1
                name = toks[p] if p < end else ""
                while p + 2 < end and toks[p + 1] == "." and _is_ident(toks[p + 2]):
                    p += 2
                    name = toks[p]
                m.annotations.append(name)
                p += 1
                if p < end and toks[p] == "(":
                    p = _match(toks, p, "(", ")") + 1
                continue
            if t in _TYPE_KEYWORDS and m.kind == "other" and m.name is None and p + 1 < end:
                m.kind, m.name = "type", toks[p + 1]
                p += 2
                while p < end and toks[p] not in "{;":
                    p = _match(toks, p, "(", ")") + 1 if toks[p] == "(" else p + 1
                if p < end and toks[p] == "{":
                    close = _match(toks, p, "{", "}")
                    m.members = members(toks, p + 1, min(close, end))
                    p = close + 1
                else:
                    p += 1
                break
            if t == "=" and m.name is None:
                after_eq = True
            if t == "(":
                if m.kind == "other" and not after_eq and p > m.start and _is_ident(toks[p - 1]):
                    m.kind, m.name = "method", toks[p - 1]
                p = _match(toks, p, "(", ")") + 1
                continue
            if t == "{":
                p = _match(toks, p, "{", "}") + 1
                if after_eq:
                    continue  # an array initializer; the field ends at `;`
                break
            p += 1
            if t == ";":
                break
        m.end = min(p, end)
        out.append(m)
    return out


def _type(ms: list[Member], name: str) -> list[Member]:
    return [m for m in ms if m.kind == "type" and m.name == name]


def locate(ms: list[Member], path: list[str]) -> list[Member]:
    """The methods at `path` (`Outer`, `Inner`..., `method`)."""
    scopes = ms
    for part in path[:-1]:
        found = _type(scopes, part)
        if not found:
            return []
        scopes = [inner for t in found for inner in t.members]
    return [m for m in scopes if m.kind == "method" and m.name == path[-1]]


def all_tests(ms: list[Member], prefix: tuple[str, ...] = ()) -> list[list[str]]:
    out: list[list[str]] = []
    for m in ms:
        if m.kind == "type" and m.name:
            out.extend(all_tests(m.members, (*prefix, m.name)))
        elif m.is_test and prefix and m.name:
            path = [*prefix, m.name]
            if path not in out:
                out.append(path)
    return out


def _walk(ms: list[Member]):
    for m in ms:
        yield m
        yield from _walk(m.members)


def body_text(toks: list[str], found: list[Member]) -> str:
    return "\n".join(" ".join(toks[m.start : m.end]) for m in found)


def context_text(toks: list[str], ms: list[Member], found: list[Member]) -> str:
    """The file without its tests and imports, plus the imports it still uses."""
    cut = [False] * len(toks)
    imports: list[Member] = []
    for m in _walk(ms):
        if m.is_test or m.kind == "import":
            for i in range(m.start, m.end):
                cut[i] = True
            if m.kind == "import":
                imports.append(m)
    kept = [t for i, t in enumerate(toks) if not cut[i]]
    used = set(kept) | {t for m in found for t in toks[m.start : m.end]}
    lines = [" ".join(kept)]
    for imp in imports:
        seg = toks[imp.start : imp.end]
        names = [t for t in seg if _is_ident(t) and t not in {"import", "static"}]
        if "*" in seg or (names and names[-1] in used):
            lines.append(" ".join(seg))
    return "\n".join(lines)


def resolve(test_id: str, files: list[str]) -> list[tuple[str, list[str], bool]]:
    """Which declared Java file a Surefire/Gradle id names, and the path inside it.

    The id is `com.acme.LimiterTest$Inner::cooldown()` (JUnit 5 may add the
    parameter list and an invocation index). The file is the one named after
    the outer class whose directories match most of the package.
    """
    classname, sep, name = test_id.rpartition("::")
    if not sep or not classname:
        return []
    name = name.split("(", 1)[0].split("[", 1)[0].strip()
    outer, *inner = classname.split("$")
    parts = outer.split(".")
    best: list[tuple[str, list[str]]] = []
    best_len = -1
    for rel in files:
        segs = rel[: -len(".java")].split("/")
        if segs[-1] != parts[-1]:
            continue
        k = 0
        while k + 1 < len(parts) and k + 1 < len(segs) and parts[-2 - k] == segs[-2 - k]:
            k += 1
        path = [parts[-1], *inner, name]
        if k > best_len:
            best, best_len = [(rel, path)], k
        elif k == best_len:
            best.append((rel, path))
    return [(rel, path, len(best) == 1) for rel, path in best]
