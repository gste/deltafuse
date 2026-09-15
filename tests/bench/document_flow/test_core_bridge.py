"""Contract tests for J03-401 core_bridge module."""

import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))


def _load_core_bridge():
    path = ROOT / 'scripts/document_flow/core_bridge.py'
    spec = importlib.util.spec_from_file_location('j03_core_bridge', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_core_bridge_module_exists_and_callable():
    bridge = _load_core_bridge()
    assert hasattr(bridge, 'observe_core')
    assert callable(bridge.observe_core)


def test_observe_core_on_empty_product_returns_intake_or_initial_state(tmp_path):
    bridge = _load_core_bridge()
    deltafuse_dir = tmp_path / '.deltafuse'
    deltafuse_dir.mkdir()
    (deltafuse_dir / 'lock.yaml').write_text('schema_version: 1\nversion: 3.0.0\n', encoding='utf-8')
    (deltafuse_dir / 'config.yaml').write_text('project:\n  baseline: draft\n', encoding='utf-8')
    (tmp_path / 'docs' / 'intake').mkdir(parents=True)
    (tmp_path / 'docs' / 'changes').mkdir(parents=True)

    obs = bridge.observe_core(tmp_path)
    assert obs.step == 'intake'
    assert obs.halt is None or obs.halt.get('kind') in ('done', None)
    assert isinstance(obs.ready, list)
    assert isinstance(obs.blocked, list)


def test_core_bridge_preserves_envelope_and_denies_unauthorized_widening(tmp_path):
    bridge = _load_core_bridge()
    deltafuse_dir = tmp_path / '.deltafuse'
    deltafuse_dir.mkdir()
    (deltafuse_dir / 'lock.yaml').write_text('schema_version: 1\nversion: 3.0.0\n', encoding='utf-8')
    (deltafuse_dir / 'config.yaml').write_text('project:\n  baseline: accepted\n', encoding='utf-8')
    (tmp_path / 'docs' / 'intake').mkdir(parents=True)
    change_dir = tmp_path / 'docs' / 'changes' / 'CHG-001'
    change_dir.mkdir(parents=True)
    (change_dir / 'routing.yaml').write_text('schema_version: 1\nroute: standard\n', encoding='utf-8')
    (change_dir / 'coverage.yaml').write_text('schema_version: 1\ncoverage: complete\n', encoding='utf-8')

    transitions = [
        {'kind': 'transition', 'change': 'CHG-001', 'gate': 'intake', 'from': 'normalized', 'to': 'analyzing'},
        {'kind': 'transition', 'change': 'CHG-001', 'gate': 'analyzed', 'from': 'analyzing', 'to': 'analyzed'},
        {'kind': 'transition', 'change': 'CHG-001', 'gate': 'specified', 'from': 'analyzed', 'to': 'specified'}
    ]
    (deltafuse_dir / 'transitions.jsonl').write_text('\n'.soin('\n'.join(json.dumps(t) for t in transitions)) if False else '\n'.join(json.dumps(t) for t in transitions) + '\n', encoding='utf-8')
    (change_dir / 'change.yaml').write_text('id: CHG-001\nstatus: specified\nintent: feature\n', encoding='utf-8')

    obs = bridge.observe_core(tmp_path)
    assert obs.step == 'decompose'
    assert obs.envelope is not None
    assert 'write' in obs.envelope
    for pattern in obs.envelope['write']:
        assert not pattern.startswith('src/')


def test_core_bridge_detects_human_gate_and_returns_null_envelope(tmp_path):
    bridge = _load_core_bridge()
    deltafuse_dir = tmp_path / '.deltafuse'
    deltafuse_dir.mkdir()
    (deltafuse_dir / 'lock.yaml').write_text('schema_version: 1\nversion: 3.0.0\n', encoding='utf-8')
    (deltafuse_dir / 'config.yaml').write_text('project:\n  baseline: accepted\n', encoding='utf-8')
    (tmp_path / 'docs' / 'intake').mkdir(parents=True)
    change_dir = tmp_path / 'docs' / 'changes' / 'CHG-001'
    change_dir.mkdir(parents=True)
    (change_dir / 'routing.yaml').write_text('schema_version: 1\nroute: standard\n', encoding='utf-8')
    (change_dir / 'coverage.yaml').write_text('schema_version: 1\ncoverage: complete\n', encoding='utf-8')

    transitions = [
        {'kind': 'transition', 'change': 'CHG-001', 'gate': 'intake', 'from': 'normalized', 'to': 'analyzing'},
        {'kind': 'transition', 'change': 'CHG-001', 'gate': 'analyzed', 'from': 'analyzing', 'to': 'analyzed'}
    ]
    (deltafuse_dir / 'transitions.jsonl').write_text('\n'.join(json.dumps(t) for t in transitions) + '\n', encoding='utf-8')
    (change_dir / 'change.yaml').write_text('id: CHG-001\nstatus: specification-proposed\nintent: feature\n', encoding='utf-8')

    obs = bridge.observe_core(tmp_path)
    assert obs.halt is not None
    assert obs.halt.get('kind') == 'spec'
    assert obs.envelope is None
