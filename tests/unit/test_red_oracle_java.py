"""Java tests in the frozen Red oracle, per method (core/oracle_java.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.core import oracle_java as java
from deltafuse.core.oracle import isolation_plan
from tests.fixtures.oracle_freeze import edit, errors, freeze, record_of

JAVA = "src/test/java/com/acme/LimiterTest.java"
JAVA_TEXT = """package com.acme;

import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/** Limiter oracle. */
class LimiterTest {
    private Limiter limiter;
    private static final int[] LIMITS = {30, 60};
    private final Runnable noop = () -> { };

    @BeforeEach
    void setUp() { limiter = new Limiter(); }

    private int floor() { return 30; }

    @Test
    void cooldown() {
        // the floor
        assertTrue(limiter.cooldown() >= floor(), "at least \\"thirty\\" {");
    }

    @Test
    void unrelated() { assertTrue(true); }

    @Nested
    class Burst {
        @Test
        void burst() { assertTrue(limiter.burst() == 5); }
    }
}
"""
JAVA_FAILED = [
    "com.acme.LimiterTest::cooldown()",
    "com.acme.LimiterTest$Burst::burst()",
]


@pytest.fixture
def frozen(tmp_path: Path) -> Path:
    red = freeze(tmp_path, {JAVA: JAVA_TEXT}, JAVA_FAILED)
    record = record_of(red)
    assert sorted(t["test"] for t in record["tests"]) == ["LimiterTest::Burst::burst", "LimiterTest::cooldown"]
    assert record["files"] == []
    assert errors(tmp_path, red) == []
    return red


def test_the_tokenizer_drops_comments_and_keeps_literals_whole():
    toks = java.tokens('int a = 1; // c\n/* b */ String s = "x // y"; char c = \'}\'; String t = """\n q """;')
    assert toks == [
        "int", "a", "=", "1", ";", "String", "s", "=", '"x // y"', ";",
        "char", "c", "=", "'}'", ";", "String", "t", "=", '"""\n q """', ";",
    ]
    assert java.tokens('String s = "open') is None
    assert java.tokens("/* open") is None


def test_members_find_methods_fields_and_nested_classes():
    toks = java.tokens(JAVA_TEXT)
    top = java.members(toks)
    (cls,) = [m for m in top if m.kind == "type"]
    assert cls.name == "LimiterTest"
    kinds = [(m.kind, m.name, m.is_test) for m in cls.members]
    assert kinds == [
        ("other", None, False),  # limiter
        ("other", None, False),  # LIMITS = {..};
        ("other", None, False),  # noop = () -> { };
        ("method", "setUp", False),
        ("method", "floor", False),
        ("method", "cooldown", True),
        ("method", "unrelated", True),
        ("type", "Burst", False),
    ]
    assert java.all_tests(top) == [["LimiterTest", "cooldown"], ["LimiterTest", "unrelated"], ["LimiterTest", "Burst", "burst"]]


@pytest.mark.parametrize(
    "test_id, expected",
    [
        ("com.acme.LimiterTest::cooldown()", ["LimiterTest", "cooldown"]),
        ("com.acme.LimiterTest::cooldown", ["LimiterTest", "cooldown"]),
        ("com.acme.LimiterTest::cooldown(int)[2]", ["LimiterTest", "cooldown"]),
        ("com.acme.LimiterTest$Burst::burst()", ["LimiterTest", "Burst", "burst"]),
        ("LimiterTest::cooldown", ["LimiterTest", "cooldown"]),
    ],
)
def test_surefire_and_gradle_ids_resolve_to_the_file_and_method(test_id, expected):
    assert java.resolve(test_id, [JAVA, "src/test/java/other/LimiterTest.java"])[0][:2] == (JAVA, expected)


@pytest.mark.parametrize(
    "old, new, named",
    [
        ("limiter.cooldown() >= floor()", "limiter.cooldown() >= 0", "LimiterTest::cooldown changed"),
        ("    @Test\n    void cooldown()", "    @Disabled\n    @Test\n    void cooldown()", "LimiterTest::cooldown changed"),
        ("void cooldown()", "void cooldownOld()", "LimiterTest::cooldown was removed or renamed"),
        ("limiter.burst() == 5", "true", "LimiterTest::Burst::burst changed"),
        ("return 30;", "return 0;", f"what {JAVA}::LimiterTest::cooldown relies on changed"),
        ("limiter = new Limiter();", "limiter = new FakeLimiter();", "relies on changed"),
        ("import static org.junit.jupiter.api.Assertions.assertTrue;", "import static fake.Assertions.assertTrue;", "relies on changed"),
        ("    @Nested\n", "    @Disabled\n    @Nested\n", "Burst::burst relies on changed"),
    ],
)
def test_editing_a_frozen_java_test_is_refused_and_named(tmp_path: Path, frozen: Path, old, new, named):
    edit(tmp_path, old, new, rel=JAVA)
    errs = errors(tmp_path, frozen)
    assert errs and named in errs[0], errs


@pytest.mark.parametrize(
    "old, new",
    [
        ("        // the floor\n", ""),
        ("/** Limiter oracle. */", "/** Limiter oracle, reworded. */"),
        ("    void cooldown() {", "    void cooldown()\n    {"),
        ("void unrelated() { assertTrue(true); }", "void unrelated() { assertTrue(1 == 1); }"),
        ("import org.junit.jupiter.api.Test;", "import org.junit.jupiter.api.Test;\nimport java.util.List;"),
        (
            "    @Test\n    void unrelated()",
            "    @Test\n    void capped() { assertTrue(limiter.cooldown() < 3600); }\n\n    @Test\n    void unrelated()",
        ),
    ],
)
def test_edits_outside_the_frozen_java_tests_are_not_refused(tmp_path: Path, frozen: Path, old, new):
    edit(tmp_path, old, new, rel=JAVA)
    assert errors(tmp_path, frozen) == []


def test_deleting_the_java_file_is_refused_once(tmp_path: Path, frozen: Path):
    (tmp_path / JAVA).unlink()
    errs = errors(tmp_path, frozen)
    assert len(errs) == 1 and f"{JAVA} was deleted" in errs[0], errs


def test_a_java_file_that_does_not_tokenize_keeps_the_file_hash(tmp_path: Path):
    red = freeze(tmp_path, {JAVA: 'class LimiterTest { String s = "unterminated; }\n'}, JAVA_FAILED)
    record = record_of(red)
    assert record["files"][0]["form"] == "bytes" and record["tests"] == []


def test_a_declared_java_helper_without_tests_is_frozen_whole_by_tokens(tmp_path: Path):
    helper = "src/test/java/com/acme/Fixtures.java"
    red = freeze(
        tmp_path,
        {JAVA: JAVA_TEXT, helper: "class Fixtures {\n  static int floor() { return 30; }\n}\n"},
        JAVA_FAILED,
    )
    edit(tmp_path, "{\n  static", "{ // helpers\n  static", rel=helper)
    assert errors(tmp_path, red) == []
    edit(tmp_path, "return 30;", "return 0;", rel=helper)
    errs = errors(tmp_path, red)
    assert errs and f"{helper} changed" in errs[0], errs


def test_the_isolated_run_for_maven_and_gradle(tmp_path: Path, frozen: Path):
    record = record_of(frozen)
    mvn, expected = isolation_plan(["mvn", "-B", "-Dtest=Other", "test"], record, JAVA_FAILED)
    assert expected == JAVA_FAILED
    assert mvn == [
        "mvn", "-B", "test",
        "-Dtest=com.acme.LimiterTest#cooldown,com.acme.LimiterTest$Burst#burst",
        "-Dsurefire.failIfNoSpecifiedTests=false",
    ]
    gradle, _ = isolation_plan(["./gradlew", "test", "--tests", "Other", "--tests=More"], record, JAVA_FAILED)
    assert gradle == [
        "./gradlew", "test",
        "--tests", "com.acme.LimiterTest.cooldown",
        "--tests", "com.acme.LimiterTest$Burst.burst",
    ]
