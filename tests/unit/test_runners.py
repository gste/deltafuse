"""The runner allowlist identifies a runner by its name, not by its path.

Isolated M01 runs (2026-09-23) called the virtualenv's pytest by absolute
path, because pytest was not on PATH there. Every such evidence command was
refused as a substituted runner - 27 of 27 in one run - and the Worker spent
the rest of its budget guessing.
"""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.runners import runner_is_authorized


def test_a_virtualenv_pytest_is_pytest():
    for argv0 in (
        "pytest",
        "D:/Users/x/proj/.venv/Scripts/pytest.exe",
        r"D:\Users\x\proj\.venv\Scripts\pytest.exe",
        "/home/x/proj/.venv/bin/pytest",
    ):
        assert runner_is_authorized([argv0, "tests/test_limiter.py", "-v"], route="code"), argv0


def test_an_absolute_python_still_needs_a_script_and_no_dash_c():
    assert runner_is_authorized(
        ["C:/Python312/python.exe", "-m", "pytest", "tests/"], route="code"
    )
    assert runner_is_authorized(["/usr/bin/python3", "tools/check.py"], route="code")
    # The rule this allowlist exists for: no one-liner standing in for the suite.
    assert not runner_is_authorized(
        ["C:/Python312/python.exe", "-c", "print('green')"], route="code"
    )


def test_a_substituted_binary_is_still_refused():
    assert not runner_is_authorized(["./green.sh"], route="code")
    assert not runner_is_authorized(["C:/tools/definitely-not-pytest.exe"], route="code")


def test_a_configured_prefix_accepts_the_same_runner_by_path(tmp_path: Path):
    (tmp_path / ".deltafuse").mkdir()
    (tmp_path / ".deltafuse" / "config.yaml").write_text(
        "workflow:\n  test_commands:\n    - pytest -q\n", encoding="utf-8"
    )
    assert runner_is_authorized(
        [str(tmp_path / ".venv/Scripts/pytest.exe"), "-q"], route="code", product_root=tmp_path
    )
    assert not runner_is_authorized(
        [str(tmp_path / ".venv/Scripts/pytest.exe"), "--collect-only"],
        route="code",
        product_root=tmp_path,
    )


def test_docs_route_takes_a_plain_interpreter():
    assert runner_is_authorized(["python", "check_links.py"], route="docs")
    assert runner_is_authorized(["/usr/bin/python3", "check_links.py"], route="docs")
    assert not runner_is_authorized(["bash", "check.sh"], route="docs")


def test_a_refused_red_says_what_the_core_read():
    """The verdict alone cannot be acted on.

    52 of the 89 evidence refusals in the runs of 2026-09-23 were "Red
    failure_category is 'fixture-error'", and the log of a refused attempt is
    never stored - so neither the Worker nor a later reader could tell why.
    """
    from deltafuse.core.evidence import _why_not_behavioral

    log = (
        "collected 1 item\n"
        "tests/test_limiter.py::test_cooldown ERROR\n"
        "E   AttributeError: 'RateLimiter' object has no attribute 'get_stats'\n"
    )
    said = _why_not_behavioral(log)
    assert "no AssertionError" in said
    assert "AttributeError: 'RateLimiter' object has no attribute 'get_stats'" in said
    assert _why_not_behavioral("") == "the command printed nothing to read"
