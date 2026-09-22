"""Unit tests for DeltaFuse context contract and budget linter."""

from pathlib import Path
import pytest
from deltafuse.core.context import (
    estimate_tokens,
    estimate_files_tokens,
    count_tokens,
    count_files_tokens,
    token_count_receipt,
    validate_context_budget,
    validate_task_context_budget,
    matches_contract_globs,
    try_endpoint_token_count,
    DEFAULT_TASK_BUDGET,
    PHASE_CONTRACTS,
    TokenizerUnavailableError,
    task_write_globs,
    load_change_route,
)


@pytest.fixture(autouse=True)
def _clear_tokenize_url(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)


def test_estimate_tokens_heuristic():
    text = "Hello world from DeltaFuse framework"
    # A04-01: 36 UTF-8 bytes / 3.75 = 9.6 -> ceil = 10
    assert estimate_tokens(text) == 10
    assert estimate_tokens("") == 0


def test_estimate_tokens_a04_01_counts_bytes_not_file_type(tmp_path: Path):
    """A04-01 replaced A03-01's words x factor (calibration 2026-09-21): the
    estimate follows UTF-8 bytes, so it no longer depends on the suffix or on a
    single Cyrillic letter."""
    body = '{"kind": "transition", "gate": "declaring", "from": "decomposed"}\n' * 20
    as_jsonl = tmp_path / "transitions.jsonl"
    as_json = tmp_path / "transitions.json"
    as_jsonl.write_text(body, encoding="utf-8")
    as_json.write_text(body, encoding="utf-8")
    # A03-01 counted the .jsonl as English prose, 82 % under the tokenizers.
    assert estimate_files_tokens([as_jsonl]) == estimate_files_tokens([as_json])
    assert estimate_files_tokens([as_jsonl]) == -(-len(body.encode("utf-8")) // 3.75)

    english = "The declaring gate is closed until every task is declared. " * 10
    one_letter = english + "ж"
    # One Cyrillic letter moved a whole A03-01 file from x1.3 to x2.2.
    assert estimate_tokens(one_letter) - estimate_tokens(english) <= 1

    russian = "Задача не может обогнать свой Change. " * 10
    assert estimate_tokens(russian) == -(-len(russian.encode("utf-8")) // 3.75)


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
    phases = ["intake", "analyze", "specify", "decompose", "declare", "implement", "verify"]
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
    assert matches_contract_globs("docs/spec/core.md", task_write_globs("docs"))
    assert not matches_contract_globs("src/core.py", task_write_globs("docs"))
    assert matches_contract_globs("docs/ops/runbook.md", task_write_globs("ops"))
    assert not matches_contract_globs("src/core.py", task_write_globs("ops"))


def test_load_change_route_defaults_to_code(tmp_path: Path):
    change = tmp_path / "docs" / "changes" / "CHG-001-test"
    change.mkdir(parents=True)
    (change / "change.yaml").write_text("id: CHG-001\nstatus: analyzed\n", encoding="utf-8")
    route, errors = load_change_route(change)
    assert route == "code"
    assert errors == []


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


# --- Q0-2: token counting determinism -------------------------------------


def test_count_tokens_reports_heuristic_mode(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    counted = count_tokens("alpha beta gamma")
    assert counted.mode == "heuristic"
    assert counted.measured is False
    assert counted.detail == "a04-01:/3.75"
    assert counted.tokens > 0


def test_count_tokens_reports_endpoint_mode(monkeypatch):
    class _Resp:
        def read(self) -> bytes:
            return b'{"tokens": [1, 2, 3]}'

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=2: _Resp())
    counted = count_tokens("alpha beta gamma")
    assert counted.mode == "endpoint"
    assert counted.measured is True
    assert counted.tokens == 3


def test_required_tokenizer_without_url_refuses(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.setenv("DELTAFUSE_TOKENIZER_REQUIRED", "1")
    with pytest.raises(TokenizerUnavailableError):
        count_tokens("alpha beta")


def test_required_tokenizer_does_not_fall_back_when_endpoint_fails(monkeypatch):
    def boom(req: object, timeout: float = 2) -> None:
        raise OSError("connection refused")

    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.setenv("DELTAFUSE_TOKENIZER_REQUIRED", "1")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(TokenizerUnavailableError):
        count_tokens("alpha beta")


def test_unrequired_tokenizer_still_falls_back_but_says_so(monkeypatch):
    def boom(req: object, timeout: float = 2) -> None:
        raise OSError("connection refused")

    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    counted = count_tokens("alpha beta")
    assert counted.mode == "heuristic"
    assert counted.measured is False


def test_count_files_tokens_returns_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    f1 = tmp_path / "a.md"
    f1.write_text("alpha beta gamma\n", encoding="utf-8")
    total, receipt = count_files_tokens([f1, f1])
    assert total > 0
    assert receipt["mode"] == "heuristic"
    assert receipt["measured"] is False
    assert receipt["heuristic"] == "a04-01"
    assert receipt["endpoint"] is None
    assert receipt["required"] is False
    assert receipt["files_counted"] == 1


def test_token_count_receipt_without_counting_is_unknown(monkeypatch):
    """A configured endpoint is not evidence that it ran."""
    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    receipt = token_count_receipt()
    assert receipt["mode"] == "unknown"
    assert receipt["measured"] is False
    assert receipt["endpoint"] == "http://127.0.0.1:1240/tokenize"


def test_validate_context_budget_fills_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    f1 = tmp_path / "a.md"
    f1.write_text("alpha beta\n", encoding="utf-8")
    receipt: dict = {}
    errs = validate_context_budget(
        {"max_tokens": 1000, "max_files": 5}, [f1], repo_root=tmp_path, receipt=receipt
    )
    assert errs == []
    assert receipt["mode"] == "heuristic"
    assert receipt["required"] is False


def test_validate_task_context_budget_fills_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.delenv("DELTAFUSE_TOKENIZER_REQUIRED", raising=False)
    spec = tmp_path / "docs" / "spec" / "core.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Core\n## REQ-01\n", encoding="utf-8")
    receipt: dict = {}
    errs = validate_task_context_budget(
        {"max_tokens": 64000, "max_files": 24},
        ["docs/spec/core.md#REQ-01"],
        ["src/core.py"],
        tmp_path,
        receipt=receipt,
    )
    assert errs == []
    assert receipt["mode"] == "heuristic"
    assert receipt["files_counted"] == 1


def test_default_task_budget_matches_contract():
    """docs/small-llm-contract.md pins 64,000 / 24 for framework-controlled input."""
    assert DEFAULT_TASK_BUDGET == {"max_tokens": 64000, "max_files": 24}
