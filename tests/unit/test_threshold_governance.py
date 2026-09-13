"""QF-022: threshold governance — numeric release gates change only via a
pre-recorded maintainer Decision.

Red evidence pins:
- the undocumented `TOKENIZER_CONSISTENCY_ALLOWANCE = 48` numeric range is
  gone from the release gate (QF-015 added it after implementation, without
  a Decision);
- thresholds.md is the source of the approved T1-T8 only; host/tokenizer
  mechanics live in the qualification host contract;
- a thresholds.md revision without an accepted Decision blocks release
  tooling (the campaign aborts before any Worker call);
- tokenizer consistency stays fail-closed WITHOUT a numeric allowance:
  usage must be measured, the tokenize count must be measured, and the
  chat template can only ADD tokens (usage >= tokenize count);
- fingerprint drift still invalidates the campaign.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import qualify  # noqa: E402
import threshold_governance  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
QUALIFY_SOURCE = REPO / "scripts" / "qualify.py"
THRESHOLDS_DOC = REPO / "backlog" / "product" / "v3" / "thresholds.md"
DECISIONS_DOC = REPO / "backlog" / "product" / "v3" / "decisions.md"


# ------------------------------------------------- no undocumented gates


def test_no_numeric_allowance_constant_in_release_gate():
    """The +48 allowance (and any allowance-shaped numeric gate) must be
    gone from the runner: it was never backed by a Decision."""
    source = QUALIFY_SOURCE.read_text(encoding="utf-8")
    assert "TOKENIZER_CONSISTENCY_ALLOWANCE" not in source
    documented = "\n".join([
        THRESHOLDS_DOC.read_text(encoding="utf-8"),
        DECISIONS_DOC.read_text(encoding="utf-8"),
    ])
    assert threshold_governance.undocumented_numeric_gates(source, documented) == []


def test_thresholds_md_has_no_tokenizer_allowance():
    """thresholds.md carries the approved T1-T8 only; the +48 range moved
    out with QF-022."""
    text = THRESHOLDS_DOC.read_text(encoding="utf-8")
    assert "+ 48" not in text and "+48" not in text
    assert "TOKENIZER_CONSISTENCY_ALLOWANCE" not in text
    assert "Токенизация" not in text  # host/tokenizer rules live in the contract


def test_host_contract_exists_and_governs_tokenizer():
    contract = REPO / "backlog" / "product" / "v3" / "qualification-host-contract.md"
    text = contract.read_text(encoding="utf-8")
    assert "tokenize" in text
    assert "fingerprint" in text.lower()


# --------------------------------------------------- revision governance


def test_current_thresholds_revision_is_approved():
    """The frozen thresholds file is approved by a recorded Decision."""
    revision = qualify.thresholds_revision()
    assert threshold_governance.check_revision(
        revision, DECISIONS_DOC
    ), "current thresholds.md revision is not covered by an accepted Decision"


def test_unapproved_threshold_revision_blocks_release_tooling(tmp_path):
    """Changing the frozen thresholds file without a new accepted Decision
    blocks release tooling."""
    mutated = tmp_path / "thresholds.md"
    mutated.write_text(
        THRESHOLDS_DOC.read_text(encoding="utf-8")
        + "\n| T9 | sneaky | 999 | nobody | guess |\n",
        encoding="utf-8",
    )
    proc = __import__("subprocess").run(
        [sys.executable, "-c",
         "import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], 'rb')"
         ".read()).hexdigest()[:12])", str(mutated)],
        capture_output=True, text=True,
    )
    # the governance check keys on git hash-object, compute it the same way
    git_hash = __import__("subprocess").run(
        ["git", "hash-object", str(mutated)], capture_output=True, text=True,
        cwd=str(REPO),
    ).stdout.strip()[:12]
    assert not threshold_governance.check_revision(git_hash, DECISIONS_DOC)
    with pytest.raises(qualify.QualificationError, match="governance"):
        qualify.assert_threshold_governance(revision=git_hash)


def test_decision_created_after_implementation_is_not_accepted(tmp_path):
    """A Decision draft without accepted status does not approve a revision."""
    decisions = tmp_path / "decisions.md"
    decisions.write_text(
        "## DR-3.0-9 — test\n\n- **Статус:** draft\n\n"
        "**Approved thresholds revisions:** `abc123def456`\n",
        encoding="utf-8",
    )
    assert not threshold_governance.check_revision("abc123def456", decisions)


# --------------------------------------------- tokenizer without allowance


def _probe(monkeypatch, *, tokens, usage):
    def post(url, payload, timeout):
        if url.endswith("/api/v0/tokenize"):
            if tokens is None:
                raise OSError("no endpoint")
            return {"tokens": tokens}
        return {"usage": {"prompt_tokens": usage}}

    monkeypatch.setattr(qualify, "_post_json", post)


def test_consistency_requires_measured_usage_not_below_tokenizer(monkeypatch):
    """Without a tuned allowance: usage must be measured and can never be
    below the tokenizer count (the chat template only adds tokens)."""
    _probe(monkeypatch, tokens=list(range(200)), usage=199)
    with pytest.raises(qualify.QualificationError, match="consistency"):
        qualify._assert_tokenizer_consistency("http://x", "m", 200)


def test_consistency_accepts_template_overhead_only(monkeypatch):
    _probe(monkeypatch, tokens=list(range(200)), usage=200)
    qualify._assert_tokenizer_consistency("http://x", "m", 200)  # no raise
    _probe(monkeypatch, tokens=list(range(200)), usage=260)
    qualify._assert_tokenizer_consistency("http://x", "m", 200)  # no raise


@pytest.mark.parametrize("usage", [None, True, 0, "many"])
def test_consistency_unmeasured_usage_blocks(monkeypatch, usage):
    _probe(monkeypatch, tokens=[1, 2, 3], usage=usage)
    with pytest.raises(qualify.QualificationError, match="consistency"):
        qualify._assert_tokenizer_consistency("http://x", "m", 3)
