"""Unit tests for DeltaFuse context contract and budget linter."""

from pathlib import Path
import pytest
from deltafuse.core.context import (
    estimate_tokens,
    estimate_files_tokens,
    validate_context_budget,
    validate_task_context_budget,
    matches_contract_globs,
    try_endpoint_token_count,
    PHASE_CONTRACTS,
    task_write_globs,
)


@pytest.fixture(autouse=True)
def _clear_tokenize_url(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)


def test_estimate_tokens_heuristic():
    text = "Hello world from DeltaFuse framework"
    # 5 English words * 1.3 = 6.5 -> ceil = 7
    tokens = estimate_tokens(text)
    assert tokens == 7


def test_estimate_tokens_a03_01_upper_bounds(tmp_path: Path):
    """A03-01: coefficient fallback is an upper bound vs recorded ornith/Qwen counts."""
    en = " ".join(["word"] * 20)
    assert estimate_tokens(en) >= 26
    assert estimate_tokens(en) <= 32  # 1.3x EN must not inflate absurdly

    ru = " ".join(["проверка"] * 17)
    assert estimate_tokens(ru) >= 37

    py = tmp_path / "sample.py"
    py.write_text(" ".join(["token"] * 30), encoding="utf-8")
    assert estimate_files_tokens([py]) >= 81

    yaml_file = tmp_path / "manifest.yaml"
    yaml_file.write_text(" ".join(["key:"] * 22), encoding="utf-8")
    yaml_est = estimate_files_tokens([yaml_file])
    assert yaml_est >= 98
    naive = 29  # historical words*1.3 on 22 words
    assert yaml_est > naive * 2  # no 70% YAML undercount

    log_file = tmp_path / "trace.log"
    log_file.write_text(" ".join(["ts"] * 35), encoding="utf-8")
    assert estimate_files_tokens([log_file]) >= 168


def test_validate_context_budget(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("word " * 100, encoding="utf-8")  # ~130 tokens
    f2.write_text("word " * 200, encoding="utf-8")  # ~260 tokens

    budget_ok = {"max_tokens": 1000, "max_files": 5}
    assert validate_context_budget(budget_ok, [f1, f2]) == []

    budget_file_exceeded = {"max_tokens": 1000, "max_files": 1}
    errs = validate_context_budget(budget_file_exceeded, [f1, f2])
    assert any("files loaded, maximum allowed is 1" in e for e in errs)

    budget_token_exceeded = {"max_tokens": 200, "max_files": 5}
    errs2 = validate_context_budget(budget_token_exceeded, [f1, f2])
    assert any("tokens loaded, maximum allowed is 200" in e for e in errs2)


def test_validate_context_budget_missing_file_is_error(tmp_path: Path):
    missing = tmp_path / "nope.md"
    errs = validate_context_budget({"max_tokens": 1000, "max_files": 5}, [missing])
    assert any("does not exist" in e for e in errs)


def test_validate_context_budget_rejects_path_traversal(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("word " * 50, encoding="utf-8")
    errs = validate_context_budget(
        {"max_tokens": 1000, "max_files": 5},
        [outside],
        repo_root=repo,
    )
    assert any("Path traversal forbidden" in e for e in errs)


def test_validate_context_budget_deduplicates_for_limits(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("word " * 100, encoding="utf-8")
    errs = validate_context_budget(
        {"max_tokens": 1000, "max_files": 1},
        [f1, f1],
    )
    assert errs == []


def test_estimate_files_tokens_deduplicates(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("word " * 100, encoding="utf-8")
    once = estimate_files_tokens([f1])
    twice = estimate_files_tokens([f1, f1])
    assert once == twice
    assert once > 0


def test_phase_contracts_completeness():
    phases = ["intake", "analyze", "specify", "decompose", "target", "implement", "verify"]
    for p in phases:
        assert p in PHASE_CONTRACTS
        assert "allowed_read" in PHASE_CONTRACTS[p]
        assert "allowed_write" in PHASE_CONTRACTS[p]


def test_matches_contract_globs_src_and_tests():
    assert matches_contract_globs("src/core.py", ["src/**"])
    assert matches_contract_globs("tests/test_task-001.py", ["tests/**"])
    assert not matches_contract_globs("docs/spec/core.md", ["src/**", "tests/**"])
    assert matches_contract_globs("src/core.py", task_write_globs())
    assert not matches_contract_globs("docs/spec/core.md", task_write_globs())


def test_validate_task_context_budget_allows_missing_allowed_path(tmp_path: Path):
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Core\n## REQ-01\n", encoding="utf-8")
    errs = validate_task_context_budget(
        {"max_tokens": 16000, "max_files": 24},
        ["docs/spec/core.md#REQ-01"],
        ["src/core.py"],
        tmp_path,
    )
    assert errs == []


def test_validate_task_context_budget_counts_declared_files(tmp_path: Path):
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Core\n## REQ-01\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    allowed = []
    for i in range(50):
        p = src / f"f{i:02d}.py"
        p.write_text("x = 1\n", encoding="utf-8")
        allowed.append(f"src/f{i:02d}.py")
    errs = validate_task_context_budget(
        {"max_tokens": 16000, "max_files": 24},
        ["docs/spec/core.md#REQ-01"],
        allowed,
        tmp_path,
    )
    assert any("files loaded, maximum allowed is 24" in e for e in errs)


def test_try_endpoint_token_count_skips_without_url(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    assert try_endpoint_token_count("hello") is None


def test_try_endpoint_token_count_posts_tokenize_not_chat(monkeypatch):
    captured: dict[str, object] = {}

    class _Resp:
        def read(self) -> bytes:
            return b'{"tokens": [1, 2, 3, 4]}'

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: object, timeout: float = 2) -> _Resp:
        captured["url"] = getattr(req, "full_url", "")
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert try_endpoint_token_count("hi") == 4
    assert captured["url"] == "http://127.0.0.1:1240/tokenize"
    assert "/v1/chat/completions" not in str(captured["url"])
